"""Offline contract, approval boundaries, concurrency and provider failure checks."""
from __future__ import annotations

import json
from io import BytesIO
import sqlite3
import uuid
from contextlib import closing
from urllib.error import HTTPError, URLError

import pytest

from sim import council_planner as planner
from sim.council import CouncilError, CouncilService, _handle_council_request
from sim.test_council import scope_body, plan_body


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setattr(planner, "configuration", lambda: {
        "ready": True, "key": "sk-offline-test-credential", "model": "offline-model",
        "timeout_seconds": 30, "max_output_tokens": 3000, "reason": None,
    })
    service = CouncilService(tmp_path / "council.sqlite")
    state = service.command("/proposals", 0, "proposal", {"markdown": "# Municipal food pilot\n## Changes\nOne hypothetical municipal food site."})
    service.command("/scopes", state["revision"], "scope", scope_body(state["proposal"]))
    return service


def response_for(service, **changes):
    output = {"action": "establish_service_site", "parameters": plan_body(service.state(), 20_000)["parameters"],
              "organization_bindings": [], "rationale": "Test the hypothetical site.",
              "assumptions": "Illustrative municipal operation.", "exclusions": "No clinical claims.",
              "uncertainties": "Operating status is unknown."}
    output.update(changes)
    return {"id": "resp_offline", "model": "offline-resolved", "status": "completed",
            "usage": {"input_tokens": 100, "output_tokens": 120},
            "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(output)}]}]}


def generate(service, key=None):
    return service.command("/planner/drafts", service.state()["revision"], key or str(uuid.uuid4()),
                           {"population": 200, "seed": 2026, "consent_to_send": True})


def adopt(service):
    state = service.state()
    draft = state["planner"]["drafts"][-1]
    return service.command("/plans", state["revision"], str(uuid.uuid4()),
                           {**draft["command"], "planner_draft_id": draft["id"]})


def test_generate_adopt_approve_and_replay_need_no_new_model_call(service, monkeypatch):
    calls = []

    def transport(config, request):
        calls.append(request)
        assert config["key"] not in json.dumps(request)
        assert request["store"] is False
        assert request["text"]["format"]["strict"] is True
        context = json.loads(request["input"])
        assert context["proposal"]["markdown"].startswith("# Municipal")
        assert "expand_facility" in {item["action"] for item in context["action_catalog"]}
        return response_for(service), "request-offline"

    monkeypatch.setattr(planner, "request_openai", transport)
    before = service.state()
    generated = generate(service, "one-attempt")
    assert generated["plan"] is None and generated["decisions"] == []
    assert generated["revision"] == before["revision"] + 1
    # Same key replays even with the original revision and never bills again.
    replay = service.command("/planner/drafts", before["revision"], "one-attempt",
                             {"population": 200, "seed": 2026, "consent_to_send": True})
    assert replay == generated and len(calls) == 1
    state = adopt(service)
    assert state["plan"]["planner_draft_id"] == state["planner"]["drafts"][0]["id"]
    assert not state["decisions"]
    with pytest.raises(CouncilError, match="Run requires"):
        service.command("/runs", state["revision"], "unapproved", {"decision_id": "not-approved"})
    proposal, scope, plan = state["proposal"], state["scope"], state["plan"]
    state = service.command("/decisions", state["revision"], "approve", {
        "proposal_id": proposal["id"], "proposal_sha256": proposal["sha256"],
        "scope_id": scope["id"], "scope_sha256": scope["sha256"],
        "plan_id": plan["id"], "plan_sha256": plan["sha256"], "world_sha256": plan["world"]["sha256"],
        "choice": "approve", "reason": "Offline plumbing check only", "confirmed_no_launch": False})
    state = service.command("/runs", state["revision"], "run", {"decision_id": state["decisions"][-1]["id"]})
    assert state["runs"][-1]["status"] == "complete" and len(calls) == 1
    restarted = CouncilService(service.db_path)
    assert restarted.state()["plan"]["planner_draft_id"] == plan["planner_draft_id"]
    assert restarted.trace(state["runs"][-1]["id"], "baseline")
    public = json.dumps(restarted.state())
    assert "sk-offline-test-credential" not in public
    call = restarted.state()["planner"]["calls"][0]
    assert call["status"] == "completed" and call["response_id"] == "resp_offline"
    assert "request" not in call and "response" not in call
    with closing(restarted._connect()) as connection:
        full = json.loads(connection.execute("SELECT body_json FROM planner_jobs").fetchone()[0])
        assert full["request"]["instructions"] == planner.INSTRUCTIONS
        assert full["response"]["id"] == "resp_offline"
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("UPDATE planner_jobs SET status='running'")


def test_refusal_failure_audited_without_silent_retry(service, monkeypatch):
    attempts = []

    def transport(*_):
        attempts.append(True)
        return {"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal"}]}]}, None

    monkeypatch.setattr(planner, "request_openai", transport)
    with pytest.raises(CouncilError) as error:
        generate(service, "refused")
    assert error.value.code == "planner_refused"
    assert service.state()["plan"] is None and not service.state()["planner"]["drafts"]
    assert service.state()["planner"]["calls"][0]["status"] == "failed"
    with pytest.raises(CouncilError) as error:
        generate(service, "refused")
    assert error.value.code == "planner_call_exists" and len(attempts) == 1


@pytest.mark.parametrize("changes", [
    {"action": "invented_action"}, {"parameters": {"location_id": "invented"}},
    {"organization_bindings": [{"role": "site_host", "organization_id": "fabricated"}]},
    {"action": "modify_utilities", "parameters": {}},
])
def test_model_output_is_independently_validated(service, monkeypatch, changes):
    monkeypatch.setattr(planner, "request_openai", lambda *_: (response_for(service, **changes), None))
    with pytest.raises(CouncilError):
        generate(service)
    assert not service.state()["planner"]["drafts"] and service.state()["plan"] is None


def test_candidate_is_reviewable_but_not_approvable(service, monkeypatch):
    monkeypatch.setattr(planner, "request_openai", lambda *_: (response_for(service, action="modify_utilities", parameters=None), None))
    generate(service)
    state = adopt(service)
    assert state["plan"]["action"] == "modify_utilities" and state["plan"]["execution_blockers"]


def test_stale_scope_and_edited_command_cannot_claim_model_provenance(service, monkeypatch):
    monkeypatch.setattr(planner, "request_openai", lambda *_: (response_for(service), None))
    generate(service)
    state = service.state()
    draft = state["planner"]["drafts"][0]
    with pytest.raises(CouncilError) as error:
        service.command("/plans", state["revision"], "tampered", {**draft["command"], "seed": 1, "planner_draft_id": draft["id"]})
    assert error.value.code == "planner_draft_changed"
    service.command("/scopes", state["revision"], "new-scope", {**scope_body(state["proposal"]), "reviewer_note": "New scope context"})
    with pytest.raises(CouncilError) as error:
        adopt(service)
    assert error.value.code == "planner_draft_stale"


def test_concurrent_edit_during_generation_is_retained_and_not_overwritten(service, monkeypatch):
    def transport(*_):
        response = response_for(service)
        state = service.state()
        service.command("/proposals", state["revision"], "concurrent", {"markdown": "# New proposal"})
        return response, None

    monkeypatch.setattr(planner, "request_openai", transport)
    with pytest.raises(CouncilError) as error:
        generate(service)
    assert error.value.code == "revision_conflict"
    state = service.state()
    assert state["proposal"]["markdown"] == "# New proposal" and not state["planner"]["drafts"]
    assert state["planner"]["calls"][0]["error"]["code"] == "revision_conflict"


def test_http_preconditions_and_missing_key_never_call_provider(service, monkeypatch):
    monkeypatch.setattr(planner, "request_openai", lambda *_: pytest.fail("must not call OpenAI"))
    body = json.dumps({"population": 200, "seed": 1, "consent_to_send": True}).encode()
    headers = {"content-length": str(len(body)), "x-council-schema": "1",
               "if-match": str(service.state()["revision"]), "idempotency-key": "http"}
    status, _ = _handle_council_request(service, "POST", "/api/council/planner/drafts", {**headers, "x-council-schema": "2"}, body)
    assert status == 400
    monkeypatch.setattr(planner, "configuration", lambda: {"ready": False, "reason": "No API key", "model": "",
                                                         "timeout_seconds": 60, "max_output_tokens": 3000})
    status, result = _handle_council_request(service, "POST", "/api/council/planner/drafts", headers, body)
    assert status == 503 and result["error"]["code"] == "planner_not_configured"
    assert service.state()["planner"]["calls"] == []


def test_env_values_are_never_expanded_and_environment_wins(tmp_path, monkeypatch):
    for name in ("OPENAI_API_KEY", "OPENAI_MODEL", "COUNCIL_OPENAI_ENABLED", "COUNCIL_OPENAI_TIMEOUT_SECONDS", "COUNCIL_OPENAI_MAX_OUTPUT_TOKENS", "VERCEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(planner, "ROOT", tmp_path)
    (tmp_path / ".env").write_text('OPENAI_API_KEY="sk-local-$literal"\nOPENAI_MODEL=test-model\nCOUNCIL_OPENAI_ENABLED=true\n', encoding="utf-8")
    config = planner.configuration()
    assert config["ready"] and config["key"] == "sk-local-$literal"
    monkeypatch.setenv("OPENAI_API_KEY", "")
    assert not planner.configuration()["ready"]
    monkeypatch.setenv("OPENAI_API_KEY", "sk-environment")
    monkeypatch.setenv("VERCEL", "1")
    assert not planner.configuration()["ready"]


@pytest.mark.parametrize("provider_status,error_code", [(401, "planner_authentication"), (429, "planner_rate_limited"), (500, "planner_provider_error")])
def test_provider_http_errors_do_not_echo_credentials(monkeypatch, provider_status, error_code):
    class Opener:
        def open(self, req, timeout):
            assert req.full_url == planner.API_URL and timeout == 60
            raise HTTPError(req.full_url, provider_status, "secret-provider-message", {}, BytesIO(b"sk-private"))

    monkeypatch.setattr(planner, "build_opener", lambda *_: Opener())
    with pytest.raises(CouncilError) as error:
        planner.request_openai({"key": "sk-private", "timeout_seconds": 60}, {"model": "offline"})
    assert error.value.code == error_code
    assert "sk-private" not in error.value.message and "secret-provider-message" not in error.value.message


def test_transport_failure_is_audited_without_retry(service, monkeypatch):
    class Opener:
        def open(self, *_args, **_kwargs):
            raise URLError("private connection details")

    monkeypatch.setattr(planner, "build_opener", lambda *_: Opener())
    with pytest.raises(CouncilError) as error:
        generate(service)
    assert error.value.code == "planner_timeout"
    assert "private" not in error.value.message
    assert service.state()["planner"]["calls"][0]["error"]["code"] == "planner_timeout"


@pytest.mark.parametrize("action,target", [("expand_facility", 24), ("reduce_or_close_service", 0)])
def test_generated_capacity_actions_use_live_catalog(service, monkeypatch, action, target):
    base = plan_body(service.state(), 20_000)["parameters"]
    monkeypatch.setattr(planner, "request_openai", lambda *_: (response_for(service, action=action,
        parameters={"base_site": base, "effective_second": 12_000, "target_capacity": target}), None))
    generate(service)
    state = adopt(service)
    assert state["plan"]["action"] == action
    assert state["plan"]["parameters"]["target_capacity"] == target
