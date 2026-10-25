import json

import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret"})
    return app.test_client()


def test_screening_page_has_questionnaire_and_navigation(client):
    response = client.get("/screening")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Та хүүхдийнхээ нэрийг дуудахад" in page
    assert "Хүүхэд тодорхой зорилгогүй мэт" in page
    assert 'id="previous-button"' in page
    assert 'id="next-button"' in page
    assert 'id="submit-button"' in page
    assert 'name="age_months"' in page
    assert "/static/js/screening.js" in page
    assert page.count("Өдөрт олон удаа") >= 1


def test_valid_api_submission_uses_backend_score_and_session_result(client):
    response = client.post(
        "/api/screening",
        json={
            "age_months": 20,
            "answers": ["E", "A", "A", "A", "A", "A", "A", "A", "A", "A"],
        },
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "score": 2,
        "max_score": 10,
        "threshold_reached": False,
        "screening_tool": "Q-CHAT-10",
        "diagnosis": False,
    }
    result_page = client.get("/results")
    assert result_page.status_code == 200
    assert "Q-CHAT-10 асуулгын оноо:" in result_page.get_data(as_text=True)
    assert "2/10" in result_page.get_data(as_text=True)


def test_threshold_result_at_three(client):
    response = client.post(
        "/api/screening",
        json={"age_months": 20, "answers": ["C", "C", "C"] + ["A"] * 6 + ["E"]},
    )
    assert response.status_code == 200
    assert response.get_json()["score"] == 3
    assert response.get_json()["threshold_reached"] is True


@pytest.mark.parametrize(
    "payload",
    [
        {"age_months": 17, "answers": ["A"] * 10},
        {"age_months": 25, "answers": ["A"] * 10},
        {"age_months": 20, "answers": ["A"] * 9},
        {"age_months": 20, "answers": ["A"] * 9 + ["Z"]},
        {"age_months": 20, "answers": ["A"] * 10, "consent": "yes"},
    ],
)
def test_invalid_api_input_is_rejected(client, payload):
    response = client.post("/api/screening", json=payload)
    assert response.status_code == 400
    assert response.get_json()["success"] is False
    assert "error" in response.get_json()


def test_non_json_request_is_rejected(client):
    response = client.post("/api/screening", data=json.dumps({"age_months": 20}))
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_results_requires_completed_screening(client):
    response = client.get("/results")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/screening")


@pytest.mark.parametrize("path", ["/", "/about", "/privacy"])
def test_public_pages_load(client, path):
    assert client.get(path).status_code == 200
