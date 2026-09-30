"""Command Center tie-out tests: every tile and chart must equal what its drill-down list shows (REQ-CC-01..04)."""
from decimal import Decimal

from tests.conftest import ADMIN, EXECUTIVE, login


def _get(client, h, path, **params):
    resp = client.get(path, headers=h, params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_tiles_tie_out_to_lists(loaded_client):
    h = login(loaded_client, *EXECUTIVE)
    d = _get(loaded_client, h, "/api/dashboard/summary")
    t = d["tiles"]
    models = _get(loaded_client, h, "/api/models")
    assert t["total_models"] == len(models) == 79
    assert t["high_tier"] == len(_get(loaded_client, h, "/api/models", tier="High"))
    assert t["revalidation_queue"] == len(_get(loaded_client, h, "/api/models", column="Revalidation"))
    assert t["revalidation_overdue"] == len(_get(loaded_client, h, "/api/models", revalidation_status="Overdue"))
    assert t["in_production"] == len(_get(loaded_client, h, "/api/models", flag="in_production"))
    assert t["sod_breaches"] == len(_get(loaded_client, h, "/api/models", flag="sod_breach")) == 1  # M-0078
    assert t["models_with_document_gaps"] == len(_get(loaded_client, h, "/api/models", flag="doc_gaps")) == \
        len(_get(loaded_client, h, "/api/documents/completeness", missing_only=True))
    assert t["models_with_open_conditions"] == len(_get(loaded_client, h, "/api/models", flag="open_conditions"))

    findings = _get(loaded_client, h, "/api/findings")
    open_statuses = {"Open", "In Progress", "Deferred"}
    assert t["open_findings"] == sum(1 for f in findings if f["status"] in open_statuses)
    overdue = _get(loaded_client, h, "/api/findings", overdue_only=True)
    assert t["overdue_findings"] == len(overdue)
    assert t["critical_overdue_findings"] == sum(1 for f in overdue if f["severity"] == "Critical")

    scores = [Decimal(m["state"]["score"]) for m in models if m["state"]["score"] is not None]
    assert t["scored_models"] == len(scores)
    assert t["portfolio_score"] == float(round(sum(scores) / len(scores), 1))


def test_distributions_sum_and_match_filters(loaded_client):
    h = login(loaded_client, *EXECUTIVE)
    d = _get(loaded_client, h, "/api/dashboard/summary")
    total = d["tiles"]["total_models"]
    for key in ("tier", "model_type", "stage", "business_line"):
        assert sum(x["count"] for x in d["distributions"][key]) == total, key
        assert abs(sum(x["pct"] for x in d["distributions"][key]) - 100) <= 1, key
    for x in d["distributions"]["stage"]:
        assert x["count"] == len(_get(loaded_client, h, "/api/models", column=x["key"])), x
    for x in d["distributions"]["model_type"]:
        assert x["count"] == len(_get(loaded_client, h, "/api/models", model_type=x["key"])), x
    sev = {x["key"]: x["count"] for x in d["distributions"]["open_findings_by_severity"]}
    assert sum(sev.values()) == d["tiles"]["open_findings"]
    bands = {x["key"]: x["count"] for x in d["distributions"]["score_band"]}
    assert bands["below_60"] == len(_get(loaded_client, h, "/api/models", flag="scored_below_60"))
    assert sum(bands.values()) == d["tiles"]["scored_models"]


def test_revalidation_timeline_is_the_revalidation_column(loaded_client):
    h = login(loaded_client, *EXECUTIVE)
    d = _get(loaded_client, h, "/api/dashboard/summary")
    column = {m["model_id"] for m in _get(loaded_client, h, "/api/models", column="Revalidation")}
    timeline = d["revalidation_timeline"]
    assert {x["model_id"] for x in timeline} == column
    days = [x["days_to_due"] for x in timeline]
    assert days == sorted(days)  # most urgent first
    assert timeline[0]["model_id"] == "M-0042" and timeline[0]["status"] == "Overdue"


def test_insights_are_generated_from_data(loaded_client):
    h = login(loaded_client, *EXECUTIVE)
    d = _get(loaded_client, h, "/api/dashboard/summary")
    rules = d["insight_counts_by_rule"]
    assert rules["sod_breach"] == 1 and rules["revalidation_overdue"] == d["tiles"]["revalidation_overdue"]
    assert rules["critical_finding_overdue"] == d["tiles"]["critical_overdue_findings"]
    shown = d["insights"]
    assert shown[0]["rule"] == "sod_breach" and shown[0]["model_id"] == "M-0078"
    assert [i["severity"] for i in shown] == sorted((i["severity"] for i in shown),
                                                    key=["Critical", "High", "Medium", "Low"].index)
    models = {m["model_id"] for m in _get(loaded_client, h, "/api/models")}
    assert all(i["model_id"] in models and i["link"] == f"/models/{i['model_id']}" for i in shown)
    assert len(shown) <= 10 and d["insight_count"] >= len(shown)


def test_insight_disappears_when_resolved(loaded_client):
    """TC-CC-04-2: close the overdue Critical finding and its insight goes away."""
    admin = login(loaded_client, *ADMIN)
    before = _get(loaded_client, admin, "/api/dashboard/summary")["insight_counts_by_rule"]["critical_finding_overdue"]
    f = next(x for x in _get(loaded_client, admin, "/api/findings", model_id="M-0012", overdue_only=True)
             if x["severity"] == "Critical")
    loaded_client.patch(f"/api/findings/{f['finding_id']}", headers=admin,
                        json={"status": "Closed", "row_version": f["row_version"], "reason": "Remediated"})
    after = _get(loaded_client, admin, "/api/dashboard/summary")["insight_counts_by_rule"]["critical_finding_overdue"]
    assert after == before - 1


def test_unknown_flag_rejected(loaded_client):
    resp = loaded_client.get("/api/models", headers=login(loaded_client, *EXECUTIVE), params={"flag": "everything"})
    assert resp.status_code == 422 and "Allowed:" in resp.json()["detail"]
