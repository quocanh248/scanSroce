function parseSmartScore(raw) {
  raw = String(raw || "").trim().replace(",", ".");
  if (!raw) return 0;
  let score;
  if (raw.includes(".")) {
    score = parseFloat(raw);
  } else if (raw === "10" || raw === "100") {
    score = 10;
  } else if (/^\d$/.test(raw)) {
    score = parseInt(raw, 10);
  } else if (/^\d{2}$/.test(raw)) {
    score = parseInt(raw, 10) / 10;
  } else if (/^\d{3}$/.test(raw)) {
    score = parseInt(raw, 10) / 100;
  } else {
    return NaN;
  }
  if (score < 0 || score > 10) return NaN;
  return Math.round(score * 100) / 100;
}

function recalcTotal() {
  let total = 0;
  document.querySelectorAll(".score-input").forEach((input) => {
    const parsed = parseSmartScore(input.value);
    const preview = input.closest("tr")?.querySelector(".score-preview");
    if (!isNaN(parsed)) {
      total += parsed;
      if (preview) preview.textContent = parsed.toFixed(2);
    } else {
      if (preview) preview.textContent = "Lỗi";
    }
  });
  const totalBox = document.getElementById("scoreTotal");
  if (totalBox) totalBox.textContent = total.toFixed(2);
}

function renumberRows() {
  document.querySelectorAll("#scoreRows tr").forEach((tr, idx) => {
    const cauInput = tr.querySelector("input[name='cau_so[]']");
    const label = tr.querySelector(".cau-label");
    if (cauInput) cauInput.value = idx + 1;
    if (label) label.textContent = `Câu ${idx + 1}`;
  });
}

document.addEventListener("input", function (e) {
  if (e.target.classList.contains("score-input")) recalcTotal();
});

document.addEventListener("click", function (e) {
  if (e.target.id === "addScoreRow") {
    const tbody = document.getElementById("scoreRows");
    const idx = tbody.querySelectorAll("tr").length + 1;
    const tr = document.createElement("tr");
    tr.className = "border-t";
    tr.innerHTML = `
      <td class="px-4 py-3 font-bold"><span class="cau-label">Câu ${idx}</span><input type="hidden" name="cau_so[]" value="${idx}"></td>
      <td class="px-4 py-3"><input name="diem[]" autocomplete="off" class="score-input w-full rounded-xl border border-slate-300 px-3 py-2 font-mono" placeholder="VD: 35 = 3.5"></td>
      <td class="px-4 py-3 font-mono score-preview">0.00</td>
      <td class="px-4 py-3 text-right"><button type="button" class="remove-score-row rounded-lg border px-3 py-2 text-sm font-bold">Xóa</button></td>
    `;
    tbody.appendChild(tr);
    recalcTotal();
  }

  if (e.target.classList.contains("remove-score-row")) {
    const rows = document.querySelectorAll("#scoreRows tr");
    if (rows.length <= 2) return;
    e.target.closest("tr").remove();
    renumberRows();
    recalcTotal();
  }
});

document.addEventListener("DOMContentLoaded", recalcTotal);
