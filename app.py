import os
import json
import secrets
from pathlib import Path

from dotenv import load_dotenv
from flask_cors import CORS
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from ml.predict import (
    DEFAULT_MODEL_PATH,
    ResearchPredictionInputError,
    predict_research_label,
)
from services.firebase_service import save_screening
from services.screening_service import (
    ScreeningValidationError,
    interpret_score,
    score_answers,
)


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def create_app(test_config=None):
    app = Flask(__name__)
    app_environment = os.environ.get("APP_ENV", "development").strip().lower()
    secret_key = os.environ.get("SECRET_KEY")
    if (
        app_environment == "production"
        and (
            not secret_key
            or secret_key == "replace-with-a-long-random-secret"
        )
    ):
        raise RuntimeError(
            "Production орчинд жинхэнэ, санамсаргүй SECRET_KEY environment variable заавал тохируулна."
        )
    debug_enabled = (
        app_environment != "production"
        and os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    )
    app.config.from_mapping(
        APP_ENV=app_environment,
        SECRET_KEY=secret_key or os.urandom(32),
        DEBUG=debug_enabled,
        RESEARCH_MODEL_PATH=(
            os.environ.get("RESEARCH_MODEL_PATH") or DEFAULT_MODEL_PATH
        ),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=(
            True
            if app_environment == "production"
            else os.environ.get("COOKIE_SECURE", "false").lower() == "true"
        ),
        MAX_CONTENT_LENGTH=16 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    app.json.ensure_ascii = False
    cors_origins = [
        origin.strip()
        for origin in os.environ.get(
            "CORS_ORIGINS", "http://127.0.0.1:5000,http://localhost:5000"
        ).split(",")
        if origin.strip()
    ]
    CORS(app, resources={r"/api/*": {"origins": cors_origins}}, supports_credentials=True)

    @app.get("/healthz")
    def health_check():
        return jsonify(status="ok"), 200

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/assessment")
    def assessment_start():
        return render_template("assessment_start.html")

    @app.post("/assessment/start")
    def start_assessment():
        if request.form.get("guardian_consent") != "yes":
            return (
                render_template(
                    "assessment_start.html",
                    consent_error="Үнэлгээг эхлүүлэхийн өмнө асран хамгаалагчийн зөвшөөрлийг баталгаажуулна уу.",
                ),
                400,
            )

        session.clear()
        session["assessment_id"] = secrets.token_urlsafe(18)
        session["guardian_consent"] = True
        session["eye_tracking_status"] = "pending"
        return redirect(url_for("screening"))

    @app.get("/screening")
    def screening():
        if not session.get("assessment_id") or not session.get("guardian_consent"):
            return redirect(url_for("assessment_start"))

        questions_path = BASE_DIR / "data" / "questions_mn.json"
        with questions_path.open(encoding="utf-8") as questions_file:
            questions = json.load(questions_file)
        return render_template(
            "screening.html",
            questions=questions,
            assessment_active=bool(session.get("assessment_id")),
        )

    @app.get("/research")
    def research():
        return render_template("research.html")

    @app.get("/camera")
    def camera():
        return render_template(
            "camera.html",
            assessment_active=bool(session.get("assessment_id")),
            assessment_id=session.get("assessment_id", ""),
        )

    @app.post("/assessment/eye-tracking")
    def assessment_eye_tracking():
        if not session.get("assessment_id"):
            return redirect(url_for("assessment_start"))

        status = request.form.get("status")
        if status not in {"completed", "skipped", "unavailable"}:
            return "Камерын үнэлгээний төлөв буруу байна.", 400

        session["eye_tracking_status"] = status
        return redirect(url_for("results"))

    @app.post("/api/screening")
    def api_screening():
        if not request.is_json:
            return jsonify(success=False, error="JSON хүсэлт илгээнэ үү."), 400

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(success=False, error="Хүсэлтийн мэдээлэл буруу байна."), 400

        consent = payload.get("consent", False)
        if not isinstance(consent, bool):
            return jsonify(success=False, error="Зөвшөөрлийн утга буруу байна."), 400
        if consent and not session.get("guardian_consent"):
            return (
                jsonify(
                    success=False,
                    error="Мэдээлэл хадгалах зөвшөөрөл өгөхийн өмнө үнэлгээний эхлэх зөвшөөрлийг баталгаажуулна уу.",
                ),
                403,
            )
        age_months = payload.get("age_months")
        answers = payload.get("answers")
        try:
            score = score_answers(age_months, answers)
        except ScreeningValidationError as exc:
            return jsonify(success=False, error=str(exc)), 400

        threshold_reached, interpretation, guidance = interpret_score(score)
        result = {
            "age_months": age_months,
            "score": score,
            "max_score": 10,
            "threshold_reached": threshold_reached,
            "interpretation": interpretation,
            "guidance": guidance,
        }
        session["screening_result"] = result

        if consent:
            try:
                save_screening(
                    age_months=age_months,
                    answers=answers,
                    score=score,
                    consent=consent,
                )
            except RuntimeError as exc:
                app.logger.error("Firebase хадгалалт амжилтгүй: %s", exc)
                return (
                    jsonify(
                        success=False,
                        error="Мэдээллийг хадгалж чадсангүй. Дахин оролдоно уу.",
                    ),
                    503,
                )

        response = dict(
            success=True,
            score=score,
            max_score=10,
            threshold_reached=threshold_reached,
            screening_tool="Q-CHAT-10",
            diagnosis=False,
        )
        if session.get("assessment_id"):
            response["next_url"] = url_for("camera")
        return jsonify(response)

    @app.post("/api/research/prediction")
    def api_research_prediction():
        if not request.is_json:
            return jsonify(success=False, error="JSON хүсэлт илгээнэ үү."), 400

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(success=False, error="Хүсэлтийн мэдээлэл буруу байна."), 400

        try:
            prediction = predict_research_label(
                payload.get("features"),
                app.config["RESEARCH_MODEL_PATH"],
            )
        except ResearchPredictionInputError as exc:
            return jsonify(success=False, error=str(exc)), 400
        except FileNotFoundError as exc:
            app.logger.error("Судалгааны загвар олдсонгүй: %s", exc)
            return (
                jsonify(
                    success=False,
                    error="Судалгааны загварыг одоогоор ачаалж чадсангүй.",
                ),
                503,
            )

        return jsonify(
            success=True,
            research_prototype=True,
            diagnosis=False,
            prediction=prediction,
            disclaimer="Судалгааны прототипийн үр дүн; эмнэлзүйн онош биш.",
        )

    @app.get("/results")
    def results():
        result = session.get("screening_result")
        if result is None:
            return redirect(url_for("assessment_start"))
        eye_tracking_status = session.get("eye_tracking_status", "not-collected")
        eye_tracking_labels = {
            "pending": "Эхлээгүй",
            "completed": "Браузерын туршилт дууссан",
            "skipped": "Алгассан",
            "unavailable": "Боломжгүй",
            "not-collected": "Цуглуулаагүй",
        }
        return render_template(
            "results.html",
            result=result,
            assessment_id=session.get("assessment_id", ""),
            eye_tracking_status=eye_tracking_status,
            eye_tracking_label=eye_tracking_labels.get(
                eye_tracking_status, "Боломжгүй"
            ),
        )

    @app.get("/about")
    def about():
        return render_template("about.html")

    @app.get("/privacy")
    def privacy():
        return render_template("privacy.html")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "5000")),
        debug=app.config["DEBUG"],
    )
