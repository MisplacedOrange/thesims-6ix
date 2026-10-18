"""Local, SQLite-backed Council for one bounded municipal food-site scenario."""

from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import math
import re
import sqlite3
import sys
import threading
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

from sim import core
from sim.data.simulation_sites import load_simulation_site_snapshot
from sim.interactables.simulation import HORIZON, MunicipalSiteSchedule, run as run_food_day

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "apps" / "web" / "public" / "data" / "toronto.json"
SITE_SNAPSHOT_PATH = ROOT / "sim" / "data" / "snapshots" / "toronto-downtown-sites-v3.json"
DEFAULT_DB = ROOT / "state" / "council.sqlite"
DEFAULT_POPULATION = 600
DEFAULT_SEED = 2026
MAX_MARKDOWN = 200_000
MAX_GRANT_CENTS = 30_000
MAX_STOCK_GRAMS = 60_000
SECTION_NAMES = {
    "constraints": "constraints", "measures": "measures", "assumptions": "assumptions",
    "goals": "goals", "changes": "changes", "unknowns": "unknowns",
}


def _simulator_version() -> str:
    digest = hashlib.sha256()
    paths = [ROOT / "sim" / "council.py"]
    for package in ("core", "interactables", "data"):
        paths.extend(path for path in (ROOT / "sim" / package).rglob("*.py")
                     if "tests" not in path.relative_to(ROOT / "sim" / package).parts
                     and not path.name.startswith("test_"))
    for path in sorted(set(paths), key=lambda item: item.relative_to(ROOT).as_posix()):
        relative = path.relative_to(ROOT).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    runtime = f"{sys.implementation.name}-{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return f"python-{runtime}/core-{core.KERNEL_VERSION}/council-food-v1+{digest.hexdigest()}"


SIMULATOR_VERSION = _simulator_version()


class CouncilError(Exception):
    def __init__(self, status: int, code: str, message: str, current_revision: int | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.current_revision = current_revision


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _record_hash(value: dict[str, Any]) -> str:
    return _sha({key: item for key, item in value.items() if key != "sha256"})


def _strict_int(value: Any, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise CouncilError(400, "invalid_field", f"{label} must be an integer from {minimum} to {maximum}.")
    return value


def _text(value: Any, label: str, limit: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > limit or (not allow_empty and not value.strip()):
        raise CouncilError(400, "invalid_field", f"{label} must be text of at most {limit} characters.")
    return value


def _fields(payload: Any, required: set[str]) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != required:
        raise CouncilError(400, "invalid_body", "Request body has missing or unexpected fields.")
    return payload


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(value)
    return result


def _span_blocks(lines: list[str], start: int, end: int) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    current: list[str] = []
    first = 0
    for index in range(start, end):
        line = lines[index]
        if line.strip():
            if not current:
                first = index + 1
            current.append(line)
        elif current:
            blocks.append({"start_line": first, "end_line": index, "text": "\n".join(current)})
            current = []
    if current:
        blocks.append({"start_line": first, "end_line": end, "text": "\n".join(current)})
    return blocks


def parse_markdown(markdown: str) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], list[dict[str, str]]]:
    lines = markdown.splitlines()
    fenced_lines = [False] * len(lines)
    fence_char: str | None = None
    fence_length = 0
    for index, line in enumerate(lines):
        if fence_char is None:
            opening = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
            if opening:
                marker = opening.group(1)
                fence_char, fence_length = marker[0], len(marker)
                fenced_lines[index] = True
        else:
            fenced_lines[index] = True
            if re.match(rf"^ {{0,3}}{re.escape(fence_char)}{{{fence_length},}}\s*$", line):
                fence_char, fence_length = None, 0
    sections = {key: [] for key in SECTION_NAMES}
    unclassified: list[dict[str, Any]] = []
    active_name: str | None = None
    active_start = 0
    unclassified_ranges: list[tuple[int, int]] = []
    unclassified_start = 0
    for index, line in enumerate(lines):
        if fenced_lines[index]:
            continue
        heading = re.match(r"^\s*##\s+(.+?)\s*#*\s*$", line)
        if not heading:
            continue
        if active_name is not None:
            sections[active_name].extend(_span_blocks(lines, active_start, index))
        elif unclassified_start < index:
            unclassified_ranges.append((unclassified_start, index))
        title = heading.group(1).strip().casefold()
        active_name = SECTION_NAMES.get(title)
        if active_name is None:
            unclassified_start = index
        else:
            active_start = index + 1
            unclassified_start = index + 1
    if active_name is not None:
        sections[active_name].extend(_span_blocks(lines, active_start, len(lines)))
    elif unclassified_start < len(lines):
        unclassified_ranges.append((unclassified_start, len(lines)))
    for start, end in unclassified_ranges:
        unclassified.extend(_span_blocks(lines, start, end))
    citations = [
        {"label": label.strip(), "url": url, "status": "unverified_reference"}
        for label, url in re.findall(r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
                                     "\n".join("" if fenced else line for fenced, line in zip(fenced_lines, lines)))
    ]
    return sections, unclassified, citations


def _world_inputs(population: int, seed: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    try:
        map_raw = MAP_PATH.read_bytes()
        district = json.loads(map_raw)
        site_snapshot, snapshot_hash = load_simulation_site_snapshot(SITE_SNAPSHOT_PATH)
        catalog = core.load_catalog()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise CouncilError(503, "inputs_unavailable", f"Pinned simulation inputs are unavailable: {exc}") from exc
    if site_snapshot.get("map_sha256") != hashlib.sha256(map_raw).hexdigest():
        raise CouncilError(409, "inputs_changed", "The map and pinned site snapshot no longer match. Recheck inputs before planning.")
    world = {
        "population": population,
        "seed": seed,
        "map_sha256": hashlib.sha256(map_raw).hexdigest(),
        "catalog_id": catalog.catalog_id,
        "catalog_sha256": catalog.sha256,
        "source_snapshot_id": str(site_snapshot["source_snapshot_id"]),
        "source_sha256": snapshot_hash,
        "simulator_version": SIMULATOR_VERSION,
    }
    world["sha256"] = _sha(world)
    return world, district, site_snapshot


class CouncilService:
    """Own one immutable-record workflow and its mutable session head."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS head (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    session_id TEXT NOT NULL UNIQUE,
                    revision INTEGER NOT NULL,
                    proposal_id TEXT,
                    scope_id TEXT,
                    plan_id TEXT,
                    decision_id TEXT,
                    latest_run_id TEXT
                );
                CREATE TABLE IF NOT EXISTS records (
                    record_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    body_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS receipts (
                    session_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    status INTEGER NOT NULL,
                    response_json TEXT NOT NULL,
                    PRIMARY KEY(session_id, idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS run_traces (
                    record_id TEXT NOT NULL REFERENCES records(record_id),
                    arm TEXT NOT NULL CHECK(arm IN ('baseline','intervention')),
                    sha256 TEXT NOT NULL,
                    body_json TEXT NOT NULL,
                    PRIMARY KEY(record_id, arm)
                );
                CREATE TRIGGER IF NOT EXISTS records_no_update
                    BEFORE UPDATE ON records BEGIN SELECT RAISE(ABORT, 'records are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS records_no_delete
                    BEFORE DELETE ON records BEGIN SELECT RAISE(ABORT, 'records are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS receipts_no_update
                    BEFORE UPDATE ON receipts BEGIN SELECT RAISE(ABORT, 'receipts are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS receipts_no_delete
                    BEFORE DELETE ON receipts BEGIN SELECT RAISE(ABORT, 'receipts are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS run_traces_no_update
                    BEFORE UPDATE ON run_traces BEGIN SELECT RAISE(ABORT, 'run traces are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS run_traces_no_delete
                    BEFORE DELETE ON run_traces BEGIN SELECT RAISE(ABORT, 'run traces are immutable'); END;
            """)
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM head WHERE singleton=1").fetchone() is None:
                connection.execute(
                    "INSERT INTO head(singleton,session_id,revision) VALUES(1,?,0)",
                    (str(uuid.uuid4()),),
                )
            connection.commit()

    def _head(self, connection: sqlite3.Connection) -> dict[str, Any]:
        row = connection.execute("SELECT * FROM head WHERE singleton=1").fetchone()
        if row is None:
            raise RuntimeError("Council database has no session head")
        return dict(row)

    def _record(self, connection: sqlite3.Connection, record_id: str) -> dict[str, Any] | None:
        row = connection.execute("SELECT body_json FROM records WHERE record_id=?", (record_id,)).fetchone()
        return json.loads(row["body_json"]) if row else None

    def _all_records(self, connection: sqlite3.Connection, kind: str) -> list[dict[str, Any]]:
        return [json.loads(row["body_json"]) for row in connection.execute(
            "SELECT body_json FROM records WHERE kind=? ORDER BY revision,record_id", (kind,))]

    def _state(self, connection: sqlite3.Connection) -> dict[str, Any]:
        head = self._head(connection)
        proposal = self._record(connection, head["proposal_id"]) if head["proposal_id"] else None
        scope = self._record(connection, head["scope_id"]) if head["scope_id"] else None
        plan = self._record(connection, head["plan_id"]) if head["plan_id"] else None
        proposals = self._all_records(connection, "proposal")
        scopes = self._all_records(connection, "scope")
        decisions = self._all_records(connection, "decision")
        runs = self._all_records(connection, "run")
        for decision in decisions:
            decision["current"] = (
                decision["id"] == head["decision_id"]
                and decision["proposal_id"] == head["proposal_id"]
                and decision["scope_id"] == head["scope_id"]
                and decision["plan_id"] == head["plan_id"]
            )
        return {
            "schema": 1,
            "session_id": head["session_id"],
            "revision": head["revision"],
            "proposal": proposal,
            "proposal_history": [{key: value for key, value in item.items()
                                  if key in {"id", "revision", "sha256", "markdown"}}
                                 for item in proposals],
            "scope": scope,
            "scope_history": scopes,
            "plan": plan,
            "decisions": decisions,
            "runs": runs,
            "locations": self._locations(),
            "service": {"available": True},
        }

    def _source_context(self) -> dict[str, Any]:
        snapshot, digest = load_simulation_site_snapshot(SITE_SNAPSHOT_PATH)
        return {
            "snapshot_id": snapshot["source_snapshot_id"],
            "sha256": digest,
            "retrieved_at": snapshot.get("source_snapshot_retrieved_at"),
            "limits": snapshot.get("evidence_limits", []),
        }

    def _locations(self) -> list[dict[str, Any]]:
        snapshot, _ = load_simulation_site_snapshot(SITE_SNAPSHOT_PATH)
        return [
            {"id": key, "label": value["display_name"], "point": value["scene_point"],
             "source_record_id": value.get("source_record_id"), "operation_status": "unknown",
             "authority": "unknown"}
            for key, value in sorted(snapshot["sites"].items())
        ]

    def state(self) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN")
            try:
                state = self._state(connection)
                connection.commit()
                return state
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _request_hash(route: str, payload: dict[str, Any]) -> str:
        return _sha({"route": route, "payload": payload})

    @staticmethod
    def _stable_id(session_id: str, key: str, kind: str) -> str:
        return f"{kind}-{hashlib.sha256((session_id + '|' + key).encode('utf-8')).hexdigest()[:24]}"

    def _record_insert(self, connection: sqlite3.Connection, kind: str,
                       revision: int, record: dict[str, Any]) -> None:
        connection.execute(
            "INSERT INTO records(record_id,kind,revision,sha256,body_json) VALUES(?,?,?,?,?)",
            (record["id"], kind, revision, record["sha256"], _json(record)),
        )

    def _begin(self, route: str, expected_revision: int, key: str,
               payload: dict[str, Any]) -> tuple[sqlite3.Connection, dict[str, Any], str, dict[str, Any] | None]:
        if not isinstance(key, str) or not key or len(key) > 200 or any(ord(c) < 32 for c in key):
            raise CouncilError(400, "invalid_idempotency_key", "Idempotency-Key must contain 1 to 200 printable characters.")
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
            raise CouncilError(400, "invalid_revision", "If-Match must be a non-negative integer revision.")
        request_hash = self._request_hash(route, payload)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            head = self._head(connection)
            receipt = connection.execute(
                "SELECT request_sha256,status,response_json FROM receipts WHERE session_id=? AND idempotency_key=?",
                (head["session_id"], key),
            ).fetchone()
            if receipt:
                connection.rollback()
                if receipt["request_sha256"] != request_hash:
                    raise CouncilError(409, "idempotency_conflict", "This key was already used with a different request.", head["revision"])
                cached = {"status": receipt["status"], "body": json.loads(receipt["response_json"])}
                connection.close()
                return connection, head, request_hash, cached
            if head["revision"] != expected_revision:
                connection.rollback()
                raise CouncilError(409, "revision_conflict", "Council state changed. Reload it before submitting this command.", head["revision"])
            return connection, head, request_hash, None
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            connection.close()
            raise

    def _finish(self, connection: sqlite3.Connection, head: dict[str, Any], key: str,
                request_hash: str, new_values: dict[str, Any]) -> dict[str, Any]:
        head.update(new_values)
        head["revision"] += 1
        connection.execute(
            "UPDATE head SET revision=?,proposal_id=?,scope_id=?,plan_id=?,decision_id=?,latest_run_id=? WHERE singleton=1",
            (head["revision"], head["proposal_id"], head["scope_id"], head["plan_id"],
             head["decision_id"], head["latest_run_id"]),
        )
        response = self._state(connection)
        connection.execute(
            "INSERT INTO receipts(session_id,idempotency_key,request_sha256,status,response_json) VALUES(?,?,?,?,?)",
            (head["session_id"], key, request_hash, 200, _json(response)),
        )
        connection.commit()
        return response

    def _command(self, route: str, expected: int, key: str, payload: dict[str, Any],
                 write: Callable[[sqlite3.Connection, dict[str, Any], str], dict[str, Any]]) -> dict[str, Any]:
        connection, head, request_hash, cached = self._begin(route, expected, key, payload)
        if cached is not None:
            return cached["body"]
        try:
            values = write(connection, head, key)
            return self._finish(connection, head, key, request_hash, values)
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def command(self, route: str, expected: int, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        if route == "/proposals":
            def write(connection: sqlite3.Connection, head: dict[str, Any], command_key: str) -> dict[str, Any]:
                data = _fields(payload, {"markdown"})
                markdown = _text(data["markdown"], "markdown", MAX_MARKDOWN)
                sections, unclassified, citations = parse_markdown(markdown)
                revision = len(self._all_records(connection, "proposal")) + 1
                record = {
                    "id": self._stable_id(head["session_id"], command_key, "proposal"),
                    "revision": revision, "markdown": markdown,
                    "sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
                    "sections": sections, "unclassified": unclassified, "citations": citations,
                    "source_context": self._source_context(),
                }
                self._record_insert(connection, "proposal", head["revision"] + 1, record)
                return {"proposal_id": record["id"], "scope_id": None, "plan_id": None,
                        "decision_id": None, "latest_run_id": head["latest_run_id"]}
            return self._command(route, expected, key, payload, write)
        if route == "/scopes":
            def write(connection: sqlite3.Connection, head: dict[str, Any], command_key: str) -> dict[str, Any]:
                data = _fields(payload, {"proposal_id", "evaluated_scope", "excluded_scope", "reviewer_note"})
                proposal = self._record(connection, head["proposal_id"]) if head["proposal_id"] else None
                if not proposal or data["proposal_id"] != proposal["id"]:
                    raise CouncilError(409, "proposal_conflict", "Scope must refer to the current proposal revision.", head["revision"])
                record = {
                    "id": self._stable_id(head["session_id"], command_key, "scope"),
                    "proposal_id": proposal["id"], "proposal_sha256": proposal["sha256"],
                    "evaluated_scope": _text(data["evaluated_scope"], "evaluated_scope", 4000),
                    "excluded_scope": _text(data["excluded_scope"], "excluded_scope", 4000, allow_empty=True),
                    "reviewer_note": _text(data["reviewer_note"], "reviewer_note", 2000, allow_empty=True),
                }
                record["sha256"] = _record_hash(record)
                self._record_insert(connection, "scope", head["revision"] + 1, record)
                return {"scope_id": record["id"], "plan_id": None,
                        "decision_id": None, "latest_run_id": head["latest_run_id"]}
            return self._command(route, expected, key, payload, write)
        if route == "/plans":
            def write(connection: sqlite3.Connection, head: dict[str, Any], command_key: str) -> dict[str, Any]:
                data = _fields(payload, {"proposal_id", "scope_id", "action", "parameters", "population", "seed"})
                proposal = self._record(connection, head["proposal_id"]) if head["proposal_id"] else None
                scope = self._record(connection, head["scope_id"]) if head["scope_id"] else None
                if not proposal or data["proposal_id"] != proposal["id"] or not scope or data["scope_id"] != scope["id"]:
                    raise CouncilError(409, "scope_conflict", "Plan must refer to the current proposal and saved scope.", head["revision"])
                population = _strict_int(data["population"], "population", 200, 1200)
                if population not in {200, 600, 1200}:
                    raise CouncilError(400, "invalid_population", "Population must match a supported city setting.")
                seed = _strict_int(data["seed"], "seed", 0, 2**31 - 1)
                world, _, snapshot = _world_inputs(population, seed)
                action = data["action"]
                if not isinstance(action, str) or action not in {"establish_service_site", "unsupported"}:
                    raise CouncilError(400, "unsupported_action", "Choose a listed action or explicitly mark this scope unsupported.")
                parameters = None
                blockers: list[str] = []
                if action == "establish_service_site":
                    parameters = self._site_parameters(data["parameters"], population, snapshot)
                    procurement = parameters["stock_grams"] * 20 // 100
                    available_stock = population * 200
                    if parameters["grant_cents"] < procurement:
                        blockers.append(f"Grant {parameters['grant_cents']}¢ cannot cover the full {procurement}¢ supplier purchase.")
                    if parameters["stock_grams"] <= 0:
                        blockers.append("No supplier stock was requested.")
                    if parameters["stock_grams"] > available_stock:
                        blockers.append(f"Supplier opening stock is {available_stock} g, below the requested {parameters['stock_grams']} g.")
                else:
                    if data["parameters"] is not None:
                        raise CouncilError(400, "invalid_plan", "An unsupported action cannot carry executable parameters.")
                    blockers.append("This scope has no supported simulator action.")
                record = {
                    "id": self._stable_id(head["session_id"], command_key, "plan"),
                    "proposal_id": proposal["id"], "proposal_sha256": proposal["sha256"],
                    "scope_id": scope["id"], "scope_sha256": scope["sha256"],
                    "action": action, "parameters": parameters,
                    "execution_blockers": blockers, "advice": self._advice(parameters, blockers, action),
                    "world": world,
                }
                record["sha256"] = _record_hash(record)
                self._record_insert(connection, "plan", head["revision"] + 1, record)
                return {"plan_id": record["id"], "decision_id": None,
                        "latest_run_id": head["latest_run_id"]}
            return self._command(route, expected, key, payload, write)
        if route == "/decisions":
            def write(connection: sqlite3.Connection, head: dict[str, Any], command_key: str) -> dict[str, Any]:
                data = _fields(payload, {"proposal_id", "proposal_sha256", "scope_id", "scope_sha256",
                                         "plan_id", "plan_sha256", "world_sha256", "choice", "reason",
                                         "confirmed_no_launch"})
                proposal = self._record(connection, head["proposal_id"]) if head["proposal_id"] else None
                scope = self._record(connection, head["scope_id"]) if head["scope_id"] else None
                plan = self._record(connection, head["plan_id"]) if head["plan_id"] else None
                expected = (proposal, scope, plan)
                if (any(item is None for item in expected)
                        or data["proposal_id"] != proposal["id"] or data["proposal_sha256"] != proposal["sha256"]
                        or data["scope_id"] != scope["id"] or data["scope_sha256"] != scope["sha256"]
                        or data["plan_id"] != plan["id"] or data["plan_sha256"] != plan["sha256"]
                        or data["world_sha256"] != plan["world"]["sha256"]):
                    raise CouncilError(409, "approval_conflict", "Decision references must match the current proposal, scope, plan and world.", head["revision"])
                current_world, _, _ = _world_inputs(plan["world"]["population"], plan["world"]["seed"])
                if current_world != plan["world"]:
                    raise CouncilError(409, "world_changed", "Frozen inputs changed since this plan was saved. Save a new plan before recording a decision.", head["revision"])
                choice = data["choice"]
                if not isinstance(choice, str) or choice not in {"approve", "request_revision", "reject"}:
                    raise CouncilError(400, "invalid_choice", "Choose approve, request_revision, or reject.")
                confirmed = data["confirmed_no_launch"]
                if not isinstance(confirmed, bool):
                    raise CouncilError(400, "invalid_field", "confirmed_no_launch must be a boolean.")
                if choice == "approve" and plan["action"] == "unsupported":
                    raise CouncilError(409, "unsupported_action", "Unsupported scope cannot be approved for execution.", head["revision"])
                if choice == "approve" and plan["execution_blockers"] and not confirmed:
                    raise CouncilError(409, "no_launch_confirmation_required", "Confirm the blocked plan will produce a no-launch run.", head["revision"])
                if choice != "approve" and confirmed:
                    raise CouncilError(400, "invalid_confirmation", "No-launch confirmation is only valid for an approved blocked plan.")
                record = {
                    "id": self._stable_id(head["session_id"], command_key, "decision"),
                    "proposal_id": proposal["id"], "proposal_sha256": proposal["sha256"],
                    "scope_id": scope["id"], "scope_sha256": scope["sha256"],
                    "plan_id": plan["id"], "plan_sha256": plan["sha256"],
                    "world_sha256": plan["world"]["sha256"], "choice": choice,
                    "reason": _text(data["reason"], "reason", 2000, allow_empty=True),
                    "confirmed_no_launch": confirmed,
                }
                record["sha256"] = _record_hash(record)
                self._record_insert(connection, "decision", head["revision"] + 1, record)
                return {"decision_id": record["id"], "latest_run_id": head["latest_run_id"]}
            return self._command(route, expected, key, payload, write)
        if route == "/runs":
            return self._run_command(expected, key, payload)
        raise CouncilError(404, "unknown_command", "Unknown Council command.")

    def _site_parameters(self, raw: Any, population: int, snapshot: dict[str, Any]) -> dict[str, Any]:
        required = {"location_id", "grant_cents", "stock_grams", "service_capacity", "operator_assumption",
                    "readiness_second", "funding_second", "delivery_second", "commissioning_second",
                    "open_second", "close_second"}
        data = _fields(raw, required)
        location_id = _text(data["location_id"], "location_id", 80)
        if location_id not in snapshot["sites"]:
            raise CouncilError(400, "unknown_location", "Choose a location from the pinned site list.")
        if data["operator_assumption"] != "hypothetical_municipal_operator":
            raise CouncilError(400, "invalid_assumption", "The supported action requires the labeled hypothetical municipal operator assumption.")
        result: dict[str, Any] = {
            "location_id": location_id,
            "grant_cents": _strict_int(data["grant_cents"], "grant_cents", 0, MAX_GRANT_CENTS),
            "stock_grams": _strict_int(data["stock_grams"], "stock_grams", 0, MAX_STOCK_GRAMS),
            "service_capacity": _strict_int(data["service_capacity"], "service_capacity", 1, population),
            "operator_assumption": "hypothetical_municipal_operator",
        }
        if result["stock_grams"] % 100:
            raise CouncilError(400, "invalid_quantity", "Supplier quantity must use 100 g purchase units.")
        stage_fields = ("readiness_second", "funding_second", "delivery_second", "commissioning_second", "open_second", "close_second")
        for field in stage_fields:
            result[field] = _strict_int(data[field], field, 0, HORIZON)
        if not (result["readiness_second"] < result["funding_second"] < result["delivery_second"]
                < result["commissioning_second"] < result["open_second"] < result["close_second"]):
            raise CouncilError(400, "invalid_schedule", "Readiness, funding, delivery, commissioning, opening and closure must use strictly increasing ticks.")
        return result

    @staticmethod
    def _advice(parameters: dict[str, Any] | None, blockers: list[str], action: str) -> list[dict[str, str]]:
        if action == "unsupported":
            return [{"role": role, "status": "blocked", "authority": "advisory",
                     "note": "No supported site action was selected; this advice cannot authorize a run."}
                    for role in ("finance", "site_readiness", "supply", "access")]
        assert parameters is not None
        status = "blocked" if blockers else "caution"
        p = parameters
        return [
            {"role": "finance", "status": status, "authority": "advisory",
             "note": f"The scenario cap is {p['grant_cents']}¢. Full stock procurement costs {p['stock_grams'] * 20 // 100}¢; this is not a live appropriation."},
            {"role": "site_readiness", "status": "caution", "authority": "advisory",
             "note": "The selected record supplies a mapped point and label only. Operator authority and current operations remain unknown; the plan assumes a hypothetical municipal operator."},
            {"role": "supply", "status": status, "authority": "advisory",
             "note": f"The run requests {p['stock_grams']} g at an illustrative supplier price of 20¢ per 100 g."},
            {"role": "access", "status": "caution", "authority": "advisory",
             "note": f"The synthetic scenario permits {p['service_capacity']} visits after opening. Observed eligibility, demand and service outcomes are unknown."},
        ]

    def _run_command(self, expected: int, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        route = "/runs"
        connection, head, request_hash, cached = self._begin(route, expected, key, payload)
        if cached is not None:
            return cached["body"]
        try:
            data = _fields(payload, {"decision_id"})
            decision = self._record(connection, head["decision_id"]) if head["decision_id"] else None
            plan = self._record(connection, head["plan_id"]) if head["plan_id"] else None
            proposal = self._record(connection, head["proposal_id"]) if head["proposal_id"] else None
            scope = self._record(connection, head["scope_id"]) if head["scope_id"] else None
            if (not decision or not plan or not proposal or not scope or data["decision_id"] != decision["id"]
                    or decision["choice"] != "approve" or plan["action"] != "establish_service_site"
                    or decision["proposal_sha256"] != proposal["sha256"]
                    or decision["scope_sha256"] != scope["sha256"]
                    or decision["plan_sha256"] != plan["sha256"]
                    or decision["world_sha256"] != plan["world"]["sha256"]):
                raise CouncilError(409, "run_not_approved", "Run requires the current approval of a supported exact plan.", head["revision"])
            if plan["execution_blockers"] and not decision["confirmed_no_launch"]:
                raise CouncilError(409, "no_launch_confirmation_required", "The approved plan has blockers and no explicit no-launch confirmation.", head["revision"])
            connection.rollback()
            connection.close()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

        world = plan["world"]
        live_world, district, site_snapshot = _world_inputs(world["population"], world["seed"])
        if live_world != world:
            raise CouncilError(409, "world_changed", "Frozen inputs differ from the current files. Save a new plan before running.", expected)
        run_id = "council-" + hashlib.sha256((head["session_id"] + "|" + key).encode("utf-8")).hexdigest()[:24]
        params = plan["parameters"]
        schedule = MunicipalSiteSchedule(
            site_id="council-site-" + plan["id"][-12:], location_id=params["location_id"],
            grant_cents=params["grant_cents"], stock_grams=params["stock_grams"],
            service_capacity=params["service_capacity"], readiness_second=params["readiness_second"],
            funding_second=params["funding_second"], delivery_second=params["delivery_second"],
            commissioning_second=params["commissioning_second"], open_second=params["open_second"],
            close_second=params["close_second"], blocker_reasons=tuple(plan["execution_blockers"]),
        )
        population, seed = world["population"], world["seed"]
        try:
            baseline = run_food_day(district, population, seed, False, (), site_snapshot,
                                    world["source_sha256"], council_run_ref={
                                        "kind": "council", "run_id": run_id, "arm": "baseline"})
            intervention = run_food_day(district, population, seed, False, (), site_snapshot,
                                        world["source_sha256"], schedule, {
                                            "kind": "council", "run_id": run_id, "arm": "intervention"})
        except (ValueError, RuntimeError, core.ConservationError) as exc:
            raise CouncilError(422, "simulation_failed", f"The bounded simulation could not complete: {exc}") from exc
        trace_hashes = {"baseline": _sha(baseline), "intervention": _sha(intervention)}
        runtime_blockers = [event["reason"] for event in intervention.get("rollout_events", [])
                            if event["stage"] in {"blocked", "no_launch"}
                            and event["status"] == "blocked" and event["reason"]]
        blockers = list(dict.fromkeys([*plan["execution_blockers"], *runtime_blockers]))
        record = {
            "id": run_id, "proposal_id": proposal["id"], "plan_id": plan["id"],
            "scope_id": scope["id"], "decision_id": decision["id"],
            "inputs_sha256": world["sha256"], "baseline_trace_sha256": trace_hashes["baseline"],
            "intervention_trace_sha256": trace_hashes["intervention"],
            "population": population, "seed": seed,
            "status": "blocked" if blockers else "complete",
            "blockers": blockers,
        }
        record["sha256"] = _record_hash(record)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = self._head(connection)
            receipt = connection.execute(
                "SELECT request_sha256,status,response_json FROM receipts WHERE session_id=? AND idempotency_key=?",
                (current["session_id"], key),
            ).fetchone()
            if receipt:
                connection.rollback()
                if receipt["request_sha256"] != request_hash:
                    raise CouncilError(409, "idempotency_conflict", "This key was already used with a different request.", current["revision"])
                return json.loads(receipt["response_json"])
            if (current["revision"] != expected or current["decision_id"] != decision["id"]
                    or current["plan_id"] != plan["id"] or current["proposal_id"] != proposal["id"]
                    or current["scope_id"] != scope["id"]):
                raise CouncilError(409, "revision_conflict", "Council changed while the run was computing. No run was committed.", current["revision"])
            next_revision = current["revision"] + 1
            self._record_insert(connection, "run", next_revision, record)
            for arm, trace in (("baseline", baseline), ("intervention", intervention)):
                connection.execute(
                    "INSERT INTO run_traces(record_id,arm,sha256,body_json) VALUES(?,?,?,?)",
                    (run_id, arm, trace_hashes[arm], _json(trace)),
                )
            current.update(revision=next_revision, latest_run_id=run_id)
            connection.execute("UPDATE head SET revision=?,latest_run_id=? WHERE singleton=1",
                               (next_revision, run_id))
            response = self._state(connection)
            connection.execute(
                "INSERT INTO receipts(session_id,idempotency_key,request_sha256,status,response_json) VALUES(?,?,?,?,?)",
                (current["session_id"], key, request_hash, 200, _json(response)),
            )
            connection.commit()
            return response
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def trace(self, run_id: str, arm: str) -> dict[str, Any]:
        if arm not in {"baseline", "intervention"}:
            raise CouncilError(404, "unknown_arm", "Council run arm was not found.")
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT body_json FROM run_traces WHERE record_id=? AND arm=?", (run_id, arm)
            ).fetchone()
        if not row:
            raise CouncilError(404, "unknown_run", "Council run was not found.")
        return json.loads(row["body_json"])


class CouncilHandler(BaseHTTPRequestHandler):
    service: CouncilService
    max_body_bytes = MAX_MARKDOWN + 16_384

    def _reply(self, status: int, body: dict[str, Any]) -> None:
        raw = _json(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _error(self, error: CouncilError) -> None:
        value = {"error": {"code": error.code, "message": error.message}}
        if error.current_revision is not None:
            value["error"]["current_revision"] = error.current_revision
        self._reply(error.status, value)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        try:
            if path == "/api/council":
                self._reply(200, self.service.state())
                return
            match = re.fullmatch(r"/api/council/runs/([a-zA-Z0-9-]+)/traces/(baseline|intervention)", path)
            if match:
                self._reply(200, self.service.trace(unquote(match.group(1)), match.group(2)))
                return
            raise CouncilError(404, "not_found", "Council resource was not found.")
        except CouncilError as error:
            self._error(error)
        except (OSError, ValueError) as error:
            self._error(CouncilError(503, "service_error", str(error)))

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        route = path.removeprefix("/api/council")
        if path not in {"/api/council/proposals", "/api/council/scopes", "/api/council/plans",
                        "/api/council/decisions", "/api/council/runs"}:
            self._error(CouncilError(404, "not_found", "Council command was not found."))
            return
        try:
            if self.headers.get("X-Council-Schema") != "1":
                raise CouncilError(400, "unsupported_schema", "X-Council-Schema must be 1.")
            length_text = self.headers.get("Content-Length", "")
            if not length_text.isdecimal():
                raise CouncilError(400, "invalid_length", "Content-Length must be a positive integer.")
            length = int(length_text)
            if length <= 0 or length > self.max_body_bytes:
                raise CouncilError(413, "body_too_large", "Request body exceeds the local service limit.")
            raw = self.rfile.read(length)
            try:
                payload = json.loads(
                    raw,
                    parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
                    parse_float=_finite_float,
                )
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
                raise CouncilError(400, "invalid_json", "Request body must be valid JSON without NaN or infinity.") from exc
            if not isinstance(payload, dict):
                raise CouncilError(400, "invalid_body", "Request body must be a JSON object.")
            if_match = self.headers.get("If-Match", "")
            if not if_match.isdecimal():
                raise CouncilError(400, "invalid_revision", "If-Match must be a non-negative integer revision.")
            key = self.headers.get("Idempotency-Key")
            response = self.service.command(route, int(if_match), key, payload)
            self._reply(200, response)
        except CouncilError as error:
            self._error(error)
        except (OSError, sqlite3.Error, ValueError) as error:
            self._error(CouncilError(503, "service_error", str(error)))

    def log_message(self, format: str, *args: object) -> None:
        print("council: " + format % args)


def serve(db_path: Path = DEFAULT_DB, port: int = 8765) -> None:
    service = CouncilService(db_path)
    handler = type("BoundCouncilHandler", (CouncilHandler,), {"service": service})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    print(f"Council API listening on http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    serve(args.db, args.port)


if __name__ == "__main__":
    main()
