"""Model inventory, tiering, lifecycle and governance-record API tests against the sample data."""
from tests.conftest import ADMIN, AUDITOR, EXECUTIVE, MRC, VALIDATOR, login

NEW_MODEL = {
    "model_id": "M-0400", "model_name": "SME Probability of Default", "model_type": "Credit Risk",
    "model_subtype": "PD", "purpose": "12-month PD for small business lending.", "business_line": "Business Banking",
    "owner_id": "U-003", "developer_id": "U-021", "validator_id": "U-016", "lifecycle_phase": "Validation",
    "version": "v1.0", "q_materiality": 3, "q_complexity": 2, "q_reliance": 3, "q_regulatory_use": 3,
}


def _model(client, headers, model_id):
    resp = client.get(f"/api/models/{model_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_sample_portfolio_loads(loaded_client):
    rows = loaded_client.get("/api/models", headers=login(loaded_client, *EXECUTIVE)).json()
    assert len(rows) == 79
    m12 = next(r for r in rows if r["model_id"] == "M-0012")
    assert m12["effective_tier"] == "High"
    assert m12["state"]["days_to_due"] == 198 and m12["state"]["revalidation_status"] == "Scheduled"
    m42 = next(r for r in rows if r["model_id"] == "M-0042")
    assert m42["state"]["revalidation_status"] == "Overdue" and m42["state"]["displayed_column"] == "Revalidation"


def test_filters_combine(loaded_client):
    h = login(loaded_client, *EXECUTIVE)
    rows = loaded_client.get("/api/models", headers=h,
                             params={"model_type": "CCAR/Stress Testing", "tier": "High"}).json()
    assert rows and all(r["model_type"] == "CCAR/Stress Testing" and r["effective_tier"] == "High" for r in rows)
    overdue = loaded_client.get("/api/models", headers=h, params={"revalidation_status": "Overdue"}).json()
    assert {"M-0015", "M-0042"} <= {r["model_id"] for r in overdue}


def test_tc_inv_02_1_admin_creates_model_with_calculated_tier(loaded_client):
    h = login(loaded_client, *ADMIN)
    resp = loaded_client.post("/api/models", headers=h, json=NEW_MODEL)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["tier_score"] == 11 and body["calculated_tier"] == "High" and body["effective_tier"] == "High"
    m = _model(loaded_client, h, "M-0400")
    assert m["phase_history"][0]["to_phase"] == "Validation"
    assert m["versions"][0]["version"] == "v1.0"
    events = loaded_client.get("/api/audit", headers=h, params={"model_id": "M-0400"}).json()
    assert [e["action"] for e in events] == ["create"]


def test_tc_inv_03_1_sod_blocks_create(loaded_client):
    resp = loaded_client.post("/api/models", headers=login(loaded_client, *ADMIN),
                              json={**NEW_MODEL, "validator_id": "U-003"})
    assert resp.status_code == 422
    assert "Validator U-003 cannot validate model M-0400 because U-003 is also the model owner." in resp.json()["detail"]


def test_phase_requirements_enforced_on_create(loaded_client):
    resp = loaded_client.post("/api/models", headers=login(loaded_client, *ADMIN),
                              json={**NEW_MODEL, "lifecycle_phase": "Monitoring"})
    assert resp.status_code == 422
    fields = {e["field"] for e in resp.json()["errors"]}
    assert {"go_live_date", "revalidation_frequency", "last_validation_date"} <= fields


def test_unknown_owner_is_rejected(loaded_client):
    resp = loaded_client.post("/api/models", headers=login(loaded_client, *ADMIN),
                              json={**NEW_MODEL, "owner_id": "U-999"})
    assert resp.status_code == 422 and "User U-999 does not exist." in resp.json()["detail"]


def test_executive_and_auditor_cannot_create_or_edit(loaded_client):
    for who in (EXECUTIVE, AUDITOR):
        assert loaded_client.post("/api/models", headers=login(loaded_client, *who), json=NEW_MODEL).status_code == 403


def test_model_owner_can_only_edit_own_models(loaded_client):
    admin = login(loaded_client, *ADMIN)
    m12 = _model(loaded_client, admin, "M-0012")["model"]
    owner = login(loaded_client, m12["owner_id"], "Model Owner")
    payload = {k: m12[k] for k in NEW_MODEL if k in m12} | {
        k: m12["tiering"][k] for k in ("q_materiality", "q_complexity", "q_reliance", "q_regulatory_use")}
    payload |= {"business_line": "Corporate Banking", "row_version": m12["row_version"],
                "go_live_date": m12["go_live_date"], "revalidation_frequency": m12["revalidation_frequency"],
                "last_validation_date": m12["last_validation_date"], "model_family": None}
    ok = loaded_client.put("/api/models/M-0012", headers=owner, json=payload)
    assert ok.status_code == 200, ok.text
    assert ok.json()["business_line"] == "Corporate Banking"

    m15 = _model(loaded_client, admin, "M-0015")["model"]
    assert m15["owner_id"] != m12["owner_id"]
    resp = loaded_client.put("/api/models/M-0015", headers=owner, json={**payload, "row_version": m15["row_version"]})
    assert resp.status_code == 403


def test_stale_model_update_is_conflict(loaded_client):
    h = login(loaded_client, *ADMIN)
    m = _model(loaded_client, h, "M-0023")["model"]
    body = {"to_phase": "Reg/Audit", "reason": "Supervisory review", "row_version": m["row_version"]}
    assert loaded_client.post("/api/models/M-0023/transition", headers=h, json=body).status_code == 200
    assert loaded_client.post("/api/models/M-0023/transition", headers=h,
                              json={**body, "to_phase": "Monitoring"}).status_code == 409


def test_phase_transition_recorded_with_reason(loaded_client):
    h = login(loaded_client, *ADMIN)
    m = _model(loaded_client, h, "M-0085")["model"]
    resp = loaded_client.post("/api/models/M-0085/transition", headers=h,
                              json={"to_phase": "Validation", "reason": "MDD complete", "row_version": m["row_version"]})
    # Validation phase needs a validator: rule enforced on transition too
    assert resp.status_code == 422 and "validator is required" in resp.json()["detail"]


def test_tc_tir_02_override_keeps_calculated_tier(loaded_client):
    h = login(loaded_client, *ADMIN)
    m = _model(loaded_client, h, "M-0012")["model"]
    resp = loaded_client.post("/api/models/M-0012/tier-override", headers=h,
                              json={"tier": "Medium", "reason": "Exposure run-off", "row_version": m["row_version"]})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["effective_tier"] == "Medium" and body["calculated_tier"] == "High"
    detail = _model(loaded_client, h, "M-0012")
    assert detail["tier_overrides"][0]["previous_tier"] == "High"
    assert detail["model"]["tiering"]["override_reason"] == "Exposure run-off"


def test_tc_tir_02_2_override_requires_reason_and_admin(loaded_client):
    admin = login(loaded_client, *ADMIN)
    m = _model(loaded_client, admin, "M-0012")["model"]
    no_reason = loaded_client.post("/api/models/M-0012/tier-override", headers=admin,
                                   json={"tier": "Low", "reason": " ", "row_version": m["row_version"]})
    assert no_reason.status_code == 422
    owner = login(loaded_client, m["owner_id"], "Model Owner")
    assert loaded_client.post("/api/models/M-0012/tier-override", headers=owner,
                              json={"tier": "Low", "reason": "x", "row_version": m["row_version"]}).status_code == 403


def test_tier_threshold_change_recalculates_models(loaded_client):
    h = login(loaded_client, *ADMIN)
    setting = next(s for s in loaded_client.get("/api/admin/policy", headers=h).json()
                   if s["setting_key"] == "tier_high_min")
    before = loaded_client.get("/api/models", headers=h).json()
    assert any(r["calculated_tier"] == "High" and r["tier_score"] < 12 for r in before)
    resp = loaded_client.put("/api/admin/policy/tier_high_min", headers=h,
                             json={"value": "12", "row_version": setting["row_version"]})
    assert resp.status_code == 200, resp.text
    after = loaded_client.get("/api/models", headers=h).json()
    for r in after:
        assert (r["calculated_tier"] == "High") == (r["tier_score"] >= 12), r["model_id"]
    recalcs = loaded_client.get("/api/audit", headers=h, params={"action": "recalculate"}).json()
    assert recalcs and all(e["reason"] == "Tier thresholds changed" for e in recalcs)


def test_invalid_tier_thresholds_rejected(loaded_client):
    h = login(loaded_client, *ADMIN)
    s = next(s for s in loaded_client.get("/api/admin/policy", headers=h).json() if s["setting_key"] == "tier_medium_min")
    resp = loaded_client.put("/api/admin/policy/tier_medium_min", headers=h, json={"value": "11", "row_version": s["row_version"]})
    assert resp.status_code == 422


def test_tier_preview(loaded_client):
    resp = loaded_client.post("/api/models/tier-preview", headers=login(loaded_client, *EXECUTIVE),
                              json={"q_materiality": 2, "q_complexity": 2, "q_reliance": 2, "q_regulatory_use": 1})
    assert resp.json()["tier"] == "Medium" and resp.json()["tier_score"] == 7


def test_tc_inv_05_1_successor_relationship_both_directions(loaded_client):
    h = login(loaded_client, *EXECUTIVE)
    old = _model(loaded_client, h, "M-0003")["relationships"]
    new = _model(loaded_client, h, "M-0012")["relationships"]
    assert {"relationship": "successor", "model_id": "M-0012", "model_name": "Wholesale PD Model"} in old
    assert any(r["relationship"] == "predecessor" and r["model_id"] == "M-0003" for r in new)


def test_legacy_sod_breach_is_visible(loaded_client):
    m = _model(loaded_client, login(loaded_client, *EXECUTIVE), "M-0078")
    assert m["model"]["legacy_sod_exception"] is True
    assert "also the model owner" in m["state"]["sod_breach"]


def test_score_is_explainable_and_retired_not_scored(loaded_client):
    h = login(loaded_client, *EXECUTIVE)
    m12 = _model(loaded_client, h, "M-0012")
    comps = {c["key"]: c for c in m12["score"]["components"]}
    # Phase 4: documentation is scored from documents on file (none in the sample data)
    assert comps["documentation"]["score"] == "0.0"
    assert "Terms of Reference not on file" in comps["documentation"]["missing"]
    assert comps["mrc_compliance"]["score"] == "70.0"  # latest decision Conditional with open conditions
    # 1 open Critical (overdue) + 1 open Medium: 100 − 25 − 10 − 10 = 55
    assert comps["issue_remediation"]["score"] == "55.0"
    assert m12["score"]["overall"] is not None
    retired = _model(loaded_client, h, "M-0003")
    assert retired["score"]["overall"] is None and retired["score"]["reason"] == "Retired models are not scored."


def test_tc_cfg_02_weight_change_changes_score(loaded_client):
    h = login(loaded_client, *ADMIN)
    # M-0012 components: documentation 0 (25), validation currency 100 (25), remediation 55 (20), MRC 70 (15)
    assert _model(loaded_client, h, "M-0012")["score"]["overall"] == "54.7"  # 4650 / 85
    s = next(s for s in loaded_client.get("/api/admin/policy", headers=h).json()
             if s["setting_key"] == "weight_validation_currency")
    loaded_client.put("/api/admin/policy/weight_validation_currency", headers=h,
                      json={"value": "50", "row_version": s["row_version"]})
    assert _model(loaded_client, h, "M-0012")["score"]["overall"] == "65.0"  # 7150 / 110


# --- validations, findings, approvals ------------------------------------------------------

def test_assigned_validator_records_validation_and_updates_currency(loaded_client):
    admin = login(loaded_client, *ADMIN)
    m = _model(loaded_client, admin, "M-0012")["model"]
    assert m["validator_id"] == "U-014"
    v = login(loaded_client, *VALIDATOR)
    resp = loaded_client.post("/api/validations", headers=v, json={
        "model_id": "M-0012", "validation_type": "Periodic", "validator_id": "U-014",
        "start_date": "2026-08-01", "completion_date": "2026-09-15", "outcome": "Approved"})
    assert resp.status_code == 201, resp.text
    after = _model(loaded_client, admin, "M-0012")["model"]
    assert after["last_validation_date"] == "2026-09-15"

    # not assigned to M-0042
    other = loaded_client.post("/api/validations", headers=v, json={
        "model_id": "M-0042", "validation_type": "Periodic", "validator_id": "U-014",
        "start_date": "2026-08-01", "outcome": "In Progress"})
    assert other.status_code == 403


def test_validation_sod_enforced(loaded_client):
    admin = login(loaded_client, *ADMIN)
    m = _model(loaded_client, admin, "M-0012")["model"]
    resp = loaded_client.post("/api/validations", headers=admin, json={
        "model_id": "M-0012", "validation_type": "Targeted", "validator_id": m["owner_id"],
        "start_date": "2026-08-01", "outcome": "In Progress"})
    assert resp.status_code == 422 and "also the model owner" in resp.json()["detail"]


def test_findings_ageing_and_overdue_filter(loaded_client):
    h = login(loaded_client, *EXECUTIVE)
    overdue = loaded_client.get("/api/findings", headers=h, params={"model_id": "M-0012", "overdue_only": True}).json()
    assert [f["title"] for f in overdue] == ["CRE obligor data gap"]
    assert overdue[0]["days_overdue"] == 40


def test_finding_lifecycle_close_and_audit(loaded_client):
    admin = login(loaded_client, *ADMIN)
    m = _model(loaded_client, admin, "M-0012")["model"]
    owner = login(loaded_client, m["owner_id"], "Model Owner")
    created = loaded_client.post("/api/findings", headers=owner, json={
        "model_id": "M-0012", "title": "Override log incomplete", "description": "Manual overrides not logged.",
        "severity": "Low", "category": "Documentation", "due_date": "2026-12-31"})
    assert created.status_code == 201, created.text
    f = created.json()
    assert f["owner_id"] == m["owner_id"] and f["raised_date"] == "2026-09-30" and f["source"] == "Manual"
    closed = loaded_client.patch(f"/api/findings/{f['finding_id']}", headers=owner,
                                 json={"status": "Closed", "row_version": f["row_version"], "reason": "Log fixed"})
    assert closed.status_code == 200, closed.text
    assert closed.json()["closed_date"] == "2026-09-30"
    events = loaded_client.get("/api/audit", headers=admin, params={"entity": "finding", "action": "close"}).json()
    assert any(e["entity_id"] == f["finding_id"] and e["reason"] == "Log fixed" for e in events)


def test_finding_invalid_values_rejected(loaded_client):
    resp = loaded_client.post("/api/findings", headers=login(loaded_client, *ADMIN), json={
        "model_id": "M-0012", "title": "X", "description": "Y", "severity": "Severe", "category": "Data",
        "due_date": "2026-12-31"})
    assert resp.status_code == 422 and "Allowed: Critical, Medium, Low" in resp.json()["detail"]


def test_approvals_mrc_only_and_conditional_rules(loaded_client):
    body = {"model_id": "M-0071", "decision_date": "2026-09-30", "forum": "MRC", "decision_type": "Pre-implementation",
            "decision": "Conditional"}
    assert loaded_client.post("/api/approvals", headers=login(loaded_client, *VALIDATOR), json=body).status_code == 403
    mrc = login(loaded_client, *MRC)
    missing = loaded_client.post("/api/approvals", headers=mrc, json=body)
    assert missing.status_code == 422 and "Conditions are required" in missing.json()["detail"]
    ok = loaded_client.post("/api/approvals", headers=mrc, json={
        **body, "conditions": "Close F-0012", "condition_due_date": "2026-12-31", "condition_status": "Open"})
    assert ok.status_code == 201, ok.text
    a = ok.json()
    met = loaded_client.patch(f"/api/approvals/{a['approval_id']}", headers=mrc,
                              json={"condition_status": "Met", "row_version": a["row_version"]})
    assert met.status_code == 200 and met.json()["condition_status"] == "Met"


def test_model_360_panels(loaded_client):
    m = _model(loaded_client, login(loaded_client, *EXECUTIVE), "M-0071")
    assert len(m["approvals"]) == 3 and m["approvals"][0]["decision_type"] == "Pre-implementation"
    assert len(m["findings"]) == 4 and m["validations"]
    assert m["user_names"][m["model"]["owner_id"]] == "Fiona Johnson"
