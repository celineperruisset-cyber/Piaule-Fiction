const STORAGE_KEY = "piaule-fiction-owner-product-objectives-v2";

const defaultState = {
  selectedDay: "day-3",
  filter: "all",
  statuses: {},
  objectiveStatuses: {},
  personalObjectiveStatuses: {},
  calendarStatuses: {},
  streamStatuses: {},
  journals: {}
};

function loadState() {
  try {
    const saved = JSON.parse(
      localStorage.getItem(STORAGE_KEY)
    );
    return { ...defaultState, ...saved };
  } catch {
    return { ...defaultState };
  }
}

let state = loadState();

const els = {
  dayStrip: document.querySelector("#dayStrip"),
  taskList: document.querySelector("#taskList"),
  dayDate: document.querySelector("#dayDate"),
  dayTitle: document.querySelector("#dayTitle"),
  dayOutcome: document.querySelector("#dayOutcome"),
  dayPercent: document.querySelector("#dayPercent"),
  dayTime: document.querySelector("#dayTime"),
  overallPercent: document.querySelector("#overallPercent"),
  overallBar: document.querySelector("#overallBar"),
  doneCount: document.querySelector("#doneCount"),
  doingCount: document.querySelector("#doingCount"),
  blockedCount: document.querySelector("#blockedCount"),
  dayNotes: document.querySelector("#dayNotes"),
  dayEvidence: document.querySelector("#dayEvidence"),
  saveFeedback: document.querySelector("#saveFeedback"),
  roadmapGrid: document.querySelector("#roadmapGrid"),
  processTable: document.querySelector("#processTable"),
  skillsGrid: document.querySelector("#skillsGrid"),
  rulesGrid: document.querySelector("#rulesGrid"),
  resourcesGrid: document.querySelector("#resourcesGrid"),
  dashboardObjectivesGrid: document.querySelector("#dashboardObjectivesGrid"),
  objectivesGrid: document.querySelector("#objectivesGrid"),
  personalFocus: document.querySelector("#personalFocus"),
  personalObjectivesGrid: document.querySelector("#personalObjectivesGrid"),
  calendarRoadmapGrid: document.querySelector("#calendarRoadmapGrid"),
  strategyGrid: document.querySelector("#strategyGrid"),
  strategySummary: document.querySelector("#strategySummary"),
  pageTitle: document.querySelector("#pageTitle"),
  toast: document.querySelector("#toast")
};

const statusLabels = {
  todo: "À faire",
  doing: "En cours",
  done: "Terminée",
  blocked: "Bloquée"
};

const typeLabels = {
  learn: "Apprendre",
  build: "Construire",
  research: "Rechercher",
  proof: "Preuve"
};

const viewTitles = {
  dashboard: "Vue d’ensemble propriétaire",
  objectives: "Objectifs produit",
  personal: "Missions de construction",
  processes: "Parcours d’un bien",
  skills: "Équipe d’agents",
  architecture: "Connecteurs & architecture",
  rules: "Cadre logiciel",
  resources: "Ressources métier",
  subscriptions: "Comptes & dépendances",
  strategy: "Pilotage du projet"
};

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function selectedDay() {
  return sprintDays.find((day) => day.id === state.selectedDay) || sprintDays[0];
}

function taskStatus(taskId) {
  return state.statuses[taskId] || initialTaskStatuses[taskId] || "todo";
}

function objectiveStatus(objectiveId) {
  return state.objectiveStatuses[objectiveId] || initialObjectiveStatuses[objectiveId] || "todo";
}

function personalObjectiveStatus(objectiveId) {
  return state.personalObjectiveStatuses[objectiveId]
    || initialPersonalObjectiveStatuses[objectiveId]
    || "todo";
}

function calendarStatus(itemId) {
  const item = calendarRoadmap.find((roadmapItem) => roadmapItem.id === itemId);
  return state.calendarStatuses[itemId] || item?.status || "todo";
}

function streamStatus(streamId) {
  const stream = projectStreams.find((item) => item.id === streamId);
  return state.streamStatuses[streamId] || stream?.status || "todo";
}

function duration(totalMinutes) {
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (!hours) return `${minutes} min`;
  return minutes ? `${hours} h ${String(minutes).padStart(2, "0")}` : `${hours} h`;
}

function percentage(tasks) {
  if (!tasks.length) return 0;
  const score = tasks.reduce((sum, item) => {
    const status = taskStatus(item.id);
    if (status === "done") return sum + 1;
    if (status === "doing") return sum + 0.35;
    return sum;
  }, 0);
  return Math.round((score / tasks.length) * 100);
}

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  window.setTimeout(() => els.toast.classList.remove("show"), 2300);
}

function renderDayStrip() {
  els.dayStrip.innerHTML = sprintDays.map((day) => {
    const progress = percentage(day.tasks);
    return `
      <button class="day-button ${day.id === state.selectedDay ? "active" : ""} ${progress === 100 ? "complete" : ""}"
        data-day="${day.id}" aria-label="Jour ${day.number}, ${day.title}, ${progress}%">
        <strong>J${day.number}</strong>
        <span>${day.shortDate}</span>
      </button>`;
  }).join("");

  els.dayStrip.querySelectorAll("[data-day]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedDay = button.dataset.day;
      saveState();
      renderDashboard();
    });
  });
}

function renderTask(taskItem, index) {
  const status = taskStatus(taskItem.id);
  const links = taskItem.resources.length
    ? `<h4>Ressources</h4><div class="resource-links">${taskItem.resources.map((resource) =>
        `<a href="${resource.url}" target="_blank" rel="noreferrer">${resource.label} ↗</a>`).join("")}</div>`
    : "";

  return `
    <article class="task-card" data-task-id="${taskItem.id}" data-status="${status}">
      <div class="task-main">
        <div class="task-number">${String(index + 1).padStart(2, "0")}</div>
        <div>
          <div class="task-title-row">
            <h3>${taskItem.title}</h3>
            <span class="badge ${taskItem.priority}">${taskItem.priority === "core" ? "Essentielle" : "Bonus"}</span>
            <span class="badge ${taskItem.type}">${typeLabels[taskItem.type]}</span>
          </div>
          <p class="task-summary">${duration(taskItem.minutes)} · ${taskItem.purpose}</p>
        </div>
        <div class="task-controls">
          <select aria-label="Statut de ${taskItem.title}" data-status-select="${taskItem.id}">
            ${Object.entries(statusLabels).map(([value, label]) =>
              `<option value="${value}" ${value === status ? "selected" : ""}>${label}</option>`).join("")}
          </select>
          <button class="details-toggle" data-toggle-task="${taskItem.id}" aria-label="Afficher le détail" aria-expanded="false">⌄</button>
        </div>
      </div>
      <div class="task-details">
        <h4>Actions</h4>
        <ol>${taskItem.steps.map((step) => `<li>${step}</li>`).join("")}</ol>
        <h4>Pourquoi cette tâche</h4>
        <p>${taskItem.purpose}</p>
        <h4>Critère de fin</h4>
        <p>${taskItem.doneWhen}</p>
        ${links}
      </div>
    </article>`;
}

function objectiveProgress(objective) {
  const status = objectiveStatus(objective.id);
  if (status === "done") return 100;
  if (status === "doing") return 50;
  if (status === "blocked") return 20;
  return 0;
}

function objectiveCard(objective, compact = false) {
  const status = objectiveStatus(objective.id);
  const progress = objectiveProgress(objective);
  return `
    <article class="objective-card ${compact ? "compact" : ""}" data-objective-id="${objective.id}" data-status="${status}">
      <div class="objective-head">
        <div>
          <p class="eyebrow">${objective.audience}</p>
          <h3>${objective.title}</h3>
        </div>
        <select aria-label="Statut de ${objective.title}" data-objective-status="${objective.id}">
          ${Object.entries(statusLabels).map(([value, label]) =>
            `<option value="${value}" ${value === status ? "selected" : ""}>${label}</option>`).join("")}
        </select>
      </div>
      <p class="objective-purpose">${objective.purpose}</p>
      <div class="objective-progress"><i style="width:${progress}%"></i></div>
      <ul>${objective.capabilities.map((capability) => `<li>${capability}</li>`).join("")}</ul>
      ${compact ? "" : `<p class="objective-done"><strong>Critère de résultat :</strong> ${objective.doneWhen}</p>`}
    </article>`;
}

function objectiveGroups(compact = false) {
  return productPhases.map((phase) => {
    const objectives = productObjectives.filter((objective) => objective.phase === phase.id);
    return `
      <section class="objective-phase">
        <div class="objective-phase-heading">
          <p class="eyebrow">PHASE ${phase.number}</p>
          <h3>${phase.title}</h3>
          <p>${phase.purpose}</p>
          ${compact ? "" : `<p class="objective-phase-done"><strong>Phase terminée lorsque :</strong> ${phase.doneWhen}</p>`}
        </div>
        <div class="objectives-grid">${objectives.map((objective) => objectiveCard(objective, compact)).join("")}</div>
      </section>`;
  }).join("");
}

function bindObjectiveEvents(root = document) {
  root.querySelectorAll("[data-objective-status]").forEach((select) => {
    select.addEventListener("change", () => {
      state.objectiveStatuses[select.dataset.objectiveStatus] = select.value;
      saveState();
      renderDashboard();
      if (document.querySelector("#objectivesView")?.classList.contains("active")) renderObjectives();
    });
  });
}

function renderObjectives() {
  if (!els.objectivesGrid) return;
  els.objectivesGrid.innerHTML = objectiveGroups();
  bindObjectiveEvents(els.objectivesGrid);
}

function renderDashboardObjectives() {
  if (!els.dashboardObjectivesGrid) return;
  els.dashboardObjectivesGrid.innerHTML = objectiveGroups(true);
  bindObjectiveEvents(els.dashboardObjectivesGrid);
}

function renderCalendarRoadmap() {
  if (!els.calendarRoadmapGrid) return;
  els.calendarRoadmapGrid.innerHTML = calendarRoadmap.map((item, index) => {
    const status = calendarStatus(item.id);
    return `
      <article class="calendar-roadmap-card" data-status="${status}">
        <div class="calendar-roadmap-number">${String(index + 1).padStart(2, "0")}</div>
        <div class="calendar-roadmap-body">
          <div class="calendar-roadmap-head">
            <div><span class="roadmap-stage">${item.stage}</span><h3>${item.title}</h3></div>
            <select aria-label="Statut de ${item.title}" data-calendar-status="${item.id}">
              ${Object.entries(statusLabels).map(([value, label]) => `<option value="${value}" ${value === status ? "selected" : ""}>${label}</option>`).join("")}
            </select>
          </div>
          <p>${item.description}</p>
          <small><strong>Preuve attendue :</strong> ${item.proof}</small>
        </div>
      </article>`;
  }).join("");

  els.calendarRoadmapGrid.querySelectorAll("[data-calendar-status]").forEach((select) => {
    select.addEventListener("change", () => {
      state.calendarStatuses[select.dataset.calendarStatus] = select.value;
      saveState();
      renderCalendarRoadmap();
      showToast("Étape agenda mise à jour");
    });
  });
}

function personalObjectiveCard(objective, index) {
  const status = personalObjectiveStatus(objective.id);
  return `
    <article class="personal-objective-card" data-status="${status}">
      <div class="personal-objective-number">${String(index + 1).padStart(2, "0")}</div>
      <div class="personal-objective-body">
        <div class="personal-objective-head">
          <div>
            <p class="eyebrow">${objective.stage}</p>
            <h3>${objective.title}</h3>
          </div>
          <select aria-label="Statut de ${objective.title}" data-personal-status="${objective.id}">
            ${Object.entries(statusLabels).map(([value, label]) =>
              `<option value="${value}" ${value === status ? "selected" : ""}>${label}</option>`).join("")}
          </select>
        </div>
        <p><strong>Pourquoi :</strong> ${objective.why}</p>
        <p><strong>Première action :</strong> ${objective.steps[0]}</p>
        <details class="personal-steps">
          <summary>Voir les missions de cette étape</summary>
          <ol>${objective.steps.map((step) => `<li>${step}</li>`).join("")}</ol>
        </details>
        <p class="personal-done"><strong>Pour considérer cette étape terminée :</strong> ${objective.doneWhen}</p>
      </div>
    </article>`;
}

function bindPersonalObjectiveEvents() {
  els.personalObjectivesGrid?.querySelectorAll("[data-personal-status]").forEach((select) => {
    select.addEventListener("change", () => {
      state.personalObjectiveStatuses[select.dataset.personalStatus] = select.value;
      saveState();
      renderPersonalObjectives();
      showToast("Objectif personnel mis à jour");
    });
  });
}

function renderPersonalObjectives() {
  if (!els.personalObjectivesGrid || !els.personalFocus) return;
  const current = personalObjectives.find((objective) => {
    const status = personalObjectiveStatus(objective.id);
    return status === "doing" || status === "todo";
  }) || personalObjectives[personalObjectives.length - 1];

  els.personalFocus.innerHTML = `
    <p class="eyebrow">PROCHAIN FOCUS</p>
    <h3>${current.title}</h3>
    <p>${current.steps[0]}</p>
    <span>${current.why}</span>`;
  els.personalObjectivesGrid.innerHTML = personalObjectives
    .map((objective, index) => personalObjectiveCard(objective, index))
    .join("");
  bindPersonalObjectiveEvents();
}

function renderStrategy() {
  if (!els.strategyGrid || !els.strategySummary) return;
  const counts = projectStreams.reduce((acc, stream) => {
    acc[streamStatus(stream.id)] += 1;
    return acc;
  }, { todo: 0, doing: 0, done: 0, blocked: 0 });
  els.strategySummary.innerHTML = `
    <article class="strategy-summary-card"><strong>${projectStreams.length}</strong><span>chantiers suivis</span></article>
    <article class="strategy-summary-card active"><strong>${counts.doing}</strong><span>en construction</span></article>
    <article class="strategy-summary-card next"><strong>${counts.todo}</strong><span>à cadrer ensuite</span></article>
    <article class="strategy-summary-card done"><strong>${counts.done}</strong><span>structurés</span></article>`;
  els.strategyGrid.innerHTML = projectStreams.map((stream, index) => {
    const status = streamStatus(stream.id);
    return `
      <article class="strategy-card ${stream.color}" data-status="${status}">
        <div class="strategy-card-top">
          <span class="strategy-number">${String(index + 1).padStart(2, "0")}</span>
          <select aria-label="Statut de ${stream.title}" data-stream-status="${stream.id}">
            ${Object.entries(statusLabels).map(([value, label]) => `<option value="${value}" ${value === status ? "selected" : ""}>${label}</option>`).join("")}
          </select>
        </div>
        <p class="eyebrow">${stream.label}</p>
        <h3>${stream.title}</h3>
        <div class="strategy-copy"><p><strong>Où nous en sommes</strong>${stream.now}</p><p><strong>Prochaine action</strong>${stream.next}</p></div>
        <p class="strategy-proof"><strong>Résultat attendu :</strong> ${stream.proof}</p>
      </article>`;
  }).join("");
  els.strategyGrid.querySelectorAll("[data-stream-status]").forEach((select) => {
    select.addEventListener("change", () => {
      state.streamStatuses[select.dataset.streamStatus] = select.value;
      saveState();
      renderStrategy();
      showToast("Chantier mis à jour");
    });
  });
}

function bindTaskEvents() {
  document.querySelectorAll("[data-status-select]").forEach((select) => {
    select.addEventListener("change", () => {
      state.statuses[select.dataset.statusSelect] = select.value;
      saveState();
      renderDashboard();
    });
  });

  document.querySelectorAll("[data-toggle-task]").forEach((button) => {
    button.addEventListener("click", () => {
      const card = button.closest(".task-card");
      const isOpen = card.classList.toggle("open");
      button.textContent = isOpen ? "⌃" : "⌄";
      button.setAttribute("aria-expanded", String(isOpen));
    });
  });
}

function renderDashboard() {
  renderDashboardObjectives();
  renderGlobalStats();
}

function renderGlobalStats() {
  const counts = productObjectives.reduce((acc, objective) => {
    acc[objectiveStatus(objective.id)] += 1;
    return acc;
  }, { todo: 0, doing: 0, done: 0, blocked: 0 });
  const score = productObjectives.reduce((total, objective) => {
    const status = objectiveStatus(objective.id);
    if (status === "done") return total + 1;
    if (status === "doing") return total + 0.5;
    return total;
  }, 0);
  const overall = productObjectives.length
    ? Math.round((score / productObjectives.length) * 100)
    : 0;

  els.overallPercent.textContent = `${overall}%`;
  els.overallBar.style.width = `${overall}%`;
  els.doneCount.textContent = counts.done;
  els.doingCount.textContent = counts.doing;
  els.blockedCount.textContent = counts.blocked;
}

function renderRoadmap() {
  els.roadmapGrid.innerHTML = sprintDays.map((day) => {
    const core = day.tasks.filter((item) => item.priority === "core");
    const bonus = day.tasks.filter((item) => item.priority === "bonus");
    const progress = percentage(day.tasks);
    return `
      <article class="roadmap-card" data-roadmap-day="${day.id}" tabindex="0" role="button">
        <header>
          <div>
            <p class="eyebrow">JOUR ${day.number} · ${day.shortDate.toUpperCase()}</p>
            <h3>${day.title}</h3>
          </div>
          <div>
            <strong>${progress}%</strong>
            <div class="mini-progress"><i style="width:${progress}%"></i></div>
          </div>
        </header>
        <p>${day.outcome}</p>
        <p><strong>Livrable :</strong> ${day.deliverable}</p>
        <div class="roadmap-meta">
          <span>${core.length} essentielles</span>
          <span>${bonus.length} bonus</span>
          <span>${duration(day.tasks.reduce((sum, item) => sum + item.minutes, 0))}</span>
        </div>
      </article>`;
  }).join("");

  const openDay = (dayId) => {
    state.selectedDay = dayId;
    saveState();
    switchView("dashboard");
    renderDashboard();
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  document.querySelectorAll("[data-roadmap-day]").forEach((card) => {
    card.addEventListener("click", () => openDay(card.dataset.roadmapDay));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") openDay(card.dataset.roadmapDay);
    });
  });
}

function renderProcesses() {
  const modeLabel = { agent: "Agent", rule: "Règle", human: "Humain" };
  els.processTable.innerHTML = `
    <table>
      <thead><tr><th>Étape</th><th>Ce que le système peut assister</th><th>Mécanisme</th><th>Portée</th></tr></thead>
      <tbody>${candidateProcesses.map(([name, action, modes, scope]) => `
        <tr>
          <td><strong>${name}</strong></td>
          <td>${action}</td>
          <td><div class="mode-list">${modes.map((mode) => `<span class="mode ${mode}">${modeLabel[mode]}</span>`).join("")}</div></td>
          <td class="${scope === "MVP" || scope.includes("MVP") ? "scope-mvp" : "scope-later"}">${scope}</td>
        </tr>`).join("")}</tbody>
    </table>`;
}

function renderSkills() {
  els.skillsGrid.innerHTML = skillMap.map((skill) => `
    <article class="skill-card">
      <p class="eyebrow">${skill.days}</p>
      <h3>${skill.name}</h3>
      <ul>${skill.proof.map((proof) => `<li>${proof}</li>`).join("")}</ul>
      <div class="confidence">
        <span>Cible de préparation</span>
        <div class="confidence-track"><i style="width:${skill.target}%"></i></div>
        <strong>${skill.target}%</strong>
      </div>
    </article>`).join("");
}

function renderResources() {
  els.resourcesGrid.innerHTML = resourceLibrary.map(([kind, title, description, resource]) => `
    <article class="resource-card">
      <span class="resource-kind">${kind}</span>
      <h3>${title}</h3>
      <p>${description}</p>
      <a href="${resource.url}" target="_blank" rel="noreferrer">Ouvrir la ressource ↗</a>
    </article>`).join("");
}

function renderRules() {
  els.rulesGrid.innerHTML = frenchRules.map((rule) => `
    <article class="rule-card">
      <div class="rule-meta">
        <strong>${rule.id}</strong>
        ${rule.kind}<br />
        Vérifiée le ${rule.verified}
      </div>
      <div class="rule-body">
        <h3>${rule.title}</h3>
        <p>${rule.statement}</p>
        <div class="rule-links">
          ${rule.sources.map((source) => `<a href="${source.url}" target="_blank" rel="noreferrer">${source.label} ↗</a>`).join("")}
        </div>
      </div>
      <div class="rule-test">
        <strong>Implémentation</strong>
        <p>${rule.enforcement}</p>
        <strong style="margin-top:10px">Test attendu</strong>
        <p>${rule.test}</p>
      </div>
    </article>`).join("");
}

function switchView(viewName) {
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  document.querySelector(`#${viewName}View`).classList.add("active");
  document.querySelectorAll(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.view === viewName));
  els.pageTitle.textContent = viewTitles[viewName];
  document.querySelector(".sidebar").classList.remove("open");
  if (viewName === "objectives") renderObjectives();
  if (viewName === "personal") renderPersonalObjectives();
  if (viewName === "strategy") renderStrategy();
}

function saveJournal() {
  const day = selectedDay();
  state.journals[day.id] = {
    notes: els.dayNotes.value.trim(),
    evidence: els.dayEvidence.value.trim()
  };
  saveState();
  els.saveFeedback.textContent = "Journal enregistré sur cet appareil.";
  showToast("Journal enregistré");
}

async function copySummary() {
  const done = productObjectives.filter((item) => objectiveStatus(item.id) === "done");
  const doing = productObjectives.filter((item) => objectiveStatus(item.id) === "doing");
  const blocked = productObjectives.filter((item) => objectiveStatus(item.id) === "blocked");
  const summary = [
    "Piaule Fiction — suivi par objectifs produit",
    `Objectifs terminés : ${done.length}/${productObjectives.length}`,
    "",
    `Terminés : ${done.length ? done.map((item) => item.title).join(" | ") : "aucun"}`,
    `En cours : ${doing.length ? doing.map((item) => item.title).join(" | ") : "aucun"}`,
    `Bloqués : ${blocked.length ? blocked.map((item) => item.title).join(" | ") : "aucun"}`,
    "",
    "Donne-moi maintenant le prochain objectif prioritaire et aide-moi à avancer étape par étape."
  ].join("\n");

  try {
    await navigator.clipboard.writeText(summary);
    showToast("Bilan copié — colle-le dans notre conversation");
  } catch {
    window.prompt("Copie ce bilan :", summary);
  }
}

function exportProgress() {
  const payload = {
    exportedAt: new Date().toISOString(),
    project: "Piaule Fiction",
    tracking: "product-objectives",
    state
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `piaule-fiction-progress-${new Date().toISOString().slice(0, 10)}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
  showToast("Sauvegarde JSON exportée");
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

document.querySelector("#copySummary").addEventListener("click", copySummary);
document.querySelector("#exportProgress").addEventListener("click", exportProgress);
document.querySelector("#menuToggle").addEventListener("click", () => document.querySelector(".sidebar").classList.toggle("open"));

renderDashboard();
renderCalendarRoadmap();
renderObjectives();
renderPersonalObjectives();
renderStrategy();
renderProcesses();
renderSkills();
renderRules();
renderResources();
