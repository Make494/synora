import {
  addCalibrationSample,
  applyCalibration,
  CALIBRATION_SAMPLES_PER_TARGET,
  CALIBRATION_TARGETS,
  createCalibration,
  EYE_LANDMARK_INDICES,
  estimateGaze,
  IRIS_LANDMARK_INDICES,
} from "./gaze.mjs";

(() => {
  const video = document.querySelector("#camera-video");
  if (!video) return;

  const cameraSelect = document.querySelector("#camera-device");
  const consentCheckbox = document.querySelector("#camera-consent");
  const startButton = document.querySelector("#camera-start");
  const stopButton = document.querySelector("#camera-stop");
  const cameraStatus = document.querySelector("#camera-status");
  const faceStatus = document.querySelector("#face-status");
  const eyeStatus = document.querySelector("#eye-status");
  const landmarkStatus = document.querySelector("#landmark-status");
  const trackingStatus = document.querySelector("#tracking-status");
  const gazeDirection = document.querySelector("#gaze-direction");
  const calibrationStartButton = document.querySelector("#calibration-start");
  const calibrationCancelButton = document.querySelector("#calibration-cancel");
  const calibrationStatus = document.querySelector("#calibration-status");
  const calibrationTarget = document.querySelector("#calibration-target");
  const gazePoint = document.querySelector("#gaze-point");
  const errorMessage = document.querySelector("#camera-error");
  const placeholder = document.querySelector("#camera-placeholder");
  const preview = document.querySelector("#camera-preview");
  const cameraSection = document.querySelector(".camera-section");
  const assessmentId = cameraSection?.dataset.assessmentId || "";
  const assessmentContinueButton = document.querySelector("#assessment-continue");
  const assessmentCompleteForm = document.querySelector("#assessment-complete-form");
  const assessmentCompleteStatus = document.querySelector("#assessment-complete-status");
  const assessmentFlowStatus = document.querySelector("#assessment-flow-status");
  const canvas = document.querySelector("#landmark-overlay");
  const context = canvas.getContext("2d");
  const version = "1.2.0";
  const packageRoot = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${version}`;
  const modelUrl =
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";
  const eyeBoundaryIndices = new Set([
    ...EYE_LANDMARK_INDICES.eyeA,
    ...EYE_LANDMARK_INDICES.eyeB,
  ]);
  const irisIndices = new Set([
    ...IRIS_LANDMARK_INDICES.eyeA,
    ...IRIS_LANDMARK_INDICES.eyeB,
  ]);
  const directionLabels = {
    left: "Зүүн тийш (ойролцоо)",
    right: "Баруун тийш (ойролцоо)",
    up: "Дээш (ойролцоо)",
    down: "Доош (ойролцоо)",
    center: "Төв орчим (ойролцоо)",
    unavailable: "Боломжгүй",
  };

  let stream = null;
  let landmarker = null;
  let landmarkerPromise = null;
  let animationFrame = null;
  let startAttempt = 0;
  let activeDeviceId = "";
  let isStarting = false;
  let calibration = null;
  let lastCalibrationSampleAt = 0;
  const gazeFrameCounts = {
    faceFrames: 0,
    validEyeFrames: 0,
    directions: { left: 0, right: 0, up: 0, down: 0, center: 0 },
  };

  if (assessmentId) {
    try {
      sessionStorage.removeItem("synoraAssessmentGazeSummary");
    } catch (error) {
      console.warn("Өмнөх browser-side туршилтын тоймыг цэвэрлэж чадсангүй.", error);
    }
  }

  function setCameraStatus(text, state) {
    cameraStatus.textContent = text;
    cameraStatus.dataset.state = state;
  }

  function explainCameraError(error) {
    switch (error && error.name) {
      case "NotAllowedError":
      case "PermissionDeniedError":
        return "Камер ашиглах зөвшөөрөл өгөөгүй байна. Chrome-ийн хаягийн мөрийн камерын зөвшөөрлийг нээгээд дахин оролдоно уу.";
      case "NotFoundError":
      case "OverconstrainedError":
        return "Сонгосон камер олдсонгүй. Камераа холбоод жагсаалтаас дахин сонгоно уу.";
      case "NotReadableError":
        return "Камер өөр программд ашиглагдаж эсвэл төхөөрөмж завгүй байна. Камерыг ашиглаж буй бусад программыг хаагаад дахин оролдоно уу.";
      case "AbortError":
        return "Камер нээгдэх үед алдаа гарлаа. Төхөөрөмж завгүй эсэхийг шалгаад дахин оролдоно уу.";
      case "SecurityError":
      case "TypeError":
        return "Камер ашиглахын тулд энэ хуудсыг HTTPS эсвэл localhost хаягаар нээнэ үү.";
      default:
        return "Камерыг нээж чадсангүй. Төхөөрөмж болон браузерын зөвшөөрлийг шалгана уу.";
    }
  }

  function setFailure(message) {
    errorMessage.textContent = message;
    setCameraStatus("Алдаа", "error");
  }

  async function refreshCameraDevices(preferredDeviceId = "") {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const cameras = devices.filter((device) => device.kind === "videoinput");
    const selectedDeviceId = preferredDeviceId || cameraSelect.value;
    cameraSelect.replaceChildren();

    if (cameras.length === 0) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Камер олдсонгүй";
      cameraSelect.append(option);
      cameraSelect.disabled = true;
      return cameras;
    }

    cameras.forEach((device, index) => {
      const option = document.createElement("option");
      option.value = device.deviceId;
      option.textContent = device.label || `Камер ${index + 1}`;
      cameraSelect.append(option);
    });

    if (cameras.some((device) => device.deviceId === selectedDeviceId)) {
      cameraSelect.value = selectedDeviceId;
    } else {
      cameraSelect.value = cameras[0].deviceId;
    }
    cameraSelect.disabled = Boolean(isStarting && !stream);
    return cameras;
  }

  async function createLandmarker() {
    const visionModule = await import(`${packageRoot}/vision_bundle.mjs`);
    const vision = await visionModule.FilesetResolver.forVisionTasks(
      `${packageRoot}/wasm`,
    );
    const options = {
      baseOptions: { modelAssetPath: modelUrl, delegate: "GPU" },
      runningMode: "VIDEO",
      numFaces: 1,
    };

    try {
      return await visionModule.FaceLandmarker.createFromOptions(vision, options);
    } catch (gpuError) {
      console.warn("MediaPipe GPU delegate амжилтгүй; CPU-г туршиж байна.", gpuError);
      return visionModule.FaceLandmarker.createFromOptions(vision, {
        ...options,
        baseOptions: { modelAssetPath: modelUrl, delegate: "CPU" },
      });
    }
  }

  function getLandmarker() {
    if (!landmarkerPromise) {
      landmarkerPromise = createLandmarker()
        .then((task) => {
          landmarker = task;
          return task;
        })
        .catch((error) => {
          landmarkerPromise = null;
          throw error;
        });
    }
    return landmarkerPromise;
  }

  function resizeOverlay() {
    const bounds = canvas.getBoundingClientRect();
    const pixelRatio = window.devicePixelRatio || 1;
    const width = Math.round(bounds.width * pixelRatio);
    const height = Math.round(bounds.height * pixelRatio);
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    return { width: bounds.width, height: bounds.height, pixelRatio };
  }

  function drawLandmarks(faces) {
    const { width, height, pixelRatio } = resizeOverlay();
    context.clearRect(0, 0, canvas.width, canvas.height);
    if (!Array.isArray(faces?.[0])) return;

    context.save();
    context.scale(pixelRatio, pixelRatio);
    context.translate(width, 0);
    context.scale(-1, 1);
    faces[0].forEach((landmark, index) => {
      if (!Number.isFinite(landmark?.x) || !Number.isFinite(landmark?.y)) return;
      context.beginPath();
      context.arc(
        landmark.x * width,
        landmark.y * height,
        irisIndices.has(index) ? 3.2 : eyeBoundaryIndices.has(index) ? 2.2 : 1.2,
        0,
        Math.PI * 2,
      );
      context.fillStyle = irisIndices.has(index)
        ? "#fb7185"
        : eyeBoundaryIndices.has(index)
          ? "#facc15"
          : "#38e8c2";
      context.fill();
    });
    context.restore();
  }

  function setCalibrationTarget(index) {
    const target = CALIBRATION_TARGETS[index];
    if (!target) {
      calibrationTarget.hidden = true;
      return;
    }
    calibrationTarget.hidden = false;
    calibrationTarget.style.left = `${target.x * 100}%`;
    calibrationTarget.style.top = `${target.y * 100}%`;
  }

  function clearCalibration(message = "Камер эхлүүлсний дараа калибровк хийнэ.") {
    calibration = null;
    lastCalibrationSampleAt = 0;
    calibrationTarget.hidden = true;
    gazePoint.hidden = true;
    calibrationStartButton.disabled = !stream;
    calibrationStartButton.textContent = "Калибровк эхлүүлэх";
    calibrationCancelButton.disabled = true;
    calibrationStatus.textContent = message;
  }

  function startCalibration() {
    if (!stream) {
      calibrationStatus.textContent = "Калибровк хийхийн өмнө камерыг эхлүүлнэ үү.";
      return;
    }
    calibration = createCalibration();
    gazePoint.hidden = true;
    calibrationStartButton.disabled = true;
    calibrationCancelButton.disabled = false;
    calibrationStatus.textContent =
      "1/5 цэг рүү харна уу. Найдвартай нүдний дүрслэл илэрсэн үед дээж цуглуулна.";
    setCalibrationTarget(0);
  }

  function updateGazeStatus(landmarks, now) {
    const gaze = estimateGaze(landmarks);
    if (!gaze.valid) {
      eyeStatus.textContent = "Нүдний/iris landmark найдвартай илрээгүй";
      gazeDirection.textContent = directionLabels.unavailable;
      trackingStatus.textContent = "Нүд найдвартай илрээгүй; дээж авахгүй";
      gazePoint.hidden = true;
      if (calibration) {
        calibrationStatus.textContent =
          `Нүдний дүрслэл найдвартай биш тул дээж авахгүй. ${calibration.currentTarget + 1}/5 цэг дээр үргэлжлүүлнэ.`;
      }
      return;
    }

    eyeStatus.textContent = "Хоёр нүдний iris landmark илэрлээ";
    gazeDirection.textContent = directionLabels[gaze.direction];
    trackingStatus.textContent = "Нүүр болон хоёр нүд дагалдаж байна; чанарын хувь тооцохгүй";
    gazeFrameCounts.validEyeFrames += 1;
    gazeFrameCounts.directions[gaze.direction] += 1;

    const point = applyCalibration(calibration, gaze);
    if (point) {
      gazePoint.style.left = `${point.x * 100}%`;
      gazePoint.style.top = `${point.y * 100}%`;
      gazePoint.hidden = false;
    } else {
      gazePoint.hidden = true;
    }

    if (!calibration || now - lastCalibrationSampleAt < 120) return;
    lastCalibrationSampleAt = now;
    const result = addCalibrationSample(calibration, gaze);
    if (!result.accepted) return;
    if (result.complete) {
      calibrationTarget.hidden = true;
      calibrationStartButton.disabled = false;
      calibrationStartButton.textContent = "Дахин калибровк хийх";
      calibrationCancelButton.disabled = false;
      calibrationStatus.textContent =
        "5 цэгийн калибровк дууслаа. Одоогийн харцны цэг ойролцоо дүрслэгдэнэ.";
    } else if (result.failed) {
      clearCalibration(
        "5 цэгийн дээжээс калибровк тооцоолж чадсангүй. Цэгүүдийг дагуулан харж дахин оролдоно уу.",
      );
    } else {
      const currentTarget = result.targetIndex;
      setCalibrationTarget(currentTarget);
      if (result.sampleCount < CALIBRATION_SAMPLES_PER_TARGET) {
        calibrationStatus.textContent =
          `${currentTarget + 1}/5 цэг рүү харна уу. ${result.sampleCount}/${CALIBRATION_SAMPLES_PER_TARGET} хүчинтэй дээж цугларлаа.`;
      } else if (currentTarget < CALIBRATION_TARGETS.length) {
        calibrationStatus.textContent =
          `${currentTarget + 1}/5 цэг рүү харна уу. Өмнөх цэгийн дээж цугларлаа.`;
      }
    }
  }

  function updateDetectionStatus(faces) {
    if (faces.length > 0) {
      gazeFrameCounts.faceFrames += 1;
      const landmarks = Array.isArray(faces[0]) ? faces[0] : [];
      faceStatus.textContent = landmarks.length ? "Нүүр илэрлээ" : "Нүүрний landmark дутуу";
      landmarkStatus.textContent = `${landmarks.length} landmark дүрслэгдэж байна`;
      placeholder.hidden = true;
      updateGazeStatus(landmarks, performance.now());
    } else {
      faceStatus.textContent = "Нүүр илрээгүй";
      landmarkStatus.textContent = "Нүүр илрүүлэхийг хүлээж байна";
      eyeStatus.textContent = "Нүүр байхгүй тул нүдийг шалгах боломжгүй";
      gazeDirection.textContent = directionLabels.unavailable;
      trackingStatus.textContent = "Нүүр илрээгүй; шалтгаан таамаглахгүй";
      gazePoint.hidden = true;
      placeholder.hidden = false;
      placeholder.textContent = "Нүүр камерын хүрээнд орж ирэхэд landmark дүрслэгдэнэ";
      if (calibration) {
        calibrationStatus.textContent =
          `Нүүр илрээгүй тул дээж авахгүй. ${calibration.currentTarget + 1}/5 цэг дээр үргэлжлүүлнэ.`;
      }
    }
  }

  function detectFrame() {
    if (!stream || !landmarker) return;
    if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      animationFrame = requestAnimationFrame(detectFrame);
      return;
    }
    try {
      const result = landmarker.detectForVideo(video, performance.now());
      const faces = Array.isArray(result.faceLandmarks) ? result.faceLandmarks : [];
      drawLandmarks(faces);
      updateDetectionStatus(faces);
      animationFrame = requestAnimationFrame(detectFrame);
    } catch (error) {
      console.error("Face landmark илрүүлэлт амжилтгүй.", error);
      void stopCamera();
      setFailure("Нүүрний landmark илрүүлэхэд алдаа гарлаа. Камерыг дахин эхлүүлнэ үү.");
    }
  }

  async function finishAssessmentCameraStep() {
    if (!assessmentId || !assessmentCompleteForm || !assessmentCompleteStatus) return;

    const summary = {
      assessmentId,
      faceFrames: gazeFrameCounts.faceFrames,
      validEyeFrames: gazeFrameCounts.validEyeFrames,
      directions: { ...gazeFrameCounts.directions },
      calibrationComplete: Boolean(calibration?.complete),
    };
    let status = summary.validEyeFrames > 0 ? "completed" : "unavailable";
    try {
      sessionStorage.setItem("synoraAssessmentGazeSummary", JSON.stringify(summary));
    } catch (error) {
      console.error("Туршилтын тоймыг browser session-д хадгалж чадсангүй.", error);
      status = "unavailable";
      if (assessmentFlowStatus) {
        assessmentFlowStatus.textContent =
          "Браузерын түр тоймыг хадгалж чадсангүй. Үр дүнд eye-tracking мэдээлэл боломжгүй гэж тэмдэглэгдэнэ.";
      }
    }

    if (assessmentContinueButton) assessmentContinueButton.disabled = true;
    await stopCamera();
    assessmentCompleteStatus.value = status;
    assessmentCompleteForm.requestSubmit();
  }

  async function stopCamera() {
    startAttempt += 1;
    if (animationFrame !== null) {
      cancelAnimationFrame(animationFrame);
      animationFrame = null;
    }
    const previousStream = stream;
    stream = null;
    activeDeviceId = "";
    if (previousStream) {
      previousStream.getTracks().forEach((track) => track.stop());
    }
    video.pause();
    video.srcObject = null;
    preview.classList.remove("is-active");
    preview.style.aspectRatio = "4 / 3";
    context.clearRect(0, 0, canvas.width, canvas.height);
    placeholder.hidden = false;
    placeholder.textContent = "Камер эхлээгүй байна";
    cameraSelect.disabled = !consentCheckbox.checked;
    startButton.disabled = false;
    stopButton.disabled = true;
    faceStatus.textContent = "Камер асаахыг хүлээж байна";
    eyeStatus.textContent = "Камер асаахыг хүлээж байна";
    landmarkStatus.textContent = "Эхлээгүй";
    trackingStatus.textContent = "Хэмжээгүй";
    gazeDirection.textContent = directionLabels.unavailable;
    clearCalibration();
    isStarting = false;
    if (cameraStatus.dataset.state !== "error") {
      setCameraStatus("Холбогдоогүй", "idle");
    }
  }

  async function startCamera() {
    if (isStarting || stream) return;
    errorMessage.textContent = "";
    if (!consentCheckbox.checked) {
      setFailure("Камерыг асаахаас өмнө дээрх зөвшөөрлийг сонгоно уу.");
      return;
    }
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      setFailure(explainCameraError({ name: "SecurityError" }));
      return;
    }

    isStarting = true;
    const attempt = ++startAttempt;
    startButton.disabled = true;
    stopButton.disabled = false;
    cameraSelect.disabled = true;
    setCameraStatus("Холбогдож байна", "starting");
    landmarkStatus.textContent = "Загвар ачаалж байна";

    try {
      const deviceId = cameraSelect.value;
      const constraints = {
        audio: false,
        video: deviceId ? { deviceId: { exact: deviceId } } : true,
      };
      const nextStream = await navigator.mediaDevices.getUserMedia(constraints);
      if (attempt !== startAttempt) {
        nextStream.getTracks().forEach((track) => track.stop());
        return;
      }

      stream = nextStream;
      const videoTrack = stream.getVideoTracks()[0];
      if (!videoTrack) throw new DOMException("Video track алга.", "NotFoundError");
      activeDeviceId = videoTrack.getSettings().deviceId || deviceId;
      video.srcObject = stream;
      preview.classList.add("is-active");
      await video.play();
      if (video.readyState < HTMLMediaElement.HAVE_METADATA) {
        await new Promise((resolve, reject) => {
          video.addEventListener("loadedmetadata", resolve, { once: true });
          video.addEventListener(
            "error",
            () => reject(new DOMException("Видео нээгдсэнгүй.", "NotReadableError")),
            { once: true },
          );
        });
      }
      if (video.videoWidth > 0 && video.videoHeight > 0) {
        preview.style.aspectRatio = `${video.videoWidth} / ${video.videoHeight}`;
      }

      const cameras = await refreshCameraDevices(activeDeviceId);
      if (attempt !== startAttempt) return;
      if (cameras.length === 0) {
        throw new DOMException("Камер олдсонгүй.", "NotFoundError");
      }

      await getLandmarker();
      if (attempt !== startAttempt) return;

      isStarting = false;
      cameraSelect.disabled = false;
      startButton.disabled = true;
      stopButton.disabled = false;
      setCameraStatus("Ажиллаж байна", "active");
      landmarkStatus.textContent = "Илрүүлэлт ажиллаж байна";
      eyeStatus.textContent = "Нүдний landmark хүлээж байна";
      gazeDirection.textContent = directionLabels.unavailable;
      calibrationStartButton.disabled = false;
      calibrationStatus.textContent = "Харцыг дэлгэцэд зураглахын тулд 5 цэгийн калибровк хийнэ үү.";
      placeholder.hidden = false;
      placeholder.textContent = "Нүүр камерын хүрээнд орж ирэхэд landmark дүрслэгдэнэ";
      animationFrame = requestAnimationFrame(detectFrame);
      videoTrack.addEventListener("ended", () => {
        if (stream === nextStream) {
          void stopCamera();
          setFailure("Камерын холболт тасарлаа. Төхөөрөмжийн холболтыг шалгана уу.");
        }
      }, { once: true });
    } catch (error) {
      if (attempt !== startAttempt) return;
      await stopCamera();
      console.error("Камер эсвэл landmark загварыг эхлүүлэх амжилтгүй.", error);
      setFailure(explainCameraError(error));
    }
  }

  startButton.addEventListener("click", () => {
    void startCamera();
  });
  stopButton.addEventListener("click", () => {
    errorMessage.textContent = "";
    void stopCamera();
  });
  calibrationStartButton.addEventListener("click", startCalibration);
  calibrationCancelButton.addEventListener("click", () => {
    clearCalibration("Калибровк цэвэрлэгдлээ. Дээж зөвхөн энэ хуудас нээлттэй үед хадгалагдана.");
  });
  cameraSelect.addEventListener("change", () => {
    if (stream) {
      void (async () => {
        await stopCamera();
        await startCamera();
      })();
    }
  });
  consentCheckbox.addEventListener("change", () => {
    if (consentCheckbox.checked) return;
    void stopCamera();
    cameraSelect.disabled = true;
  });
  window.addEventListener("pagehide", () => {
    void stopCamera();
  });

  assessmentContinueButton?.addEventListener("click", () => {
    void finishAssessmentCameraStep();
  });

  if (navigator.mediaDevices?.addEventListener) {
    navigator.mediaDevices.addEventListener("devicechange", () => {
      if (stream) {
        void refreshCameraDevices(activeDeviceId).catch((error) => {
          console.error("Камерын жагсаалтыг шинэчилж чадсангүй.", error);
        });
      }
    });
  }
})();
