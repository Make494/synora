(() => {
  const printButton = document.querySelector("#print-results");
  if (printButton) printButton.addEventListener("click", () => window.print());
})();
