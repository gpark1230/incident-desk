from app.models import UserRole


def test_create_incident_writes_a_created_audit_row(client, make_user, auth_headers):
    make_user("analyst@example.com", role=UserRole.analyst)
    headers = auth_headers("analyst@example.com")

    created = client.post(
        "/incidents", headers=headers, json={"title": "Ransomware alert", "severity": "critical"}
    ).json()

    audit_log = client.get(f"/incidents/{created['id']}/audit-log", headers=headers).json()

    assert len(audit_log) == 1
    assert audit_log[0]["action"] == "created"
    assert "critical" in audit_log[0]["details"]


def test_update_incident_logs_a_readable_diff(client, make_user, auth_headers):
    make_user("analyst2@example.com", role=UserRole.analyst)
    headers = auth_headers("analyst2@example.com")

    created = client.post(
        "/incidents", headers=headers, json={"title": "Phishing email", "severity": "medium"}
    ).json()

    client.patch(f"/incidents/{created['id']}", headers=headers, json={"status": "closed"})

    audit_log = client.get(f"/incidents/{created['id']}/audit-log", headers=headers).json()

    assert len(audit_log) == 2
    assert audit_log[1]["action"] == "updated"
    assert "open -> closed" in audit_log[1]["details"]


def test_noop_update_writes_no_audit_row(client, make_user, auth_headers):
    make_user("analyst3@example.com", role=UserRole.analyst)
    headers = auth_headers("analyst3@example.com")

    created = client.post(
        "/incidents", headers=headers, json={"title": "Phishing email", "severity": "medium"}
    ).json()

    # re-sending the current status is a no-op, should not add a second audit row
    client.patch(f"/incidents/{created['id']}", headers=headers, json={"status": "open"})

    audit_log = client.get(f"/incidents/{created['id']}/audit-log", headers=headers).json()

    assert len(audit_log) == 1


def test_get_nonexistent_incident_404s(client, make_user, auth_headers):
    make_user("viewer@example.com", role=UserRole.viewer)
    headers = auth_headers("viewer@example.com")

    response = client.get("/incidents/999999", headers=headers)

    assert response.status_code == 404


def test_filter_by_severity(client, make_user, auth_headers):
    make_user("analyst4@example.com", role=UserRole.analyst)
    headers = auth_headers("analyst4@example.com")

    client.post("/incidents", headers=headers, json={"title": "A", "severity": "low"})
    client.post("/incidents", headers=headers, json={"title": "B", "severity": "critical"})

    response = client.get("/incidents?severity=critical", headers=headers)

    results = response.json()
    assert len(results) == 1
    assert results[0]["title"] == "B"


def test_pagination_limit(client, make_user, auth_headers):
    make_user("analyst5@example.com", role=UserRole.analyst)
    headers = auth_headers("analyst5@example.com")

    for i in range(5):
        client.post("/incidents", headers=headers, json={"title": f"Incident {i}", "severity": "low"})

    response = client.get("/incidents?limit=2", headers=headers)

    assert len(response.json()) == 2


def test_comment_appears_in_audit_log(client, make_user, auth_headers):
    make_user("analyst6@example.com", role=UserRole.analyst)
    headers = auth_headers("analyst6@example.com")

    created = client.post(
        "/incidents", headers=headers, json={"title": "Unusual traffic", "severity": "medium"}
    ).json()

    client.post(f"/incidents/{created['id']}/comments", headers=headers, json={"body": "Investigating."})

    audit_log = client.get(f"/incidents/{created['id']}/audit-log", headers=headers).json()

    assert len(audit_log) == 2
    assert audit_log[1]["action"] == "commented"
