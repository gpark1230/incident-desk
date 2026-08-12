def test_signup_creates_viewer_by_default(client):
    response = client.post("/auth/signup", json={"email": "new@example.com", "password": "testpass123"})

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"
    assert body["role"] == "viewer"


def test_signup_duplicate_email_fails(client):
    client.post("/auth/signup", json={"email": "dupe@example.com", "password": "testpass123"})

    response = client.post("/auth/signup", json={"email": "dupe@example.com", "password": "testpass123"})

    assert response.status_code == 400


def test_login_returns_a_token(client):
    client.post("/auth/signup", json={"email": "login@example.com", "password": "testpass123"})

    response = client.post("/auth/login", data={"username": "login@example.com", "password": "testpass123"})

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_wrong_password_fails(client):
    client.post("/auth/signup", json={"email": "wrongpw@example.com", "password": "testpass123"})

    response = client.post("/auth/login", data={"username": "wrongpw@example.com", "password": "nope"})

    assert response.status_code == 401


def test_me_requires_a_token(client):
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_me_returns_the_logged_in_user(client, auth_headers):
    client.post("/auth/signup", json={"email": "me@example.com", "password": "testpass123"})
    headers = auth_headers("me@example.com")

    response = client.get("/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"
