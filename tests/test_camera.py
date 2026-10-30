from pathlib import Path

from app import create_app


ROOT = Path(__file__).resolve().parents[1]


def test_camera_page_renders_local_camera_controls_and_safety_text():
    client = create_app({"TESTING": True, "SECRET_KEY": "test-secret"}).test_client()

    response = client.get("/camera")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'id="camera-device"' in page
    assert 'id="camera-start"' in page
    assert 'id="camera-stop"' in page
    assert 'id="camera-video"' in page
    assert 'id="landmark-overlay"' in page
    assert "асран хамгаалагчийн зөвшөөрөл" in page
    assert "харцны чиглэлийг" in page
    assert 'id="calibration-start"' in page
    assert 'id="calibration-cancel"' in page
    assert 'id="eye-status"' in page
    assert 'id="gaze-direction"' in page
    assert 'type="module" src="/static/js/camera.js"' in page
    assert "/static/js/camera.js" in page
    assert "Камерын туршилт" in page


def test_camera_javascript_handles_permission_errors_and_cleans_up_tracks():
    source = (ROOT / "static" / "js" / "camera.js").read_text(encoding="utf-8")

    for browser_error in (
        "NotAllowedError",
        "NotFoundError",
        "NotReadableError",
        "OverconstrainedError",
        "SecurityError",
    ):
        assert browser_error in source
    assert "navigator.mediaDevices.getUserMedia" in source
    assert "navigator.mediaDevices.enumerateDevices" in source
    assert "previousStream.getTracks().forEach((track) => track.stop())" in source
    assert 'cameraSelect.addEventListener("change"' in source
    assert 'window.addEventListener("pagehide"' in source
    assert "requestAnimationFrame(detectFrame)" in source
    assert "clearCalibration();" in source


def test_gaze_module_uses_iris_and_eye_landmarks_and_rejects_bad_samples():
    source = (ROOT / "static" / "js" / "gaze.mjs").read_text(encoding="utf-8")

    for index in (33, 133, 362, 263, 468, 472, 473, 477):
        assert str(index) in source
    assert "export function estimateGaze" in source
    assert 'reason: "unreliable-eyes"' in source
    assert "export function addCalibrationSample" in source
    assert "CALIBRATION_SAMPLES_PER_TARGET = 8" in source
    assert "export function applyCalibration" in source


def test_camera_interface_separates_face_eyes_and_experimental_gaze():
    client = create_app({"TESTING": True, "SECRET_KEY": "test-secret"}).test_client()

    page = client.get("/camera").get_data(as_text=True)
    assert 'id="face-status"' in page
    assert 'id="eye-status"' in page
    assert 'id="gaze-direction"' in page
    assert "Tracking тасрах нь зан үйл эсвэл эрүүл мэндийн дохио биш" in page
    assert "туршилтын ойролцоо тооцоо" in page


def test_privacy_page_explains_browser_only_camera_processing():
    client = create_app({"TESTING": True, "SECRET_KEY": "test-secret"}).test_client()

    response = client.get("/privacy")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "зөвхөн браузер дотор түр боловсруулна" in page
    assert "сервер рүү дамжуулахгүй" in page


def test_unified_camera_step_keeps_only_temporary_browser_summary():
    client = create_app({"TESTING": True, "SECRET_KEY": "test-secret"}).test_client()
    client.post("/assessment/start", data={"guardian_consent": "yes"})

    page = client.get("/camera").get_data(as_text=True)
    source = (ROOT / "static" / "js" / "camera.js").read_text(encoding="utf-8")
    assert 'data-assessment-id="' in page
    assert "synoraAssessmentGazeSummary" in source
    assert "validEyeFrames" in source
    assert "calibrationComplete" in source
    assert "sessionStorage.setItem" in source
    assert "fetch(" not in source
    assert 'assessmentContinueButton?.addEventListener("click"' in source


def test_results_reads_and_clears_the_temporary_browser_gaze_summary():
    source = (ROOT / "static" / "js" / "results.js").read_text(encoding="utf-8")
    assert "synoraAssessmentGazeSummary" in source
    assert "summary?.assessmentId !== assessmentId" in source
    assert "sessionStorage.removeItem(storageKey)" in source
    assert "баталгаажсан скринингийн үзүүлэлт биш" in source
    assert "markSummaryUnavailable();" in source
    assert '"Тойм боломжгүй"' in source
