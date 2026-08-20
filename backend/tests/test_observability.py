from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_client_error_report_accepted_without_auth():
    res = client.post(
        "/client-errors",
        json={"message": "TypeError: cannot read x of undefined", "stack": "at foo (app.js:1:1)", "url": "https://app/nesting"},
    )
    assert res.status_code == 204


def test_client_error_report_requires_message():
    res = client.post("/client-errors", json={"url": "https://app/nesting"})
    assert res.status_code == 422
