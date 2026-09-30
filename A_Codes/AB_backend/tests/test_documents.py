"""Document Centre tests (BRD §27–§40; acceptance criteria DOC-01..DOC-20)."""
import csv
import io
import zipfile

import pytest

from app.rules import document_rules
from tests.conftest import ADMIN, AUDITOR, EXECUTIVE, VALIDATOR, login, make_docx

PDF = "application/pdf"
KEYWORDS = document_rules.parse_keywords([
    "Terms of Reference=terms of reference|tor", "Model Development Document=model development|mdd",
    "Validation Report=validation report|validation", "Monitoring Plan=monitoring plan",
    "Monitoring Report=monitoring report|monitoring", "Model Approval/MRC Paper=mrc|approval",
])


# --- rules -------------------------------------------------------------------------------------

@pytest.mark.parametrize(("name", "folders", "expected", "source"), [
    ("TOR.pdf", ["M-0012", "Governance"], "Terms of Reference", "filename"),
    ("Validation_Report_2026.pdf", [], "Validation Report", "filename"),
    ("MonitoringPlan.pdf", [], "Monitoring Plan", "filename"),
    ("Monitoring_Report_2026_Q2.pdf", [], "Monitoring Report", "filename"),
    ("q2_results.pdf", ["M-0012", "Monitoring", "2026_Q2"], "Monitoring Report", "folder"),
    ("Storage.pdf", [], "Other", "none"),  # 'tor' inside a word is not a match
])
def test_classification(name, folders, expected, source):
    guess = document_rules.classify_type(name, folders, KEYWORDS)
    assert (guess.document_type, guess.source) == (expected, source)


def test_model_detection_and_versions():
    assert document_rules.detect_model_id(["Credit_Risk", "M-0012", "Validation"], "VR.pdf") == ("M-0012", "folder")
    assert document_rules.detect_model_id([], "M0042_MDD.pdf") == ("M-0042", "filename")
    assert document_rules.parse_version("Validation_Report_v2.1.pdf") == "2.1"
    assert document_rules.parse_version("MDD v3.pdf") == "3.0"
    assert document_rules.title_from_file("Validation_Report_v2.1.pdf") == "Validation Report"
    assert document_rules.next_version(["1.0", "1.1"]) == "1.2"
    assert document_rules.next_version(["1.9", "1.10"]) == "1.11"


def test_required_types_by_phase():
    phases = ["Initiation", "Development", "Validation", "Implementation", "Monitoring", "Reg/Audit", "Retirement"]
    args = (phases, ["ToR"], ["ToR", "MDD"], ["ToR", "MDD", "VR"])
    assert document_rules.required_types("Initiation", *args) == []
    assert document_rules.required_types("Validation", *args) == ["ToR", "MDD"]
    assert document_rules.required_types("Monitoring", *args) == ["ToR", "MDD", "VR"]
    c = document_rules.completeness(["ToR", "MDD", "VR"], {"ToR", "Other"})
    assert (c.missing, c.score) == (["MDD", "VR"], 33.3)


# --- single upload ---------------------------------------------------------------------------------

def _single(client, headers, name, data, **form):
    form = {"model_id": "M-0012", "document_type": "Validation Report", **form}
    return client.post("/api/documents", headers=headers, files={"file": (name, data, PDF)}, data=form)


def test_doc_01_17_single_pdf_upload_and_download(loaded_client, make_pdf):
    h = login(loaded_client, *ADMIN)
    data = make_pdf(["Validation Report", "M-0012"])
    resp = _single(loaded_client, h, "Validation_Report_2026.pdf", data)
    assert resp.status_code == 201, resp.text
    doc = resp.json()
    assert doc["document_id"] == "D-000001" and doc["current_version"] == "1.0" and doc["title"] == "Validation Report 2026"
    v = doc["versions"][0]
    assert len(v["checksum"]) == 64 and v["uploaded_by"] == "U-001" and v["mime_type"] == PDF
    got = loaded_client.get(f"/api/documents/{doc['document_id']}/versions/1.0/download", headers=login(loaded_client, *AUDITOR))
    assert got.status_code == 200 and got.content == data
    events = loaded_client.get("/api/audit", headers=h, params={"document_id": doc["document_id"]}).json()
    assert [e["action"] for e in events] == ["upload"] and events[0]["model_id"] == "M-0012"


def test_doc_02_docx_upload_by_assigned_validator_only(loaded_client):
    v = login(loaded_client, *VALIDATOR)  # U-014 validates M-0012
    ok = _single(loaded_client, v, "MDD.docx", make_docx("Model development document"),
                 document_type="Model Development Document")
    assert ok.status_code == 201, ok.text
    assert ok.json()["versions"][0]["file_type"] == "docx"
    other = _single(loaded_client, v, "MDD.docx", make_docx("other"), model_id="M-0042",
                    document_type="Model Development Document")
    assert other.status_code == 403
    assert _single(loaded_client, login(loaded_client, *EXECUTIVE), "x.docx", make_docx("x")).status_code == 403


@pytest.mark.parametrize(("name", "data", "message"), [
    ("tool.exe", b"MZ\x90\x00", "not accepted"),
    ("fake.pdf", b"hello world", "not a PDF"),
    ("fake.docx", b"%PDF-1.4 not a docx", "not an Office document"),
])
def test_file_validation(loaded_client, name, data, message):
    resp = _single(loaded_client, login(loaded_client, *ADMIN), name, data)
    assert resp.status_code == 422 and message in resp.json()["detail"]


def test_oversized_document_rejected(loaded_client):
    big = b"%PDF-1.4\n" + b"0" * (10 * 1024 * 1024 + 1)
    resp = _single(loaded_client, login(loaded_client, *ADMIN), "big.pdf", big)
    assert resp.status_code == 422 and "limit is 10 MB" in resp.json()["detail"]


def test_doc_08_exact_duplicate_and_versioning(loaded_client, make_pdf):
    h = login(loaded_client, *ADMIN)
    data = make_pdf(["TOR v1"])
    first = _single(loaded_client, h, "TOR.pdf", data, document_type="Terms of Reference").json()
    dup = _single(loaded_client, h, "TOR_copy.pdf", data, document_type="Terms of Reference")
    assert dup.status_code == 409 and "SHA-256 checksum" in dup.json()["detail"]
    # explicit new version of the same bytes is allowed
    again = _single(loaded_client, h, "TOR.pdf", data, document_type="Terms of Reference",
                    new_version_of=first["document_id"], change_reason="Re-issued")
    assert again.status_code == 201 and again.json()["current_version"] == "1.1"
    # a changed file with the same title becomes the next version automatically; explicit v2.0 honoured
    v2 = _single(loaded_client, h, "TOR_v2.0.pdf", make_pdf(["TOR v2"]), document_type="Terms of Reference",
                 version="2.0")
    assert v2.json()["document_id"] == first["document_id"]
    assert [v["version"] for v in v2.json()["versions"]] == ["2.0", "1.1", "1.0"]
    older = _single(loaded_client, h, "TOR.pdf", make_pdf(["TOR v1.5"]), document_type="Terms of Reference",
                    version="1.5")
    assert older.status_code == 422 and "older than the current version" in older.json()["detail"]
    for version in ("1.0", "1.1", "2.0"):  # DOC-17: every version stays downloadable
        assert loaded_client.get(f"/api/documents/{first['document_id']}/versions/{version}/download",
                                 headers=h).status_code == 200


# --- batch, folder and ZIP --------------------------------------------------------------------------

def _batch(client, headers, files, source="folder"):
    multipart = [("files", (p.split("/")[-1], d, "application/octet-stream")) for p, d in files]
    data = {"paths": [p for p, _ in files], "source": source}
    return client.post("/api/documents/batches", headers=headers, files=multipart, data=data)


def _folder_upload(make_pdf):
    root = "Model_Governance/Credit_Risk"
    return [
        (f"{root}/M-0012/Governance/TOR.pdf", make_pdf(["TOR M-0012"])),
        (f"{root}/M-0012/Validation/Validation_Report_2026.pdf", make_pdf(["VR M-0012"])),
        (f"{root}/M-0015/Monitoring/2026_Q2/Q2_results.pdf", make_pdf(["Monitoring M-0015"])),
        ("Misc/notes.pdf", make_pdf(["notes"])),
        (f"{root}/M-0012/Governance/broken.pdf", b"not really a pdf"),
    ]


def test_doc_03_04_06_folder_upload_review_and_confirm(loaded_client, make_pdf):
    h = login(loaded_client, *ADMIN)
    resp = _batch(loaded_client, h, _folder_upload(make_pdf))
    assert resp.status_code == 201, resp.text
    b = resp.json()
    assert b["batch_id"].startswith("B-20260930-") and b["batch_type"] == "documents" and b["status"] == "Ready"
    items = {i["relative_path"].split("/")[-1]: i for i in b["items"]}
    assert (items["TOR.pdf"]["model_id"], items["TOR.pdf"]["document_type"]) == ("M-0012", "Terms of Reference")
    assert items["Validation_Report_2026.pdf"]["document_type"] == "Validation Report"
    q2 = items["Q2_results.pdf"]
    assert (q2["model_id"], q2["document_type"], q2["type_source"]) == ("M-0015", "Monitoring Report", "folder")
    assert items["notes.pdf"]["status"] == "Needs mapping"
    assert items["broken.pdf"]["status"] == "Invalid" and "not a PDF" in items["broken.pdf"]["error"]
    assert all(len(i["checksum"]) == 64 for i in b["items"])  # DOC-07
    # nothing stored before Confirm
    assert loaded_client.get("/api/documents", headers=h).json() == []

    # DOC-13/15: user maps the unmatched file and overrides a classification
    fix = loaded_client.patch(f"/api/documents/batches/{b['batch_id']}/items", headers=h, json={
        "item_ids": [items["notes.pdf"]["item_id"]], "model_id": "M-0012", "document_type": "Other"})
    assert {i["file_name"]: i["status"] for i in fix.json()["items"]}["notes.pdf"] == "Ready"

    done = loaded_client.post(f"/api/documents/batches/{b['batch_id']}/confirm", headers=h).json()
    assert done["status"] == "Partially Completed"  # DOC-10: the invalid file did not stop the others
    assert done["successful_records"] == 4 and done["failed_records"] == 1

    docs = {d["file_name"]: d for d in loaded_client.get("/api/documents", headers=h).json()}
    assert docs["TOR.pdf"]["folder_path"] == "Model_Governance/Credit_Risk/M-0012/Governance"  # DOC-18
    folders = {f["relative_path"]: f for f in loaded_client.get("/api/documents/folders", headers=h).json()}
    assert folders["Model_Governance/Credit_Risk/M-0012"]["model_id"] == "M-0012"  # DOC-06
    assert folders["Model_Governance/Credit_Risk/M-0012/Governance"]["parent_folder_id"] == \
        folders["Model_Governance/Credit_Risk/M-0012"]["folder_id"]

    # DOC-19: lineage from document to batch, path and uploader
    detail = loaded_client.get(f"/api/documents/{docs['TOR.pdf']['document_id']}", headers=h).json()
    v = detail["versions"][0]
    assert (v["import_batch_id"], v["relative_path"], v["uploaded_by"]) == (
        b["batch_id"], "Model_Governance/Credit_Risk/M-0012/Governance/TOR.pdf", "U-001")

    report = loaded_client.get(f"/api/documents/batches/{b['batch_id']}/error-report", headers=h)
    rows = list(csv.reader(io.StringIO(report.content.decode("utf-8-sig"))))
    assert rows[1][0].endswith("broken.pdf") and rows[1][1] == "Invalid"  # DOC-12


def test_doc_05_zip_upload_and_safety(loaded_client, make_pdf):
    h = login(loaded_client, *ADMIN)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path, data in _folder_upload(make_pdf)[:3]:
            z.writestr(path, data)
        z.writestr("__MACOSX/._TOR.pdf", b"junk")
    b = _batch(loaded_client, h, [("evidence.zip", buf.getvalue())], source="batch").json()
    assert b["source"] == "zip" and len(b["items"]) == 3
    assert {i["relative_path"] for i in b["items"]} == {p for p, _ in _folder_upload(make_pdf)[:3]}

    evil = io.BytesIO()
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("../../etc/passwd.pdf", make_pdf(["x"]))
    resp = _batch(loaded_client, h, [("evil.zip", evil.getvalue())])
    assert resp.status_code == 422 and "unsafe path" in resp.json()["detail"]

    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("big.pdf", b"%PDF-" + b"\0" * (5 * 1024 * 1024))
    resp = _batch(loaded_client, h, [("bomb.zip", bomb.getvalue())])
    assert resp.status_code == 422 and "zip bomb" in resp.json()["detail"]


def test_manifest_overrides_heuristics(loaded_client, make_pdf):
    h = login(loaded_client, *ADMIN)
    manifest = "relative_path,model_id,document_type,version,effective_date\nMisc/file1.pdf,M-0015,Backtesting Report,1.2,2026-06-30\n"
    b = _batch(loaded_client, h, [("Misc/file1.pdf", make_pdf(["bt"])), ("manifest.csv", manifest.encode())]).json()
    item = b["items"][0]
    assert b["manifest_files"] == ["manifest.csv"] and len(b["items"]) == 1
    assert (item["model_id"], item["document_type"], item["version"], item["type_source"]) == (
        "M-0015", "Backtesting Report", "1.2", "manifest")


def test_duplicates_in_batch_and_against_register(loaded_client, make_pdf):
    h = login(loaded_client, *ADMIN)
    data = make_pdf(["same"])
    stored = _single(loaded_client, h, "TOR.pdf", data, document_type="Terms of Reference").json()
    b = _batch(loaded_client, h, [("M-0042/TOR.pdf", make_pdf(["other"])), ("M-0042/TOR_copy.pdf", make_pdf(["other"])),
                                  ("M-0012/TOR.pdf", data)]).json()
    by = {i["relative_path"]: i for i in b["items"]}
    assert by["M-0042/TOR_copy.pdf"]["duplicate_kind"] == "in_batch" and by["M-0042/TOR_copy.pdf"]["status"] == "Skipped"
    exact = by["M-0012/TOR.pdf"]
    assert exact["duplicate_kind"] == "exact" and exact["duplicate_of"].startswith(stored["document_id"])
    assert exact["status"] == "Skipped"  # BRD §35: exact re-upload is not stored unless asked


def test_doc_20_completeness_and_documentation_score(loaded_client, make_pdf):
    h = login(loaded_client, *ADMIN)
    c = loaded_client.get("/api/documents/completeness", headers=h, params={"model_id": "M-0012"}).json()[0]
    assert c["present"] == [] and len(c["missing"]) == 5
    _single(loaded_client, h, "TOR.pdf", make_pdf(["tor"]), document_type="Terms of Reference")
    _single(loaded_client, h, "VR.pdf", make_pdf(["vr"]), document_type="Validation Report")
    c = loaded_client.get("/api/documents/completeness", headers=h, params={"model_id": "M-0012"}).json()[0]
    assert c["present"] == ["Terms of Reference", "Validation Report"] and c["score"] == 40.0
    comps = {x["key"]: x for x in loaded_client.get("/api/models/M-0012", headers=h).json()["score"]["components"]}
    assert comps["documentation"]["score"] == "40.0"
    assert "2 of 5 required documents on file." == comps["documentation"]["explanation"]


def test_archive_legal_hold_and_links(loaded_client, make_pdf):
    h = login(loaded_client, *ADMIN)
    d = _single(loaded_client, h, "VR.pdf", make_pdf(["vr"])).json()
    validation = loaded_client.get("/api/validations", headers=h, params={"model_id": "M-0012"}).json()[0]
    link = loaded_client.post(f"/api/documents/{d['document_id']}/links", headers=h,
                              json={"entity_type": "validation", "entity_id": validation["validation_id"]})
    assert link.status_code == 201
    other = loaded_client.get("/api/validations", headers=h, params={"model_id": "M-0042"}).json()[0]
    wrong = loaded_client.post(f"/api/documents/{d['document_id']}/links", headers=h,
                               json={"entity_type": "validation", "entity_id": other["validation_id"]})
    assert wrong.status_code == 422

    hold = loaded_client.post(f"/api/documents/{d['document_id']}/legal-hold", headers=h,
                              json={"hold": True, "reason": "Regulatory review"})
    assert hold.json()["legal_hold"] is True
    assert loaded_client.post(f"/api/documents/{d['document_id']}/archive", headers=h,
                              json={"reason": "Superseded"}).status_code == 409
    loaded_client.post(f"/api/documents/{d['document_id']}/legal-hold", headers=h, json={"hold": False, "reason": "Closed"})
    assert loaded_client.post(f"/api/documents/{d['document_id']}/archive", headers=login(loaded_client, *AUDITOR),
                              json={"reason": "x"}).status_code == 403
    archived = loaded_client.post(f"/api/documents/{d['document_id']}/archive", headers=h, json={"reason": "Superseded"})
    assert archived.json()["status"] == "Archived"
    # archived documents stay retrievable but drop out of the active register
    assert loaded_client.get("/api/documents", headers=h).json() == []
    assert loaded_client.get(f"/api/documents/{d['document_id']}/versions/1.0/download", headers=h).status_code == 200


def test_document_manifest_templates_are_document_channel(loaded_client):
    h = login(loaded_client, *ADMIN)
    t = {x["template_id"]: x for x in loaded_client.get("/api/imports/templates", headers=h).json()}
    assert t["T17"]["available"] and t["T17"]["channel"] == "documents"
    assert loaded_client.get("/api/imports/templates/T17/blank", headers=h).status_code == 200
