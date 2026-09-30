from decimal import Decimal

import pytest

from app.rules.policy_values import PolicyValueError, normalise_policy_value, parse_policy_value
from tests.conftest import ADMIN, AUDITOR, EXECUTIVE, login


# --- rules --------------------------------------------------------------------------

@pytest.mark.parametrize(("value", "value_type", "expected"), [
    ("60", "integer", 60),
    ("98", "percent", Decimal("98")),
    ("0.65", "decimal", Decimal("0.65")),
    ("ToR; MDD", "list", ["ToR", "MDD"]),
    ("Y", "boolean", True),
])
def test_parse_valid_values(value, value_type, expected):
    assert parse_policy_value(value, value_type) == expected


@pytest.mark.parametrize(("value", "value_type", "message"), [
    ("sixty", "integer", "not a whole number"),
    ("101", "percent", "outside 0–100"),
    ("", "text", "cannot be blank"),
    (" ; ", "list", "at least one item"),
    ("maybe", "boolean", "not a yes/no value"),
])
def test_parse_invalid_values(value, value_type, message):
    with pytest.raises(PolicyValueError, match=message):
        parse_policy_value(value, value_type)


def test_list_values_are_normalised():
    assert normalise_policy_value("ToR;MDD ;  Validation Report", "list") == "ToR; MDD; Validation Report"


# --- API ----------------------------------------------------------------------------

def _setting(client, headers, key):
    return next(s for s in client.get("/api/admin/policy", headers=headers).json() if s["setting_key"] == key)


def test_bootstrap_loaded_policy(client):
    settings = client.get("/api/admin/policy", headers=login(client, *EXECUTIVE)).json()
    keys = {s["setting_key"] for s in settings}
    assert {"tier_high_min", "weight_monitoring", "document_types"} <= keys


def test_admin_updates_policy_with_audit_before_and_after(client):
    admin = login(client, *ADMIN)
    current = _setting(client, admin, "reval_lead_days")
    resp = client.put("/api/admin/policy/reval_lead_days", headers=admin,
                      json={"value": "90", "row_version": current["row_version"], "reason": "Policy review"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["value"] == "90" and body["updated_by"] == "U-001"
    assert body["row_version"] == current["row_version"] + 1

    events = client.get("/api/audit", headers=admin, params={"entity": "policy_setting", "action": "update"}).json()
    event = next(e for e in events if e["entity_id"] == "reval_lead_days")
    assert event["before_json"]["value"] == "60"
    assert event["after_json"]["value"] == "90"
    assert event["reason"] == "Policy review"


def test_invalid_policy_value_is_rejected_with_message(client):
    admin = login(client, *ADMIN)
    current = _setting(client, admin, "reval_lead_days")
    resp = client.put("/api/admin/policy/reval_lead_days", headers=admin,
                      json={"value": "sixty", "row_version": current["row_version"]})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Invalid value for 'reval_lead_days': 'sixty' is not a whole number."


def test_stale_policy_update_is_a_conflict(client):
    admin = login(client, *ADMIN)
    current = _setting(client, admin, "due_soon_days")
    ok = client.put("/api/admin/policy/due_soon_days", headers=admin,
                    json={"value": "45", "row_version": current["row_version"]})
    assert ok.status_code == 200
    stale = client.put("/api/admin/policy/due_soon_days", headers=admin,
                       json={"value": "20", "row_version": current["row_version"]})
    assert stale.status_code == 409


def test_unknown_policy_key_is_404(client):
    resp = client.put("/api/admin/policy/no_such_key", headers=login(client, *ADMIN),
                      json={"value": "1", "row_version": 1})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Policy setting 'no_such_key' does not exist."


def test_audit_trail_has_no_write_routes(client):
    admin = login(client, *ADMIN)
    event_id = client.get("/api/audit", headers=admin).json()[0]["event_id"]
    for method in ("post", "put", "patch", "delete"):
        resp = getattr(client, method)(f"/api/audit/{event_id}", headers=admin)
        assert resp.status_code in (404, 405), method


def test_audit_read_is_restricted(client):
    assert client.get("/api/audit", headers=login(client, *AUDITOR)).status_code == 200
    assert client.get("/api/audit", headers=login(client, *EXECUTIVE)).status_code == 403


def test_bootstrap_is_idempotent(db_session):
    from sqlalchemy import func, select

    from app.config import get_settings
    from app.models import AuditEvent
    from app.services.bootstrap_service import load_bootstrap

    with db_session() as s:
        before = s.scalar(select(func.count()).select_from(AuditEvent))
        load_bootstrap(s, get_settings().bootstrap_dir)
        after = s.scalar(select(func.count()).select_from(AuditEvent))
    assert after == before
