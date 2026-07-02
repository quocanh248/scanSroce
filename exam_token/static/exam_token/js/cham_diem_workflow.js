document.addEventListener("DOMContentLoaded", function () {
  const form = document.querySelector("[data-score-form]");
  const submitBtn = document.querySelector("[data-score-submit]");
  const totalBox = document.querySelector("[data-score-total]");
  const errorBox = document.querySelector("[data-score-error]");

  function scoreInputs() {
    if (!form) return [];
    return Array.from(form.querySelectorAll(".score-input")).filter((el) => !el.disabled && !el.readOnly);
  }

  function formatScore(value) {
    if (Number.isNaN(value)) return "Lỗi";
    return String(Math.round(value * 100) / 100).replace(/\.0$/, "");
  }

  function parseScore(raw) {
    raw = String(raw || "").trim().replace(",", ".");
    if (!raw) return 0;
    if (raw.includes(".")) return Number(raw);
    if (raw === "10" || raw === "100") return 10;
    if (raw.length === 1) return Number(raw);
    if (raw.length === 2) return Number(raw) / 10;
    if (raw.length === 3) return Number(raw) / 100;
    return Number.NaN;
  }

  function setPreview(input, value, hasError) {
    const wrap = input.closest(".rounded-xl") || input.parentElement;
    const preview = (input.parentElement && input.parentElement.querySelector("[data-score-preview]")) ||
                    (wrap && wrap.querySelector("[data-score-preview]"));
    if (!preview) return;
    const raw = input.value.trim();
    if (!raw) {
      preview.textContent = "0";
      preview.classList.remove("text-red-700", "bg-red-50");
      preview.classList.add("text-blue-800", "bg-slate-100");
      return;
    }
    preview.textContent = hasError ? "Lỗi" : formatScore(value);
    preview.classList.toggle("text-red-700", hasError);
    preview.classList.toggle("bg-red-50", hasError);
    preview.classList.toggle("text-blue-800", !hasError);
    preview.classList.toggle("bg-slate-100", !hasError);
  }

  function updateTotal() {
    const inputs = scoreInputs();
    let total = 0;
    let hasError = false;

    inputs.forEach((input) => {
      const raw = input.value.trim();
      if (!raw) {
        input.classList.remove("border-red-500");
        setPreview(input, 0, false);
        return;
      }

      const value = parseScore(raw);
      const inputHasError = Number.isNaN(value) || value < 0 || value > 10;
      if (inputHasError) {
        hasError = true;
        input.classList.add("border-red-500");
      } else {
        input.classList.remove("border-red-500");
        total += value;
      }
      setPreview(input, value, inputHasError);
    });

    total = Math.round(total * 100) / 100;
    if (totalBox) totalBox.textContent = formatScore(total);

    if (errorBox) {
      if (hasError) {
        errorBox.textContent = "Có điểm không hợp lệ.";
        errorBox.classList.remove("hidden");
      } else if (total > 10) {
        errorBox.textContent = "Tổng điểm không được vượt quá 10.";
        errorBox.classList.remove("hidden");
      } else {
        errorBox.textContent = "";
        errorBox.classList.add("hidden");
      }
    }

    if (submitBtn) submitBtn.disabled = hasError || total > 10;
    return { total, hasError };
  }

  if (form) {
    const inputs = scoreInputs();

    inputs.forEach((input) => {
      input.addEventListener("input", updateTotal);
      input.addEventListener("keydown", function (event) {
        if (event.key !== "Enter") return;
        event.preventDefault();

        const currentInputs = scoreInputs();
        const index = currentInputs.indexOf(input);
        const next = currentInputs[index + 1];
        if (next) {
          next.focus();
          next.select();
          return;
        }

        const state = updateTotal();
        if (!state.hasError && state.total <= 10 && submitBtn) submitBtn.click();
      });
    });

    updateTotal();

    // Sau khi quét QR và trang phiếu chấm được render, tự đưa con trỏ vào Câu 1.
    setTimeout(() => {
      const first = scoreInputs()[0];
      if (first) {
        first.focus();
        first.select();
      }
    }, 100);
  }

  const qrInput = document.getElementById("qrInput");
  if (!form && qrInput) {
    qrInput.focus();
    qrInput.select();
  }

  const overlay = document.getElementById("gk1Overlay");
  document.addEventListener("keydown", function (event) {
    if (!event.ctrlKey || event.key !== "9") return;
    if (!overlay) return;
    event.preventDefault();
    overlay.classList.toggle("hidden");
  });
  document.querySelectorAll("[data-close-overlay]").forEach((btn) => {
    btn.addEventListener("click", () => overlay?.classList.add("hidden"));
  });
});
