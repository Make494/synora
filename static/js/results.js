(() => {
  const printButton = document.querySelector("#print-results");
  if (printButton) printButton.addEventListener("click", () => window.print());

  const experiment = document.querySelector("#results-experiment");
  if (!experiment) return;

  const eyeSourceStatus = document.querySelector("#eye-source-status");
  const eyeResultStatus = document.querySelector("#eye-result-status");
  const eyeResultSummary = document.querySelector("#eye-result-summary");
  const experimentalEyeSummary = document.querySelector("#experimental-eye-summary");
  const experimentalComparison = document.querySelector("#experimental-comparison");
  const experimentalConclusion = document.querySelector("#experimental-conclusion");
  const storageKey = "synoraAssessmentGazeSummary";

  function markSummaryUnavailable() {
    if (experiment.dataset.eyeStatus === "completed") {
      eyeSourceStatus.textContent = "Browser-ийн тойм боломжгүй";
      eyeResultStatus.textContent = "Тойм боломжгүй";
    }
  }

  function isCount(value) {
    return Number.isSafeInteger(value) && value >= 0;
  }

  function readSummary(raw, assessmentId) {
    const summary = JSON.parse(raw);
    const directions = summary?.directions;
    const directionNames = ["left", "right", "up", "down", "center"];
    if (
      !assessmentId ||
      summary?.assessmentId !== assessmentId ||
      !isCount(summary.faceFrames) ||
      !isCount(summary.validEyeFrames) ||
      typeof summary.calibrationComplete !== "boolean" ||
      !directions ||
      directionNames.some((name) => !isCount(directions[name])) ||
      directionNames.reduce((total, name) => total + directions[name], 0) !==
        summary.validEyeFrames ||
      summary.validEyeFrames > summary.faceFrames
    ) {
      return null;
    }
    return summary;
  }

  function renderSummary(summary) {
    if (!summary || summary.validEyeFrames === 0) return false;
    const directionLabels = {
      left: "Зүүн",
      right: "Баруун",
      up: "Дээш",
      down: "Доош",
      center: "Төв орчим",
    };
    const directionSummary = Object.entries(summary.directions)
      .filter(([, count]) => count > 0)
      .map(([direction, count]) => `${directionLabels[direction]}: ${count}`)
      .join(", ");
    const observation =
      `Браузерын туршилтаар хоёр нүдний iris landmark найдвартай илэрсэн ${summary.validEyeFrames} frame байна. ` +
      `Ойролцоо чиглэлийн тоолол: ${directionSummary}. ` +
      `5 цэгийн калибровк ${summary.calibrationComplete ? "дууссан" : "дуусаагүй"}.`;
    eyeSourceStatus.textContent = "Browser-ийн түр тойм боломжтой";
    eyeResultStatus.textContent = "Туршилтын тойм";
    eyeResultSummary.textContent = observation;
    experimentalEyeSummary.textContent = observation;
    experimentalComparison.textContent =
      `Харьцуулалт: Q-CHAT-10-ын одоогийн лавлагааны босго ${experiment.dataset.qchatIndicator === "threshold-reached" ? "хүрсэн" : "хүрээгүй"}. ` +
      "Камерын чиглэлийн тоолол баталгаажсан скринингийн үзүүлэлт биш тул хоёр эх үүсвэрийн нийцэл эсвэл зөрүүг тогтоох боломжгүй.";
    experimentalConclusion.textContent =
      `Ажиглалтын хураангуй: ${summary.validEyeFrames} frame-д ойролцоо gaze тооцоо бүртгэгдэв. ` +
      "Энэ техникийн тойм нь хүүхдийн зан үйлийн утга эсвэл аутизмын үзүүлэлт биш; скринингийн нэгдсэн дүгнэлт гаргаагүй.";
    return true;
  }

  let rawSummary = null;
  try {
    rawSummary = sessionStorage.getItem(storageKey);
  } catch (error) {
    console.error("Browser-ийн түр туршилтын тоймыг уншиж чадсангүй.", error);
    markSummaryUnavailable();
    eyeResultSummary.textContent =
      "Browser-ийн түр тоймыг уншиж чадсангүй. Eye-tracking үр дүн боломжгүй; энэ нь зан үйл эсвэл эрүүл мэндийн дохио биш.";
  }

  if (rawSummary !== null) {
    try {
      const summary = readSummary(rawSummary, experiment.dataset.assessmentId);
      if (!renderSummary(summary)) {
        markSummaryUnavailable();
        eyeResultSummary.textContent =
          "Хүчинтэй eye-tracking хэмжилт бүртгэгдээгүй эсвэл тойм энэ үнэлгээтэй таарахгүй байна. Үүнийг эрсдэлийн үзүүлэлт гэж тайлбарлахгүй.";
      }
    } catch (error) {
      console.error("Browser-ийн түр туршилтын тойм буруу байна.", error);
      markSummaryUnavailable();
      eyeResultSummary.textContent =
        "Туршилтын тойм буруу тул ашигласангүй. Eye-tracking үр дүн боломжгүй; энэ нь эрүүл мэндийн дохио биш.";
    }
    try {
      sessionStorage.removeItem(storageKey);
    } catch (error) {
      console.error("Browser-ийн түр туршилтын тоймыг цэвэрлэж чадсангүй.", error);
    }
  } else {
    markSummaryUnavailable();
  }
})();
