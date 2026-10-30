import json

import pytest

import app as app_module
from app import create_app


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret"})
    return app.test_client()


def test_screening_page_has_questionnaire_and_navigation(client):
    client.post("/assessment/start", data={"guardian_consent": "yes"})
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


def test_screening_requires_guardian_consent_workflow(client):
    response = client.get("/screening")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/assessment")


def test_homepage_assessment_link_and_camera_assets_are_served(client):
    homepage = client.get("/").get_data(as_text=True)
    assert 'href="/assessment"' in homepage

    client.post("/assessment/start", data={"guardian_consent": "yes"})
    assert client.get("/screening").status_code == 200
    client.post(
        "/api/screening",
        json={"age_months": 20, "answers": ["A"] * 10},
    )
    camera_page = client.get("/camera").get_data(as_text=True)
    assert 'src="/static/js/camera.js"' in camera_page
    assert client.get("/static/js/camera.js").status_code == 200
    assert client.get("/static/js/gaze.mjs").status_code == 200


def test_unified_assessment_requires_guardian_consent_and_clears_previous_result(client):
    start_page = client.get("/assessment")
    assert start_page.status_code == 200
    assert "асран хамгаалагчийн зөвшөөрөл" in start_page.get_data(as_text=True)

    client.post(
        "/api/screening",
        json={"age_months": 20, "answers": ["A"] * 10},
    )
    denied = client.post("/assessment/start", data={})
    assert denied.status_code == 400

    accepted = client.post(
        "/assessment/start",
        data={"guardian_consent": "yes"},
        follow_redirects=False,
    )
    assert accepted.status_code == 302
    assert accepted.headers["Location"].endswith("/screening")
    with client.session_transaction() as browser_session:
        assert browser_session.get("assessment_id")
        assert browser_session.get("guardian_consent") is True
        assert browser_session.get("screening_result") is None


def test_storage_consent_requires_guardian_consent_session(client, monkeypatch):
    saved_records = []
    monkeypatch.setattr(
        app_module,
        "save_screening",
        lambda **record: saved_records.append(record),
    )
    payload = {
        "age_months": 20,
        "answers": ["A"] * 10,
        "consent": True,
    }

    denied = client.post("/api/screening", json=payload)
    assert denied.status_code == 403
    assert saved_records == []

    client.post("/assessment/start", data={"guardian_consent": "yes"})
    accepted = client.post("/api/screening", json=payload)
    assert accepted.status_code == 200
    assert len(saved_records) == 1


def test_unified_workflow_continues_to_camera_and_allows_skip(client):
    client.post("/assessment/start", data={"guardian_consent": "yes"})
    screening = client.post(
        "/api/screening",
        json={"age_months": 20, "answers": ["A"] * 10},
    )
    assert screening.status_code == 200
    assert screening.get_json()["next_url"] == "/camera"

    camera_page = client.get("/camera").get_data(as_text=True)
    assert "АЛХАМ 2 / 3" in camera_page
    assert 'id="assessment-continue"' in camera_page
    assert 'value="skipped"' in camera_page
    assert 'value="unavailable"' in camera_page
    assert "tracking_ratio" not in camera_page

    skipped = client.post(
        "/assessment/eye-tracking",
        data={"status": "skipped"},
        follow_redirects=True,
    )
    assert skipped.status_code == 200
    page = skipped.get_data(as_text=True)
    assert "АЛХАМ 3 / 3" in page
    assert "Алгассан" in page
    assert "Нэгтгэсэн оноо <span>— / 10</span>" in page


def test_unified_workflow_marks_camera_unavailable_without_screening_inference(client):
    client.post("/assessment/start", data={"guardian_consent": "yes"})
    client.post(
        "/api/screening",
        json={"age_months": 20, "answers": ["A"] * 10},
    )
    response = client.post(
        "/assessment/eye-tracking",
        data={"status": "unavailable"},
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Боломжгүй" in page
    assert "Камерын tracking тасалдах" in page
    assert "Дүгнэлт гаргаагүй" in page


def test_eye_tracking_invalid_or_missing_measurement_status_is_rejected(client):
    client.post("/assessment/start", data={"guardian_consent": "yes"})
    for form_data in ({}, {"status": "measurement"}):
        response = client.post("/assessment/eye-tracking", data=form_data)
        assert response.status_code == 400
        assert "төлөв буруу" in response.get_data(as_text=True)


def test_completed_flow_reports_real_gaze_summary_only_when_browser_provides_it(client):
    client.post("/assessment/start", data={"guardian_consent": "yes"})
    client.post(
        "/api/screening",
        json={"age_months": 20, "answers": ["C", "C", "C"] + ["A"] * 6 + ["E"]},
    )
    client.post(
        "/assessment/eye-tracking",
        data={"status": "completed"},
        follow_redirects=True,
    )
    page = client.get("/results").get_data(as_text=True)
    assert "Туршилтын үр дүн ба дүгнэлт" in page
    assert "Одоогийн лавлагааны босго хүрсэн." in page
    assert "Eye-tracking-ийн valid хэмжилт байхгүй" in page
    assert "Хяналттай хөгжүүлэлтэд зориулсан тусдаа research API хэвээр байна." in page
    assert "TD" not in page and "ASD" not in page


def test_research_page_renders_separate_feature_form(client):
    response = client.get("/research")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    for feature in (
        "tracking_ratio",
        "ball_visible_rate",
        "pointing_rate",
        "eyes_rate",
        "face_rate",
        "Age",
    ):
        assert f'id="{feature}"' in page
        assert f'name="{feature}"' in page
    assert "зөвхөн хяналттай хөгжүүлэлт" in page
    assert "зөвшөөрөлтэй, бодит eye-tracking хэмжилтээс гарсан утгыг" in page
    assert "эмнэлзүйн онош" in page
    assert "хяналттай хөгжүүлэлт" in page
    assert 'id="research-loading"' in page
    assert "/static/js/research.js" in page


def test_research_page_has_no_assumed_numeric_bounds(client):
    page = client.get("/research").get_data(as_text=True)
    assert "min=" not in page
    assert "max=" not in page


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


def test_results_dashboard_keeps_unvalidated_score_and_missing_data_unavailable(client):
    client.post(
        "/api/screening",
        json={"age_months": 20, "answers": ["A"] * 10},
    )
    page = client.get("/results").get_data(as_text=True)

    assert "Нэгтгэсэн оноо <span>— / 10</span>" in page
    assert "Шинжлэх ухааны баталгаажуулалт хүлээж байна" in page
    assert "1–2" in page and "3–4" in page and "5–6" in page
    assert "7–8" in page and "9–10" in page
    assert "Браузерын хэмжилтийн тойм" in page
    assert "Боломжгүй · энэ урсгалд холбогдоогүй" in page
    assert "ML үр дүн" in page
    assert "загварын prediction гаргахгүй" in page
    assert "ASD" not in page and "TD" not in page
    assert "Энэ нь аутизм байхгүйг үгүйсгэхгүй" in page
    assert "Туршилтын үр дүн ба дүгнэлт" in page
    assert "нийцэл, зөрүүг тогтоох үндэслэл байхгүй" in page
    assert "ML үр дүн" in page


def test_threshold_result_at_three(client):
    response = client.post(
        "/api/screening",
        json={"age_months": 20, "answers": ["C", "C", "C"] + ["A"] * 6 + ["E"]},
    )
    assert response.status_code == 200
    assert response.get_json()["score"] == 3
    assert response.get_json()["threshold_reached"] is True
    page = client.get("/results").get_data(as_text=True)
    assert "мэргэшсэн эрүүл мэндийн ажилтантай зөвлөлдөнө үү" in page
    assert "Нэгтгэсэн оноо <span>— / 10</span>" in page


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


def test_research_prediction_uses_eye_tracking_features_separately(client):
    response = client.post(
        "/api/research/prediction",
        json={
            "features": {
                "tracking_ratio": 0.0,
                "ball_visible_rate": 0.0,
                "pointing_rate": 0.0,
                "eyes_rate": 0.0,
                "face_rate": 0.0,
                "Age": 0.0,
            }
        },
    )
    assert response.status_code == 200
    result = response.get_json()
    assert result["success"] is True
    assert result["research_prototype"] is True
    assert result["diagnosis"] is False
    assert result["prediction"]["class_id"] in (0, 1)
    assert result["prediction"]["label"] in ("TD", "ASD")
    assert "онош биш" in result["disclaimer"]


@pytest.mark.parametrize(
    "features",
    [
        {},
        {
            "tracking_ratio": 1.0,
            "ball_visible_rate": 1.0,
            "pointing_rate": 1.0,
            "eyes_rate": 1.0,
            "face_rate": 1.0,
            "Age": 1.0,
            "q1": "A",
        },
        {
            "tracking_ratio": "unknown",
            "ball_visible_rate": 0.0,
            "pointing_rate": 0.0,
            "eyes_rate": 0.0,
            "face_rate": 0.0,
            "Age": 0.0,
        },
    ],
)
def test_research_prediction_rejects_wrong_feature_input(client, features):
    response = client.post(
        "/api/research/prediction",
        json={"features": features},
    )
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_about_page_describes_research_model_as_non_diagnostic(client):
    response = client.get("/about")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "tracking_ratio" in page
    assert "эмнэлзүйн онош биш" in page
    assert "Төслийг санаачлагчид:" in page
    assert "Нандин-Эрдэнэ" in page
    assert "Мөрөөдөл" in page
    assert "AI модель сургаж, систем хөгжүүлсэн:" in page
    assert "А. Малик" in page


def test_regular_navigation_hides_manual_research_and_camera_pages(client):
    page = client.get("/").get_data(as_text=True)
    assert "Нэгдсэн үнэлгээ" in page
    assert 'href="/research"' not in page
    assert 'href="/camera"' not in page
    assert client.get("/research").status_code == 200


def test_restarting_assessment_discards_prior_result(client):
    client.post("/assessment/start", data={"guardian_consent": "yes"})
    client.post(
        "/api/screening",
        json={"age_months": 20, "answers": ["A"] * 10},
    )
    with client.session_transaction() as browser_session:
        first_assessment_id = browser_session["assessment_id"]

    client.post("/assessment/start", data={"guardian_consent": "yes"})
    with client.session_transaction() as browser_session:
        assert browser_session["assessment_id"] != first_assessment_id
        assert "screening_result" not in browser_session
        assert browser_session["eye_tracking_status"] == "pending"
    assert client.get("/results").status_code == 302


def test_privacy_page_discloses_research_feature_processing(client):
    response = client.get("/privacy")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "tracking_ratio" in page
    assert "Firebase-д хадгалдаггүй" in page


def test_results_requires_completed_screening(client):
    response = client.get("/results")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/assessment")


@pytest.mark.parametrize("path", ["/", "/about", "/privacy"])
def test_public_pages_load(client, path):
    assert client.get(path).status_code == 200


def test_health_check_is_available_and_does_not_expose_configuration(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    assert b"SECRET_KEY" not in response.data
    assert b"FIREBASE" not in response.data


def test_production_requires_secret_key_and_forces_secure_session(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("FLASK_DEBUG", "true")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app()

    monkeypatch.setenv("SECRET_KEY", "replace-with-a-long-random-secret")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app()

    monkeypatch.setenv("SECRET_KEY", "test-production-secret")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    app = create_app()
    assert app.config["APP_ENV"] == "production"
    assert app.config["DEBUG"] is False
    assert app.config["SESSION_COOKIE_SECURE"] is True
