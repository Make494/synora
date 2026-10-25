import os
import json
from pathlib import Path

from dotenv import load_dotenv
from flask_cors import CORS
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

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
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or os.urandom(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false").lower()
        == "true",
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

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/screening")
    def screening():
        questions_path = BASE_DIR / "data" / "questions_mn.json"
        with questions_path.open(encoding="utf-8") as questions_file:
            questions = json.load(questions_file)
        return render_template("screening.html", questions=questions)

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

        return jsonify(
            success=True,
            score=score,
            max_score=10,
            threshold_reached=threshold_reached,
            screening_tool="Q-CHAT-10",
            diagnosis=False,
        )

    @app.get("/results")
    def results():
        result = session.get("screening_result")
        if result is None:
            return redirect(url_for("screening"))
        return render_template("results.html", result=result)

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
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true",
    )
