"""HTTP, restart, idempotency and bounded run behavior for the local Council."""

from __future__ import annotations

import hashlib
import json
import threading
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import sim.council as council
import pytest
from sim.council import CouncilHandler, CouncilService


@contextmanager
def council_api(db_path: Path):
    service = CouncilService(db_path)
    handler = type("TestCouncilHandler", (CouncilHandler,), {"service": service})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        yield base
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def request(base: str, path: str, method: str = "GET", *, body=None, revision=None,
            key=None, raw=None, schema="1"):
    headers = {}
    data = None
    if method == "POST":
        headers["X-Council-Schema"] = schema
        headers["If-Match"] = str(revision)
        headers["Idempotency-Key"] = key
        headers["Content-Type"] = "application/json"
        data = raw if raw is not None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = Request(base + path, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=90) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def post(base: str, path: str, revision: int, key: str, body: dict):
    status, result = request(base, path, "POST", revision=revision, key=key, body=body)
    assert status == 200, result
    assert result["schema"] == 1
    return result


def proposal_body(markdown: str):
    return {"markdown": markdown}


def scope_body(proposal):
    return {"proposal_id": proposal["id"], "evaluated_scope": "One hypothetical municipal food site.",
            "excluded_scope": "No provider conversion or multi-day effects.",
            "reviewer_note": "Explicitly narrow the proposal to the supported one-day action."}


def plan_body(state, stock_grams: int):
    return {
        "proposal_id": state["proposal"]["id"],
        "scope_id": state["scope"]["id"],
        "action": "establish_service_site",
        "population": 200,
        "seed": 2026,
        "parameters": {
            "location_id": state["locations"][0]["id"],
            "grant_cents": 10_000,
            "stock_grams": stock_grams,
            "service_capacity": 12,
            "operator_assumption": "hypothetical_municipal_operator",
            "readiness_second": 500,
            "funding_second": 1_000,
            "delivery_second": 6_000,
            "commissioning_second": 7_000,
            "open_second": 8_000,
            "close_second": 20_000,
        },
    }


def decision_body(state, confirmed_no_launch=False):
    proposal, scope, plan = state["proposal"], state["scope"], state["plan"]
    return {
        "proposal_id": proposal["id"], "proposal_sha256": proposal["sha256"],
        "scope_id": scope["id"], "scope_sha256": scope["sha256"],
        "plan_id": plan["id"], "plan_sha256": plan["sha256"],
        "world_sha256": plan["world"]["sha256"], "choice": "approve",
        "reason": "Approve the bounded plan for paired scenario comparison.",
        "confirmed_no_launch": confirmed_no_launch,
    }


def canonical_sha(value) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("action,target", [("expand_facility", 24), ("reduce_or_close_service", 6),
                                          ("reduce_or_close_service", 0)])
def test_capacity_action_compares_same_base_site_and_commits_only_at_effective_tick(tmp_path, action, target):
    with council_api(tmp_path / "council.sqlite") as base:
        state = post(base, "/api/council/proposals", 0, "p", proposal_body("## Changes\nAdjust municipal service."))
        state = post(base, "/api/council/scopes", state["revision"], "s", scope_body(state["proposal"]))
        body = plan_body(state, 20000)
        body.update(action=action, parameters={"base_site": body["parameters"],
                                              "effective_second": 12000, "target_capacity": target})
        state = post(base, "/api/council/plans", state["revision"], "p1", body)
        state = post(base, "/api/council/decisions", state["revision"], "d", decision_body(state))
        state = post(base, "/api/council/runs", state["revision"], "r", {"decision_id": state["decisions"][-1]["id"]})
        run = state["runs"][-1]
        assert run["status"] == "complete"
        baseline = request(base, f"/api/council/runs/{run['id']}/traces/baseline")[1]
        intervention = request(base, f"/api/council/runs/{run['id']}/traces/intervention")[1]
        assert baseline["accounting"]["invariant_problems"] == intervention["accounting"]["invariant_problems"] == []
        assert baseline["households"] == intervention["households"]
        assert not any(e["stage"] == "capacity_change" for e in baseline["rollout_events"])
        changed = [e for e in intervention["rollout_events"] if e["stage"] == "capacity_change"]
        assert len(changed) == 1 and changed[0]["capacity"] == target
        assert changed[0]["simulation_time"] == 12000 and changed[0]["status"] == "completed"
        assert [e for e in baseline["rollout_events"] if e["simulation_time"] < 12000] == [
            e for e in intervention["rollout_events"] if e["simulation_time"] < 12000]
        site_id = next(s["id"] for s in intervention["sites"] if s["type"] == "council")
        assert next(s for s in baseline["sites"] if s["id"] == site_id)["spending_cents"] == 4000
        assert next(s for s in intervention["sites"] if s["id"] == site_id)["spending_cents"] == 4000
        if target == 0:
            assert not any(e["action"] == "service" and e.get("site_id") == site_id
                           and e["simulation_time"] >= 12000 and e["result"] == "completed"
                           for e in intervention["events"])


def test_candidates_cannot_be_approved_and_capacity_validation_is_atomic(tmp_path):
    with council_api(tmp_path / "council.sqlite") as base:
        state = post(base, "/api/council/proposals", 0, "p", proposal_body("## Changes\nInfrastructure"))
        assert len(state["action_catalog"]) == 10
        state = post(base, "/api/council/scopes", state["revision"], "s", scope_body(state["proposal"]))
        for index, candidate in enumerate(item for item in state["action_catalog"] if not item["executable"]):
            body = plan_body(state, 20000)
            body.update(action=candidate["action"], parameters=None)
            state = post(base, "/api/council/plans", state["revision"], f"p{index}", body)
            assert state["plan"]["execution_blockers"]
            status, error = request(base, "/api/council/decisions", "POST", revision=state["revision"],
                                    key=f"d{index}", body=decision_body(state, True))
            assert status == 409 and error["error"]["code"] == "unsupported_action"
        for index, (action, target, second) in enumerate([
            ("expand_facility", 12, 12000), ("reduce_or_close_service", 24, 12000),
            ("expand_facility", 24, 8000), ("expand_facility", 24, 20000),
            ("expand_facility", True, 12000), ("reduce_or_close_service", -1, 12000),
        ]):
            body = plan_body(state, 20000)
            body.update(action=action, parameters={"base_site": body["parameters"],
                                                  "effective_second": second, "target_capacity": target})
            status, _ = request(base, "/api/council/plans", "POST", revision=state["revision"], key=f"bad{index}", body=body)
            assert status == 400
            assert request(base, "/api/council")[1]["revision"] == state["revision"]


def test_proposal_receipt_survives_restart_and_http_rejects_unversioned_or_non_json(tmp_path):
    db_path = tmp_path / "council.sqlite"
    markdown = "# Food site\r\n\r\n## Assumptions\r\nHypothetical operator.\r\n\r\n## Mystery\r\nKeep this text.\r\n"
    body = proposal_body(markdown)
    with council_api(db_path) as base:
        status, state = request(base, "/api/council")
        assert status == 200 and state["schema"] == 1 and state["revision"] == 0
        status, missing_version = request(base, "/api/council/proposals", "POST", revision=0,
                                          key="missing-schema", body=body, schema="")
        assert status == 400 and missing_version["error"]["code"] == "unsupported_schema"
        status, bad_json = request(base, "/api/council/proposals", "POST", revision=0,
                                   key="nan", raw=b'{"markdown":"x","value":NaN}')
        assert status == 400 and bad_json["error"]["code"] == "invalid_json"
        status, overflow = request(base, "/api/council/proposals", "POST", revision=0,
                                   key="overflow", raw=b'{"markdown":"x","value":1e309}')
        assert status == 400 and overflow["error"]["code"] == "invalid_json"
        saved = post(base, "/api/council/proposals", 0, "proposal-key", body)
        assert saved["proposal"]["markdown"] == markdown
        assert saved["proposal"]["sections"]["assumptions"] == [
            {"start_line": 4, "end_line": 4, "text": "Hypothetical operator."}]
        assert [span["text"] for span in saved["proposal"]["unclassified"]] == [
            "# Food site", "## Mystery\nKeep this text."]
        assert len(saved["proposal_history"]) == 1

    with council_api(db_path) as base:
        retried = post(base, "/api/council/proposals", 0, "proposal-key", body)
        assert retried["revision"] == 1
        assert retried["proposal"]["markdown"] == markdown
        status, conflict = request(base, "/api/council/proposals", "POST", revision=1,
                                   key="proposal-key", body=proposal_body(markdown + "amended"))
        assert status == 409 and conflict["error"]["code"] == "idempotency_conflict"
        status, stale = request(base, "/api/council/proposals", "POST", revision=0,
                                key="stale", body=proposal_body(markdown + "another"))
        assert status == 409 and stale["error"]["code"] == "revision_conflict"
        assert request(base, "/api/council")[1]["revision"] == 1


def test_http_intake_keeps_fenced_markdown_out_of_sections_and_citations(tmp_path):
    markdown = ("## Goals\nActual goal.\n\n```markdown\n## Assumptions\n"
                "Example only.\n[Example](https://example.invalid/source)\n```\n\n"
                "[Source](https://example.org/report)\n")
    with council_api(tmp_path / "council.sqlite") as base:
        state = post(base, "/api/council/proposals", 0, "proposal", proposal_body(markdown))
        proposal = state["proposal"]
        assert proposal["markdown"] == markdown
        assert [span["text"] for span in proposal["sections"]["goals"]] == [
            "Actual goal.", "```markdown\n## Assumptions\nExample only.\n"
            "[Example](https://example.invalid/source)\n```", "[Source](https://example.org/report)"]
        assert proposal["sections"]["assumptions"] == []
        assert proposal["citations"] == [{"label": "Source", "url": "https://example.org/report",
                                          "status": "unverified_reference"}]


def test_council_pair_runs_core_and_rechecks_same_tick_supplier_stock(tmp_path, monkeypatch):
    db_path = tmp_path / "council.sqlite"
    markdown = ("## Goals\r\nModel a neighborhood food site.\r\n\r\n"
                "## Unknowns\r\nOperator authority and observed need remain unknown.\r\n")
    with council_api(db_path) as base:
        state = post(base, "/api/council/proposals", 0, "proposal", proposal_body(markdown))
        state = post(base, "/api/council/scopes", state["revision"], "scope", scope_body(state["proposal"]))
        draft = plan_body(state, stock_grams=20_000)
        invalid_bool = dict(draft, population=True)
        status, _ = request(base, "/api/council/plans", "POST", revision=state["revision"],
                            key="bool-population", body=invalid_bool)
        assert status == 400
        invalid_fraction = plan_body(state, stock_grams=20_000)
        invalid_fraction["parameters"]["grant_cents"] = 10_000.5
        status, _ = request(base, "/api/council/plans", "POST", revision=state["revision"],
                            key="fraction-grant", body=invalid_fraction)
        assert status == 400
        invalid_quantity = plan_body(state, stock_grams=20_000)
        invalid_quantity["parameters"]["stock_grams"] = 1
        status, bad_quantity = request(base, "/api/council/plans", "POST", revision=state["revision"],
                                       key="single-gram", body=invalid_quantity)
        assert status == 400 and bad_quantity["error"]["code"] == "invalid_quantity"
        assert request(base, "/api/council")[1]["revision"] == state["revision"]
        state = post(base, "/api/council/plans", state["revision"], "plan-success", draft)
        assert state["plan"]["execution_blockers"] == []
        assert len(state["plan"]["world"]["simulator_version"].split("+")[-1]) == 64
        original_simulator_version = council.SIMULATOR_VERSION
        monkeypatch.setattr(council, "SIMULATOR_VERSION", original_simulator_version + "+changed")
        status, stale_approval = request(base, "/api/council/decisions", "POST", revision=state["revision"],
                                         key="approve-stale-world", body=decision_body(state))
        assert status == 409 and stale_approval["error"]["code"] == "world_changed"
        assert request(base, "/api/council")[1]["revision"] == state["revision"]
        monkeypatch.setattr(council, "SIMULATOR_VERSION", original_simulator_version)
        state = post(base, "/api/council/decisions", state["revision"], "approve-success", decision_body(state))
        good_run_request = {"decision_id": state["decisions"][-1]["id"]}
        state = post(base, "/api/council/runs", state["revision"], "run-success", good_run_request)
        good = state["runs"][-1]
        assert good["status"] == "complete"
        assert good["population"] == 200 and good["seed"] == 2026
        assert "traces" not in good
        status, baseline = request(base, f"/api/council/runs/{good['id']}/traces/baseline")
        assert status == 200
        status, intervention = request(base, f"/api/council/runs/{good['id']}/traces/intervention")
        assert status == 200
        assert baseline["run_ref"] == {"kind": "council", "run_id": good["id"], "arm": "baseline"}
        assert intervention["run_ref"] == {"kind": "council", "run_id": good["id"], "arm": "intervention"}
        assert baseline["households"] == intervention["households"]
        assert baseline["data_snapshot"]["content_sha256"] == intervention["data_snapshot"]["content_sha256"]
        assert intervention["accounting"]["invariant_problems"] == []
        assert intervention["accounting"]["total_cash_cents"] == 0
        assert intervention["accounting"]["imported_grams"] == (
            intervention["accounting"]["remaining_grams"] + intervention["accounting"]["consumed_grams"])
        assert good["baseline_trace_sha256"] == canonical_sha(baseline)
        assert good["intervention_trace_sha256"] == canonical_sha(intervention)
        milestones = intervention["rollout_events"]
        assert [event["stage"] for event in milestones] == [
            "readiness", "funding", "delivery", "commissioning", "opening", "closure"]
        assert [event["capacity"] for event in milestones] == [0, 0, 0, 0, 12, 0]
        site = next(site for site in intervention["sites"] if site["type"] == "council")
        assert site["received_grams"] == 20_000 and site["spending_cents"] == 4_000
        funding_event = next(event for event in intervention["events"] if event.get("stage") == "funding")
        assert funding_event["site_state"]["spending_cents"] == 0

        # A second scenario's same-second ordering makes the existing retail delivery
        # consume supplier stock first for this seed. The accepted plan must block at
        # delivery, return the unspent grant, and preserve zero service capacity.
        state = post(base, "/api/council/plans", state["revision"], "plan-short-stock",
                     plan_body(state, stock_grams=35_000))
        assert state["decisions"][-1]["current"] is False
        assert state["plan"]["execution_blockers"] == []
        assert state["plan"]["parameters"]["delivery_second"] == 6_000
        state = post(base, "/api/council/decisions", state["revision"], "approve-short-stock", decision_body(state))
        blocked_run_request = {"decision_id": state["decisions"][-1]["id"]}
        state = post(base, "/api/council/runs", state["revision"], "run-short-stock", blocked_run_request)
        blocked = state["runs"][-1]
        assert blocked["status"] == "blocked"
        assert blocked["blockers"] == ["full supplier quantity or procurement payment is unavailable"]
        _, blocked_trace = request(base, f"/api/council/runs/{blocked['id']}/traces/intervention")
        assert any(event["stage"] == "no_launch" for event in blocked_trace["rollout_events"])
        assert [event["capacity"] for event in blocked_trace["rollout_events"] if event["stage"] == "opening"] == [0]
        assert blocked_trace["accounting"]["invariant_problems"] == []
        blocked_site = next(site for site in blocked_trace["sites"] if site["type"] == "council")
        assert blocked_site["capacity"] == 0 and blocked_site["received_grams"] == 0
        assert blocked_site["spending_cents"] == 0
        assert blocked_trace["events"][-1]["public_spending_cents"] == 0
        state = post(base, "/api/council/plans", state["revision"], "plan-unsupported", {
            "proposal_id": state["proposal"]["id"], "scope_id": state["scope"]["id"],
            "action": "unsupported", "parameters": None, "population": 200, "seed": 2026,
        })
        unsupported_decision = decision_body(state)
        status, error = request(base, "/api/council/decisions", "POST", revision=state["revision"],
                               key="approve-unsupported", body=unsupported_decision)
        assert status == 409 and error["error"]["code"] == "unsupported_action"
        assert request(base, "/api/council")[1]["revision"] == state["revision"]
        blocked_plan = plan_body(state, stock_grams=60_000)
        blocked_plan["parameters"]["grant_cents"] = 10_000
        state = post(base, "/api/council/plans", state["revision"], "plan-static-blockers", blocked_plan)
        assert len(state["plan"]["execution_blockers"]) == 2
        status, error = request(base, "/api/council/decisions", "POST", revision=state["revision"],
                               key="approve-without-no-launch", body=decision_body(state))
        assert status == 409 and error["error"]["code"] == "no_launch_confirmation_required"
        state = post(base, "/api/council/decisions", state["revision"], "approve-confirmed-no-launch",
                     decision_body(state, confirmed_no_launch=True))

    with council_api(db_path) as base:
        state = request(base, "/api/council")[1]
        assert [run["id"] for run in state["runs"]] == [good["id"], blocked["id"]]
        _, replay = request(base, f"/api/council/runs/{good['id']}/traces/intervention")
        assert replay == intervention
        replayed_receipt = post(base, "/api/council/runs", 4, "run-success", good_run_request)
        assert replayed_receipt["revision"] == 5
        assert replayed_receipt["runs"][-1]["id"] == good["id"]
