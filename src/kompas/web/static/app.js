const API = "/api/v1";

const state = {
  token: localStorage.getItem("kompas_token") || "",
  user: null,
  employees: [],
  evaluations: [],
  model: null,
  forms: null,
  activeEval: null,
  activeProgress: null,
};

const $ = (id) => document.getElementById(id);

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function showHomeAlert(msg, kind = "error") {
  const el = $("home-alert");
  el.className = `alert alert-${kind}`;
  el.textContent = msg;
  el.hidden = !msg;
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.token) headers.set("Authorization", `Bearer ${state.token}`);
  if (!(options.body instanceof FormData) && options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const resp = await fetch(`${API}${path}`, { ...options, headers });
  if (!resp.ok) {
    let msg = `Błąd HTTP ${resp.status}`;
    try {
      const data = await resp.json();
      msg = data?.error?.message || data?.detail || msg;
    } catch { /* ignore */ }
    throw new Error(msg);
  }
  const ct = resp.headers.get("content-type") || "";
  return ct.includes("application/json") ? resp.json() : resp;
}

function showAlert(msg, kind = "error") {
  const el = $("wiz-alert");
  el.className = `alert alert-${kind}`;
  el.textContent = msg;
  el.hidden = !msg;
}

function showView(loggedIn) {
  $("view-login").hidden = loggedIn;
  $("view-workspace").hidden = !loggedIn;
  $("user-bar").hidden = !loggedIn;
}

async function bootstrapWorkspace() {
  state.user = await api("/auth/me");
  $("user-pill").textContent = `${state.user.full_name} (${state.user.role})`;
  $("btn-hr").hidden = !["hr", "admin"].includes(state.user.role);

  const [employees, evaluations, model, forms] = await Promise.all([
    api("/evaluations/employees"),
    api("/evaluations"),
    api("/competencies/model"),
    api("/competencies/forms"),
  ]);
  state.employees = employees;
  state.evaluations = evaluations;
  state.model = model;
  state.forms = forms;

  renderHome();
  showView(true);
}

function renderHome() {
  $("panel-home").hidden = false;
  $("panel-wizard").hidden = true;
  $("panel-hr").hidden = true;

  const opts = state.employees
    .map((e) => `<option value="${e.id}">${e.first_name} ${e.last_name} — ${e.position}</option>`)
    .join("");
  $("select-emp-first").innerHTML = opts || `<option value="">Brak podległych pracowników</option>`;
  $("select-emp-periodic").innerHTML = opts || `<option value="">Brak podległych pracowników</option>`;

  const empMap = Object.fromEntries(state.employees.map((e) => [e.id, e]));
  const rows = state.evaluations
    .map((ev) => {
      const emp = empMap[ev.employee_id];
      const name = emp ? `${emp.first_name} ${emp.last_name}` : ev.employee_id;
      const typeLbl = ev.type === "first" ? "Pierwsza ocena" : `Ocena okresowa (Arkusz ${ev.form})`;
      return `
        <div class="eval-row">
          <div>
            <strong>${name}</strong> • ${typeLbl}<br/>
            <span class="muted small">Status: ${ev.status} | Etap: ${ev.current_step}</span>
          </div>
          <button class="btn btn-outline btn-open-eval" data-id="${ev.id}">Otwórz</button>
        </div>`;
    })
    .join("");
  $("evaluations-list").innerHTML = rows || `<p class="muted">Brak utworzonych ocen. Rozpocznij nową ocenę powyżej.</p>`;
  document.querySelectorAll(".btn-open-eval").forEach((b) =>
    b.addEventListener("click", () => openEvaluation(b.dataset.id))
  );
}

function renderDeadlinesPanel(ev) {
  const panel = $("wiz-deadlines-panel");
  const rows = (ev.deadlines || [])
    .map(
      (d) =>
        `<tr><td>${escapeHtml(d.label)}</td><td><strong>${d.due_date}</strong></td><td class="muted small">${escapeHtml(d.legal_basis || "-")}</td></tr>`
    )
    .join("");
  const extRows = (ev.deadline_extensions || [])
    .map(
      (x) =>
        `<li class="small">${escapeHtml(x.step_id)}: ${x.previous_due_date} → <strong>${x.new_due_date}</strong> (${escapeHtml(x.reason)})</li>`
    )
    .join("");
  const stepOpts = (ev.deadlines || [])
    .map((d) => `<option value="${d.step_id}">${escapeHtml(d.label)} (${d.due_date})</option>`)
    .join("");

  panel.innerHTML = `
    <h4>Terminy ustawowe i przedłużenia (§ 5 rozp. 2015 / art. 81 ust. 8 ustawy)</h4>
    ${rows ? `<table><tr><th>Etap</th><th>Termin</th><th>Podstawa prawna</th></tr>${rows}</table>` : `<p class="muted small">Brak zdefiniowanych terminów.</p>`}
    ${extRows ? `<div style="margin-top:10px;"><strong>Historia przedłużeń:</strong><ul>${extRows}</ul></div>` : ""}
    ${
      stepOpts
        ? `<form id="form-extend-deadline" class="deadline-ext-form">
             <label class="small">Etap<select id="ext-step">${stepOpts}</select></label>
             <label class="small">Nowy termin<input type="date" id="ext-date" required /></label>
             <label class="small">Przyczyna (np. nieobecność)<input type="text" id="ext-reason" minlength="3" placeholder="Usprawiedliwiona nieobecność..." required /></label>
             <button type="submit" class="btn btn-outline">Przedłuż termin</button>
           </form>`
        : ""
    }`;

  const form = $("form-extend-deadline");
  if (form) {
    form.onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api(`/evaluations/${ev.id}/deadlines/extend`, {
          method: "POST",
          body: JSON.stringify({
            step_id: $("ext-step").value,
            new_due_date: $("ext-date").value,
            reason: $("ext-reason").value.trim(),
          }),
        });
        await openEvaluation(ev.id);
        $("wiz-deadlines-panel").hidden = false;
      } catch (err) {
        showAlert(err.message);
      }
    };
  }
}

async function openEvaluation(evalId) {
  showAlert("");
  const [ev, progress] = await Promise.all([
    api(`/evaluations/${evalId}`),
    api(`/evaluations/${evalId}/progress`),
  ]);
  state.activeEval = ev;
  state.activeProgress = progress;

  $("panel-home").hidden = true;
  $("panel-hr").hidden = true;
  $("panel-wizard").hidden = false;

  const emp = state.employees.find((e) => e.id === ev.employee_id);
  const empName = emp ? `${emp.first_name} ${emp.last_name} (${emp.position})` : ev.employee_id;
  const reevalTag = ev.is_post_negative_reevaluation ? " • Ponowna ocena (6 mies.)" : "";
  $("wiz-title").textContent = `${ev.type === "first" ? "Pierwsza ocena" : "Ocena okresowa"} — ${empName}`;
  $("wiz-meta").textContent = `ID: ${ev.id} • Arkusz ${ev.form} • Status: ${ev.status}${reevalTag}`;

  renderDeadlinesPanel(ev);

  $("wiz-stepper").innerHTML = progress.steps
    .map(
      (s, i) => `
      <div class="step-pill ${s.state}" title="${s.legal_basis || ""}">
        ${i + 1}. ${s.title}
      </div>`
    )
    .join("");

  renderCurrentStep(ev);
}

async function completeStep(stepId, note = null) {
  try {
    showAlert("");
    await api(`/evaluations/${state.activeEval.id}/steps/complete`, {
      method: "POST",
      body: JSON.stringify({ step_id: stepId, note }),
    });
    await openEvaluation(state.activeEval.id);
  } catch (err) {
    showAlert(err.message);
  }
}

function renderCurrentStep(ev) {
  const body = $("wiz-body");
  if (ev.status === "completed") {
    body.innerHTML = `
      <div class="alert alert-ok">Ocena została zakończona.</div>
      <div class="field-row">
        <button class="btn btn-primary" id="btn-dl-pdf">Pobierz arkusz PDF (z archiwizacją)</button>
        <button class="btn btn-outline" id="btn-dl-html">Podgląd HTML</button>
      </div>`;
    $("btn-dl-pdf").onclick = () => downloadDoc(ev.id, "pdf", true);
    $("btn-dl-html").onclick = () => downloadDoc(ev.id, "html", false);
    return;
  }

  const step = ev.current_step;
  if (step === "job_description_analysis") {
    body.innerHTML = `
      <h3>1. Analiza opisu stanowiska pracy (OSP)</h3>
      <p class="muted">Wgraj plik OSP (.docx / .pdf) lub wklej treść, aby zweryfikować dobór formularza (B vs C) i kryteriów dodatkowych.</p>
      <div class="field-col">
        <label>Plik OSP (.docx / .pdf / .txt)<input type="file" id="osp-file" accept=".docx,.pdf,.txt,.md" /></label>
        <label>Lub wklej fragment OSP<textarea id="osp-text" rows="4" placeholder="Wklej główne zadania i wymagania ze stanowiska..."></textarea></label>
      </div>
      <div class="field-row">
        <button class="btn btn-purple" id="btn-analyze-osp">Analizuj OSP</button>
        <button class="btn btn-primary" id="btn-step-done">Przejdź dalej →</button>
      </div>
      <div id="osp-result" style="margin-top:12px;"></div>`;
    $("btn-analyze-osp").onclick = async () => {
      try {
        const fileInput = $("osp-file");
        let res;
        if (fileInput.files.length > 0) {
          const fd = new FormData();
          fd.append("file", fileInput.files[0]);
          res = await api("/competencies/analyze-job-description/upload", { method: "POST", body: fd });
        } else {
          res = await api("/competencies/analyze-job-description", {
            method: "POST",
            body: JSON.stringify({ text: $("osp-text").value }),
          });
        }
        const recs = res.recommended_additional_criteria
          .map((r) => `<li><strong>${r.name}</strong> — ${r.reason}</li>`)
          .join("");
        $("osp-result").innerHTML = `
          <div class="alert alert-ok">
            <strong>${res.rationale}</strong>
            ${recs ? `<ul>${recs}</ul>` : "<p>Brak dodatkowych rekomendacji słów kluczowych.</p>"}
          </div>`;
      } catch (err) {
        showAlert(err.message);
      }
    };
    $("btn-step-done").onclick = () => completeStep("job_description_analysis");
    return;
  }

  if (step === "criteria_setting") {
    const formDef = state.forms[ev.form];
    const allowed = formDef.allowed_additional_criteria;
    const byId = Object.fromEntries(state.model.competencies.map((c) => [c.id, c.name]));
    const checkboxes = allowed
      .map((cid) => {
        const chk = ev.additional_criteria.includes(cid) ? "checked" : "";
        return `<label><input type="checkbox" name="add-crit" value="${cid}" ${chk} style="width:auto;" /> ${byId[cid] || cid}</label>`;
      })
      .join("");
    body.innerHTML = `
      <h3>2. Ustalenie kryteriów oceny (Część I arkusza ${ev.form})</h3>
      <p><strong>Kryteria obowiązkowe:</strong> ${ev.mandatory_criteria.map((c) => byId[c] || c).join(", ")}</p>
      <p><strong>Kryteria dodatkowe (maks. ${formDef.max_additional_criteria}):</strong></p>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-bottom:12px;">${checkboxes}</div>
      <label>Cele do osiągnięcia (jeden na linię, opcjonalnie)
        <textarea id="wiz-goals" rows="3">${(ev.goals || []).join("\n")}</textarea>
      </label>
      <div class="field-row">
        <button class="btn btn-primary" id="btn-save-criteria">Zatwierdź kryteria i przejdź dalej →</button>
      </div>`;
    $("btn-save-criteria").onclick = async () => {
      try {
        const chosen = [...document.querySelectorAll('input[name="add-crit"]:checked')].map((x) => x.value);
        const goals = $("wiz-goals").value.split("\n").map((s) => s.trim()).filter(Boolean);
        await api(`/evaluations/${ev.id}/criteria`, {
          method: "PUT",
          body: JSON.stringify({ additional_criteria: chosen, goals, confirm: true }),
        });
        await completeStep("criteria_setting");
      } catch (err) {
        showAlert(err.message);
      }
    };
    return;
  }

  if (step === "initial_interview") {
    body.innerHTML = `
      <h3>Rozmowa wstępna (§ 3 rozporządzenia z 23.07.2015 r.)</h3>
      <p class="muted">Omów z ocenianym obowiązki z OSP, oczekiwania wobec 5 elementów oceny oraz wyznacz termin złożenia sprawozdania (po 8 miesiącach pracy).</p>
      <button class="btn btn-primary" id="btn-init-done">Potwierdź rozmowę wstępną i przejdź dalej →</button>`;
    $("btn-init-done").onclick = () => completeStep("initial_interview");
    return;
  }

  if (step === "report") {
    const rd = ev.report_details || {};
    const onTimeVal = ev.report_submitted_on_time === false ? "false" : "true";
    body.innerHTML = `
      <h3>Sprawozdanie ocenianego (Załącznik nr 3)</h3>
      <p class="muted">Sprawozdanie powinno obejmować okres nie krótszy niż 7 miesięcy (§ 6 ust. 1 rozporządzenia z 23.07.2015 r.).</p>
      <div class="field-col">
        <label>Czy sprawozdanie złożono w wyznaczonym terminie?
          <select id="rep-ontime">
            <option value="true" ${onTimeVal === "true" ? "selected" : ""}>Tak – w terminie</option>
            <option value="false" ${onTimeVal === "false" ? "selected" : ""}>Nie – po terminie / brak</option>
          </select>
        </label>
        <label>Okres objęty sprawozdaniem (w miesiącach, min. 7)
          <input type="number" id="rep-period" min="7" max="24" value="${rd.period_months ?? 8}" />
        </label>
        <label>Wykonywane zadania
          <textarea id="rep-tasks" rows="2" placeholder="Główne zadania realizowane w okresie pierwszej oceny...">${escapeHtml(rd.tasks_performed || "")}</textarea>
        </label>
        <label>Napotkane trudności i sposoby ich rozwiązania
          <textarea id="rep-problems" rows="2" placeholder="Opis trudności oraz podjętych działań...">${escapeHtml(rd.problems_and_solutions || "")}</textarea>
        </label>
        <label>Nabyte umiejętności i wiedza
          <textarea id="rep-skills" rows="2" placeholder="Nowe kompetencje, szkolenia, narzędzia...">${escapeHtml(rd.new_skills_and_knowledge || "")}</textarea>
        </label>
        <label>Propozycje usprawnień na stanowisku pracy
          <textarea id="rep-improvements" rows="2" placeholder="Rekomendacje organizacyjne lub merytoryczne...">${escapeHtml(rd.improvement_proposals || "")}</textarea>
        </label>
      </div>
      <button class="btn btn-primary" id="btn-save-rep">Zapisz sprawozdanie i przejdź dalej →</button>`;
    $("btn-save-rep").onclick = async () => {
      try {
        showAlert("");
        const periodRaw = $("rep-period").value.trim();
        const periodMonths = periodRaw ? Number(periodRaw) : null;
        if (periodMonths !== null && periodMonths < 7) {
          showAlert("Sprawozdanie musi obejmować okres nie krótszy niż 7 miesięcy (§ 6 ust. 1).");
          return;
        }
        const tasks = $("rep-tasks").value.trim();
        const problems = $("rep-problems").value.trim();
        const skills = $("rep-skills").value.trim();
        const improvements = $("rep-improvements").value.trim();
        const hasAnyDetail = Boolean(tasks || problems || skills || improvements);
        if (hasAnyDetail && !tasks) {
          showAlert("Uzupełnij pole „Wykonywane zadania” lub wyczyść pozostałe pola szczegółowe.");
          return;
        }
        await api(`/evaluations/${ev.id}/first-eval-facts`, {
          method: "PUT",
          body: JSON.stringify({
            report_submitted_on_time: $("rep-ontime").value === "true",
            report_details: hasAnyDetail
              ? {
                  tasks_performed: tasks,
                  problems_and_solutions: problems,
                  new_skills_and_knowledge: skills,
                  improvement_proposals: improvements,
                  period_months: periodMonths,
                }
              : null,
          }),
        });
        await completeStep("report");
      } catch (err) {
        showAlert(err.message);
      }
    };
    return;
  }

  if (step === "competency_assessment") {
    const scalePoints = state.forms[ev.form].scale.map((s) => s.points);
    const scaleLabels = Object.fromEntries(state.forms[ev.form].scale.map((s) => [s.points, s.label]));
    const criteria = [...ev.mandatory_criteria, ...ev.additional_criteria];
    const compMap = Object.fromEntries(state.model.competencies.map((c) => [c.id, c]));

    body.innerHTML = `
      <h3>Ocena kompetencji z zastosowaniem modelu</h3>
      <p class="muted">Dla każdego wskaźnika wybierz obserwowane zachowanie (lub „Brak podstaw”). System podpowie poziom – ostateczną ocenę cząstkową wybierasz Ty.</p>
      <div id="comp-cards">
        ${criteria
          .map((cid) => {
            const comp = compMap[cid];
            const existing = ev.assessments[cid] || {};
            const obsMap = Object.fromEntries((existing.indicators || []).map((i) => [i.indicator_id, i]));
            const sugTxt = existing.suggestion
              ? `Sugestia systemu: <strong>${existing.suggestion.points ?? "-"} pkt</strong> (${existing.suggestion.message})`
              : "Wybierz wskaźniki i zapisz kryterium, aby zobaczyć sugestię systemu.";
            return `
              <div class="criterion-box" data-cid="${cid}">
                <div class="row-between">
                  <h4>${comp.name}</h4>
                  <span class="muted small">${sugTxt}</span>
                </div>
                ${comp.indicators
                  .map((ind) => {
                    const cur = obsMap[ind.id]?.observed_points;
                    return `
                      <div class="indicator-row">
                        <div><strong>${ind.name}</strong></div>
                        <div class="level-grid">
                          ${scalePoints
                            .map((pts) => {
                              const checked = cur === pts ? "checked" : "";
                              return `
                                <label class="level-opt ${cur === pts ? "selected" : ""}">
                                  <input type="radio" name="ind-${ind.id}" value="${pts}" ${checked} />
                                  <strong>${pts} pkt</strong> (${scaleLabels[pts]})<br/>
                                  <span>${ind.levels[pts] || ""}</span>
                                </label>`;
                            })
                            .join("")}
                          <label class="level-opt ${cur === null ? "selected" : ""}">
                            <input type="radio" name="ind-${ind.id}" value="" ${cur === null ? "checked" : ""} />
                            <strong>Brak podstaw</strong><br/>Brak okazji do obserwacji.
                          </label>
                        </div>
                        <input
                          type="text"
                          class="evidence-input ind-evidence"
                          data-ind-id="${ind.id}"
                          placeholder="Dowód STAR (Sytuacja – działanie – rezultat), opcjonalnie..."
                          value="${escapeHtml(obsMap[ind.id]?.evidence || "")}"
                        />
                      </div>`;
                  })
                  .join("")}
                <div class="field-row">
                  <select class="final-pts" data-cid="${cid}">
                    <option value="">-- Wybierz ostateczną ocenę cząstkową --</option>
                    ${scalePoints
                      .map((pts) => `<option value="${pts}" ${existing.final_points === pts ? "selected" : ""}>${pts} pkt – ${scaleLabels[pts]}</option>`)
                      .join("")}
                  </select>
                  <button type="button" class="btn btn-outline btn-save-crit" data-cid="${cid}">Zapisz kryterium</button>
                </div>
              </div>`;
          })
          .join("")}
      </div>
      <button class="btn btn-primary" id="btn-assess-done">Zakończ ocenę kryteriów i przejdź dalej →</button>`;

    document.querySelectorAll(".btn-save-crit").forEach((btn) =>
      btn.addEventListener("click", async () => {
        try {
          const cid = btn.dataset.cid;
          const comp = compMap[cid];
          const indicators = comp.indicators.map((ind) => {
            const sel = document.querySelector(`input[name="ind-${ind.id}"]:checked`);
            const val = sel && sel.value !== "" ? Number(sel.value) : null;
            const evInput = document.querySelector(`.ind-evidence[data-ind-id="${ind.id}"]`);
            const evidence = evInput ? evInput.value.trim() || null : null;
            return { indicator_id: ind.id, observed_points: val, evidence };
          });
          const ptsSel = document.querySelector(`.final-pts[data-cid="${cid}"]`).value;
          await api(`/evaluations/${ev.id}/criteria/${cid}/assessment`, {
            method: "PUT",
            body: JSON.stringify({
              indicators,
              final_points: ptsSel ? Number(ptsSel) : null,
            }),
          });
          await openEvaluation(ev.id);
        } catch (err) {
          showAlert(err.message);
        }
      })
    );
    $("btn-assess-done").onclick = () => completeStep("competency_assessment");
    return;
  }

  if (step === "evaluation_interview") {
    body.innerHTML = `
      <h3>Rozmowa oceniająca</h3>
      <p class="muted">Skorzystaj z zakładki <strong>Asystent rozmowy</strong> po prawej stronie, aby wygenerować pytania otwarte i uporządkować argumenty.</p>
      <button class="btn btn-primary" id="btn-int-done">Potwierdź przeprowadzenie rozmowy i przejdź dalej →</button>`;
    $("btn-int-done").onclick = () => completeStep("evaluation_interview");
    return;
  }

  if (step === "decision") {
    const emp = state.employees.find((e) => e.id === ev.employee_id);
    const examVal = !ev.exam_status_recorded ? "true" : ev.exam_passed === null ? "na" : ev.exam_passed ? "true" : "false";
    const examBlock =
      ev.type === "first"
        ? `<label>Egzamin ze służby przygotowawczej
            <select id="dec-exam">
              <option value="true" ${examVal === "true" ? "selected" : ""}>Zaliczony</option>
              <option value="false" ${examVal === "false" ? "selected" : ""}>Niezaliczony</option>
              <option value="na" ${examVal === "na" ? "selected" : ""}>Nie dotyczy</option>
            </select>
          </label>`
        : "";
    const outcomeHtml = ev.outcome
      ? `<div class="alert ${ev.outcome.positive ? "alert-ok" : "alert-error"}">
           <strong>${ev.outcome.positive ? "OCENA POZYTYWNA" : "OCENA NEGATYWNA"}</strong>
           (średnia: ${ev.outcome.average}${ev.outcome.overall_label ? `, ${ev.outcome.overall_label}` : ""})
           <ul>${ev.outcome.reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join("")}</ul>
         </div>`
      : "";
    const showPromo = ev.type === "periodic" && emp?.is_civil_servant && ev.outcome?.positive;
    const promo = ev.rank_promotion_motion || {};
    const promoBlock = showPromo
      ? `<div class="promo-box">
           <h4>Część III — Wniosek o kolejny stopień służbowy (art. 89 ust. 1, opcjonalnie)</h4>
           <p class="muted small">Przysługuje urzędnikowi służby cywilnej po uzyskaniu pozytywnej oceny okresowej.</p>
           <div class="field-col">
             <label>Wnioskowany stopień służbowy
               <input type="text" id="promo-rank" value="${escapeHtml(promo.requested_rank || "")}" placeholder="np. III stopień służbowy" />
             </label>
             <label>Uzasadnienie wniosku (min. 10 znaków)
               <textarea id="promo-rationale" rows="2" placeholder="Wyróżniająca realizacja zadań, wysoka jakość analiz...">${escapeHtml(promo.rationale || "")}</textarea>
             </label>
           </div>
           <button type="button" class="btn btn-outline" id="btn-save-promo">Zapisz wniosek o kolejny stopień</button>
           ${ev.rank_promotion_motion ? `<span class="muted small" style="margin-left:8px;">✓ Zapisano wniosek (${escapeHtml(promo.requested_rank)})</span>` : ""}
         </div>`
      : "";

    body.innerHTML = `
      <h3>Zakończenie oceny i sporządzenie na piśmie</h3>
      ${examBlock}
      <label>Uzasadnienie oceny (obowiązkowe przy ocenie negatywnej)
        <textarea id="dec-just" rows="3">${escapeHtml(ev.justification || "")}</textarea>
      </label>
      <label>Wnioski rozwojowe / IPRZ ${ev.type === "periodic" ? "(obowiązkowe)" : "(fakultatywne)"}
        <textarea id="dec-iprz" rows="3">${escapeHtml(ev.development_plan || "")}</textarea>
      </label>
      <div class="field-row">
        <button class="btn btn-purple" id="btn-compute">Oblicz wynik oceny</button>
        <button class="btn btn-primary" id="btn-dec-done">Zatwierdź i przejdź do zapoznania →</button>
      </div>
      <div style="margin-top:12px;">${outcomeHtml}</div>
      ${promoBlock}`;
    if ($("btn-save-promo")) {
      $("btn-save-promo").onclick = async () => {
        try {
          showAlert("");
          await api(`/evaluations/${ev.id}/rank-promotion`, {
            method: "PUT",
            body: JSON.stringify({
              requested_rank: $("promo-rank").value.trim(),
              rationale: $("promo-rationale").value.trim(),
            }),
          });
          await openEvaluation(ev.id);
        } catch (err) {
          showAlert(err.message);
        }
      };
    }
    $("btn-compute").onclick = async () => {
      try {
        if (ev.type === "first") {
          const val = $("dec-exam").value;
          await api(`/evaluations/${ev.id}/first-eval-facts`, {
            method: "PUT",
            body: JSON.stringify({
              exam_applicable: val !== "na",
              exam_passed: val === "na" ? null : val === "true",
            }),
          });
        }
        await api(`/evaluations/${ev.id}/outcome`, {
          method: "POST",
          body: JSON.stringify({
            justification: $("dec-just").value || null,
            development_plan: $("dec-iprz").value || null,
          }),
        });
        await openEvaluation(ev.id);
      } catch (err) {
        showAlert(err.message);
      }
    };
    $("btn-dec-done").onclick = () => completeStep("decision");
    return;
  }

  if (step === "acknowledgement") {
    body.innerHTML = `
      <h3>Zapoznanie ocenianego z oceną i eksport dokumentacji</h3>
      <p class="muted">Pobierz arkusz w formacie PDF lub HTML, przekaż kopię ocenianemu i zakończ proces.</p>
      <div class="field-row">
        <button class="btn btn-outline" id="btn-dl-pdf">Pobierz PDF (z archiwizacją)</button>
        <button class="btn btn-outline" id="btn-dl-html">Podgląd HTML</button>
        <button class="btn btn-primary" id="btn-ack-done">Zakończ proces oceny ✓</button>
      </div>`;
    $("btn-dl-pdf").onclick = () => downloadDoc(ev.id, "pdf", true);
    $("btn-dl-html").onclick = () => downloadDoc(ev.id, "html", false);
    $("btn-ack-done").onclick = () => completeStep("acknowledgement");
  }
}

async function downloadDoc(evalId, fmt, archive) {
  const resp = await api(`/evaluations/${evalId}/document?fmt=${fmt}&archive=${archive}`);
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank");
}

async function renderHr() {
  $("panel-home").hidden = true;
  $("panel-wizard").hidden = true;
  $("panel-hr").hidden = false;
  $("hr-reminder-status").hidden = true;

  const dash = await api("/monitoring/dashboard");
  $("hr-stats").innerHTML = `
    <div class="stat-card"><div class="stat-val">${dash.total_evaluations}</div><div class="muted small">Wszystkie oceny</div></div>
    <div class="stat-card"><div class="stat-val">${dash.in_progress}</div><div class="muted small">W trakcie</div></div>
    <div class="stat-card"><div class="stat-val">${dash.completed}</div><div class="muted small">Zakończone</div></div>
    <div class="stat-card"><div class="stat-val">${dash.overdue_count}</div><div class="muted small">Zaległe terminy</div></div>`;

  const rows = dash.upcoming_deadlines
    .map(
      (d) => `<tr><td>${d.evaluation_id}</td><td>${d.label}</td><td>${d.due_date}</td><td>${d.overdue ? "ZALEGŁY" : `${d.days_remaining} dni`}</td></tr>`
    )
    .join("");
  $("hr-deadlines").innerHTML = rows
    ? `<table><tr><th>Ocena</th><th>Etap</th><th>Termin</th><th>Status</th></tr>${rows}</table>`
    : `<p class="muted">Brak nadchodzących terminów w zadanym oknie.</p>`;
}

// Event bindings
$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("login-error").hidden = true;
  try {
    const res = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username: $("login-username").value, password: $("login-password").value }),
    });
    state.token = res.access_token;
    localStorage.setItem("kompas_token", state.token);
    await bootstrapWorkspace();
  } catch (err) {
    $("login-error").textContent = err.message;
    $("login-error").hidden = false;
  }
});

document.querySelectorAll(".demo-accounts .chip").forEach((btn) =>
  btn.addEventListener("click", () => {
    $("login-username").value = btn.dataset.user;
    $("login-password").value = btn.dataset.pass;
    $("login-form").requestSubmit();
  })
);

$("btn-logout").onclick = () => {
  state.token = "";
  localStorage.removeItem("kompas_token");
  showView(false);
};
$("btn-home").onclick = renderHome;
$("btn-back-home").onclick = renderHome;
$("btn-hr").onclick = renderHr;
$("btn-toggle-deadlines").onclick = () => {
  const panel = $("wiz-deadlines-panel");
  panel.hidden = !panel.hidden;
};

$("btn-send-reminders").onclick = async () => {
  const sent = await api("/monitoring/reminders/send", { method: "POST" });
  $("hr-reminder-status").textContent = `Wysłano przypomnień: ${sent.length}`;
  $("hr-reminder-status").hidden = false;
};

$("btn-start-first").onclick = async () => {
  const empId = $("select-emp-first").value;
  if (!empId) return;
  try {
    showHomeAlert("");
    const ev = await api("/evaluations", {
      method: "POST",
      body: JSON.stringify({ employee_id: empId, evaluation_type: "first" }),
    });
    state.evaluations.unshift(ev);
    await openEvaluation(ev.id);
  } catch (err) {
    showHomeAlert(err.message);
  }
};

$("btn-start-periodic").onclick = async () => {
  const empId = $("select-emp-periodic").value;
  if (!empId) return;
  try {
    showHomeAlert("");
    const formOverride = $("select-form-periodic").value || null;
    const isPostNegative = $("chk-post-negative").checked;
    const ev = await api("/evaluations", {
      method: "POST",
      body: JSON.stringify({
        employee_id: empId,
        evaluation_type: "periodic",
        form_override: formOverride,
        is_post_negative_reevaluation: isPostNegative,
      }),
    });
    state.evaluations.unshift(ev);
    await openEvaluation(ev.id);
  } catch (err) {
    showHomeAlert(err.message);
  }
};

// Assistant tabs & chat
document.querySelectorAll(".tabs .tab").forEach((t) =>
  t.addEventListener("click", () => {
    document.querySelectorAll(".tabs .tab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    $("tab-formal").hidden = t.dataset.tab !== "formal";
    $("tab-conversation").hidden = t.dataset.tab !== "conversation";
  })
);

document.querySelectorAll(".qa-sample").forEach((btn) =>
  btn.addEventListener("click", () => {
    $("chat-input").value = btn.dataset.q;
    $("chat-form").requestSubmit();
  })
);

$("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $("chat-input").value.trim();
  if (!q) return;
  $("chat-input").value = "";
  const log = $("chat-log");
  log.innerHTML += `<div class="msg msg-user">${q}</div>`;
  try {
    const resp = await api("/assistant/ask", {
      method: "POST",
      body: JSON.stringify({
        question: q,
        mode: "formal",
        evaluation_id: state.activeEval?.id || null,
      }),
    });
    const cites = resp.citations.map((c) => `[${c.index}] ${c.source}`).join(" • ");
    const warns = resp.warnings.length ? `<div class="alert alert-warn">${resp.warnings.join(" ")}</div>` : "";
    log.innerHTML += `
      <div class="msg msg-ai">
        ${warns}
        <div>${resp.answer}</div>
        ${cites ? `<div class="citation">Źródła: ${cites}</div>` : ""}
      </div>`;
  } catch (err) {
    log.innerHTML += `<div class="msg msg-ai alert-error">${err.message}</div>`;
  }
  log.scrollTop = log.scrollHeight;
});

$("btn-load-prep").onclick = async () => {
  if (!state.activeEval) {
    $("prep-output").innerHTML = `<div class="alert alert-warn">Najpierw otwórz ocenę po lewej stronie.</div>`;
    return;
  }
  const prep = await api(`/assistant/conversation-prep/${state.activeEval.id}`);
  $("prep-output").innerHTML = `
    <h4>Pytania otwierające</h4>
    <ul>${prep.opening_questions.map((q) => `<li>${q}</li>`).join("")}</ul>
    <h4>Wątki wg kompetencji</h4>
    <ul>${prep.criterion_prompts.map((c) => `<li><strong>${c.competency}</strong> (${c.label}): ${c.guidance}</li>`).join("")}</ul>
    ${prep.ai_tips ? `<h4>Wskazówki AI</h4><p>${prep.ai_tips}</p>` : ""}
    <h4>Domknięcie rozmowy</h4>
    <ul>${prep.closing_points.map((p) => `<li>${p}</li>`).join("")}</ul>`;
};

if (state.token) {
  bootstrapWorkspace().catch(() => showView(false));
} else {
  showView(false);
}
