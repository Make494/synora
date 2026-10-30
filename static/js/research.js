(() => {
  const form = document.querySelector("#research-form");
  if (!form) return;

  const featureNames = [
    "tracking_ratio",
    "ball_visible_rate",
    "pointing_rate",
    "eyes_rate",
    "face_rate",
    "Age",
  ];
  const submitButton = document.querySelector("#research-submit");
  const errorMessage = document.querySelector("#research-error");
  const loadingMessage = document.querySelector("#research-loading");
  const resultSection = document.querySelector("#research-result");

  function showError(message, input) {
    errorMessage.textContent = message;
    if (input) input.focus();
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorMessage.textContent = "";
    resultSection.hidden = true;

    const features = {};
    for (const name of featureNames) {
      const input = form.elements.namedItem(name);
      const rawValue = input.value.trim();
      if (!rawValue) {
        showError(`${name} талбарт утга оруулна уу.`, input);
        return;
      }

      const value = Number(rawValue);
      if (!Number.isFinite(value)) {
        showError(`${name} талбарт тоон утга оруулна уу.`, input);
        return;
      }
      features[name] = value;
    }

    submitButton.disabled = true;
    loadingMessage.hidden = false;
    try {
      const response = await fetch("/api/research/prediction", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ features }),
      });
      let result;
      try {
        result = await response.json();
      } catch {
        throw new Error("Серверээс ирсэн хариуг уншиж чадсангүй.");
      }
      if (!response.ok || result.success !== true || !result.prediction) {
        throw new Error(result.error || "Таамаглалыг боловсруулахад алдаа гарлаа.");
      }

      document.querySelector("#result-class-id").textContent =
        String(result.prediction.class_id);
      document.querySelector("#result-label").textContent =
        String(result.prediction.label);
      document.querySelector("#result-diagnosis").textContent =
        result.diagnosis === false ? "Үгүй — онош биш" : "Тодорхойгүй";
      resultSection.hidden = false;
    } catch (error) {
      errorMessage.textContent =
        error instanceof TypeError
          ? "Сүлжээний холболт тасарлаа. Холболтоо шалгаад дахин оролдоно уу."
          : error.message;
    } finally {
      loadingMessage.hidden = true;
      submitButton.disabled = false;
    }
  });
})();
