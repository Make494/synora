(() => {
  const dataNode = document.querySelector("#question-data");
  const form = document.querySelector("#screening-form");
  if (!dataNode || !form) return;

  const questions = JSON.parse(dataNode.textContent);
  const answers = Array(questions.length).fill(null);
  let current = 0;
  const questionText = document.querySelector("#question-text");
  const answerList = document.querySelector("#answer-list");
  const questionCount = document.querySelector("#question-count");
  const questionKicker = document.querySelector("#question-kicker");
  const progress = document.querySelector("#progress-bar");
  const progressFill = document.querySelector("#progress-fill");
  const progressPercent = document.querySelector("#progress-percent");
  const previousButton = document.querySelector("#previous-button");
  const nextButton = document.querySelector("#next-button");
  const submitButton = document.querySelector("#submit-button");
  const questionError = document.querySelector("#question-error");
  const submitError = document.querySelector("#submit-error");

  function renderQuestion() {
    const question = questions[current];
    questionText.textContent = question.text;
    questionCount.textContent = `Асуулт ${current + 1} / ${questions.length}`;
    questionKicker.textContent = `АСУУЛТ ${String(current + 1).padStart(2, "0")}`;
    progress.setAttribute("aria-valuenow", String(current + 1));
    progressFill.style.width = `${((current + 1) / questions.length) * 100}%`;
    progressPercent.textContent = `${Math.round(((current + 1) / questions.length) * 100)}%`;
    previousButton.disabled = current === 0;
    nextButton.hidden = current === questions.length - 1;
    submitButton.hidden = current !== questions.length - 1;
    questionError.textContent = "";
    answerList.replaceChildren();

    question.options.forEach((label, optionIndex) => {
      const value = String.fromCharCode(65 + optionIndex);
      const optionLabel = document.createElement("label");
      optionLabel.className = "answer-option";
      const input = document.createElement("input");
      input.type = "radio";
      input.name = `question-${current}`;
      input.value = value;
      input.checked = answers[current] === value;
      const letter = document.createElement("span");
      letter.className = "answer-letter";
      letter.textContent = value;
      const text = document.createElement("span");
      text.className = "answer-text";
      text.textContent = label;
      optionLabel.append(input, letter, text);
      answerList.append(optionLabel);
    });
  }

  function selectedAnswer() {
    return answerList.querySelector('input[type="radio"]:checked')?.value || null;
  }

  nextButton.addEventListener("click", () => {
    const answer = selectedAnswer();
    if (!answer) {
      questionError.textContent = "Үргэлжлүүлэхийн өмнө нэг хариулт сонгоно уу.";
      answerList.querySelector("input")?.focus();
      return;
    }
    answers[current] = answer;
    current += 1;
    renderQuestion();
    questionText.focus({ preventScroll: true });
  });

  previousButton.addEventListener("click", () => {
    if (current > 0) {
      const answer = selectedAnswer();
      if (answer) answers[current] = answer;
      current -= 1;
      renderQuestion();
      questionText.focus({ preventScroll: true });
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submitError.textContent = "";
    const answer = selectedAnswer();
    if (!answer) {
      questionError.textContent = "Үр дүн харахын өмнө энэ асуултад хариулна уу.";
      answerList.querySelector("input")?.focus();
      return;
    }
    answers[current] = answer;
    const ageMonths = Number(document.querySelector("#age-months").value);
    if (!Number.isInteger(ageMonths) || ageMonths < 18 || ageMonths > 24) {
      submitError.textContent = "Үргэлжлүүлэхийн өмнө хүүхдийн насыг 18–24 сараас сонгоно уу.";
      document.querySelector("#age-months").focus();
      return;
    }

    submitButton.disabled = true;
    submitButton.textContent = "Түр хүлээнэ үү…";
    try {
      const response = await fetch("/api/screening", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          age_months: ageMonths,
          answers,
          consent: document.querySelector("#storage-consent").checked,
        }),
      });
      const result = await response.json();
      if (!response.ok || result.success !== true) {
        throw new Error(result.error || "Үнэлгээг боловсруулахад алдаа гарлаа.");
      }
      window.location.assign(result.next_url || "/results");
    } catch (error) {
      submitError.textContent =
        error instanceof TypeError
          ? "Сүлжээний холболт тасарлаа. Холболтоо шалгаад дахин оролдоно уу."
          : error.message;
      submitButton.disabled = false;
      submitButton.innerHTML = 'Үр дүн харах <span aria-hidden="true">→</span>';
    }
  });

  renderQuestion();
})();
