from app.auth.roles import ROLE_PERMISSIONS, Permission, Role, has_permission
from tests.conftest import ADMIN, AUDITOR, EXECUTIVE, VALIDATOR, login

READ_ONLY_ROLES = (Role.AUDITOR, Role.EXECUTIVE)
WRITE_PERMISSIONS = set(Permission) - {Permission.READ, Permission.AUDIT_READ}


def test_every_role_has_a_permission_set():
    assert set(ROLE_PERMISSIONS) == set(Role)


def test_auditor_and_executive_are_read_only():
    for role in READ_ONLY_ROLES:
        assert not (ROLE_PERMISSIONS[role] & WRITE_PERMISSIONS), role


def test_unknown_role_has_no_permissions():
    assert not has_permission("Superuser", Permission.READ)


def test_login_and_me(client):
    headers = login(client, *VALIDATOR)
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["user_id"] == "U-014"
    assert me["role"] == "Validator"
    assert "document:upload" in me["permissions"]
    assert "policy:edit" not in me["permissions"]


def test_login_with_role_user_does_not_hold_is_refused(client):
    resp = client.post("/api/auth/login", json={"user_id": "U-041", "role": "Admin"})
    assert resp.status_code == 403
    assert "does not hold the role 'Admin'" in resp.json()["detail"]


def test_multi_role_user_can_log_in_as_either_role(client):
    for role in ("MRC Member", "Executive"):
        assert client.get("/api/auth/me", headers=login(client, "U-040", role)).json()["role"] == role


def test_missing_or_bad_token_is_401(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_dev_users_lists_active_users(client):
    users = client.get("/api/auth/dev-users").json()
    assert {"U-001", "U-041"} <= {u["user_id"] for u in users}


def test_auditor_cannot_edit_policy_and_nothing_changes(client):
    before = {s["setting_key"]: s for s in client.get("/api/admin/policy", headers=login(client, *ADMIN)).json()}
    resp = client.put("/api/admin/policy/reval_lead_days", headers=login(client, *AUDITOR),
                      json={"value": "90", "row_version": before["reval_lead_days"]["row_version"]})
    assert resp.status_code == 403
    after = {s["setting_key"]: s for s in client.get("/api/admin/policy", headers=login(client, *ADMIN)).json()}
    assert after["reval_lead_days"]["value"] == "60"


def test_executive_cannot_create_users(client):
    resp = client.post("/api/users", headers=login(client, *EXECUTIVE), json={
        "user_id": "U-900", "full_name": "Test Person", "email": "t.person@demo-bank.example", "roles": ["Validator"],
    })
    assert resp.status_code == 403


def test_admin_creates_user_with_audit_event(client):
    admin = login(client, *ADMIN)
    resp = client.post("/api/users", headers=admin, json={
        "user_id": "U-900", "full_name": "Test Person", "email": "t.person@demo-bank.example",
        "roles": ["Validator", "Model Developer"],
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["roles"] == ["Model Developer", "Validator"]
    events = client.get("/api/audit", headers=admin, params={"entity": "app_user", "action": "create"}).json()
    created = [e for e in events if e["entity_id"] == "U-900"]
    assert len(created) == 1
    assert created[0]["user_id"] == "U-001" and created[0]["role"] == "Admin"


def test_create_user_with_unknown_role_is_rejected(client):
    resp = client.post("/api/users", headers=login(client, *ADMIN), json={
        "user_id": "U-901", "full_name": "Test Person", "email": "t2@demo-bank.example", "roles": ["Superuser"],
    })
    assert resp.status_code == 422
    assert "Unknown role(s): Superuser" in resp.json()["detail"]


def test_deactivated_user_token_stops_working(client, db_session):
    headers = login(client, *VALIDATOR)
    from app.models import AppUser
    with db_session() as s:
        s.get(AppUser, "U-014").active = False
        s.commit()
    assert client.get("/api/auth/me", headers=headers).status_code == 401
