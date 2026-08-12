from app.models import UserRole


def test_viewer_cannot_create_incident(client, make_user, auth_headers):
    make_user("viewer@example.com", role=UserRole.viewer)
    headers = auth_headers("viewer@example.com")

    response = client.post(
        "/incidents",
        headers=headers,
        json={"title": "Suspicious login", "severity": "high"},
    )

    assert response.status_code == 403


def test_analyst_can_create_incident(client, make_user, auth_headers):
    make_user("analyst@example.com", role=UserRole.analyst)
    headers = auth_headers("analyst@example.com")

    response = client.post(
        "/incidents",
        headers=headers,
        json={"title": "Suspicious login", "severity": "high"},
    )

    assert response.status_code == 201


def test_admin_can_create_incident(client, make_user, auth_headers):
    make_user("admin@example.com", role=UserRole.admin)
    headers = auth_headers("admin@example.com")

    response = client.post(
        "/incidents",
        headers=headers,
        json={"title": "Suspicious login", "severity": "high"},
    )

    assert response.status_code == 201


def test_viewer_can_read_incidents(client, make_user, auth_headers):
    analyst = make_user("analyst2@example.com", role=UserRole.analyst)
    make_user("viewer2@example.com", role=UserRole.viewer)

    analyst_headers = auth_headers("analyst2@example.com")
    client.post("/incidents", headers=analyst_headers, json={"title": "Phishing", "severity": "low"})

    viewer_headers = auth_headers("viewer2@example.com")
    response = client.get("/incidents", headers=viewer_headers)

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_viewer_cannot_update_incident(client, make_user, auth_headers):
    make_user("analyst3@example.com", role=UserRole.analyst)
    make_user("viewer3@example.com", role=UserRole.viewer)

    analyst_headers = auth_headers("analyst3@example.com")
    created = client.post(
        "/incidents", headers=analyst_headers, json={"title": "Phishing", "severity": "low"}
    ).json()

    viewer_headers = auth_headers("viewer3@example.com")
    response = client.patch(
        f"/incidents/{created['id']}", headers=viewer_headers, json={"status": "closed"}
    )

    assert response.status_code == 403


def test_viewer_cannot_post_comment(client, make_user, auth_headers):
    make_user("analyst4@example.com", role=UserRole.analyst)
    make_user("viewer4@example.com", role=UserRole.viewer)

    analyst_headers = auth_headers("analyst4@example.com")
    created = client.post(
        "/incidents", headers=analyst_headers, json={"title": "Phishing", "severity": "low"}
    ).json()

    viewer_headers = auth_headers("viewer4@example.com")
    response = client.post(
        f"/incidents/{created['id']}/comments", headers=viewer_headers, json={"body": "sneaky"}
    )

    assert response.status_code == 403
