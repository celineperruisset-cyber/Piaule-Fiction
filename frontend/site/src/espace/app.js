/* ===================== Espace participant =====================
   Arrive ici après la création du compte (accueil).
   Si une recherche a été tapée sur l'accueil, elle est reprise telle quelle : on ne la redemande pas.
   Sinon, la première étape est de l'écrire. */
const $ = id => document.getElementById(id);
const store = {
  get(k){ try { return JSON.parse(localStorage.getItem(k)); } catch (x) { return null; } },
  set(k, v){ try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, JSON.stringify(v)); } catch (x) {} }
};
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
const fmt = n => n.toLocaleString("fr-FR");
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

/* @@PARSE@@ (repris de l'accueil au moment de la construction) */

const EX = ["Un studio à Lyon, 600 € max, près d'un métro, pour septembre", "Une coloc à Paris pour mon alternance, 750 € max", "Un T1 meublé à Bordeaux, calme, moins de 650 €", "Une chambre à Lille près de la fac, 450 € max"];

/* Le menu du compte */
$("me-b").addEventListener("click", () => { const o = $("me-m").hidden; $("me-m").hidden = !o; $("me-b").setAttribute("aria-expanded", String(o)); });
document.addEventListener("pointerdown", e => { if (!$("me").contains(e.target)) { $("me-m").hidden = true; $("me-b").setAttribute("aria-expanded", "false"); } });
$("me-out").addEventListener("click", async () => {
  try { await fetch("api/compte", {method: "POST", credentials: "same-origin", headers: {"Content-Type": "application/json"}, body: JSON.stringify({action: "deconnexion"})}); } catch (x) {}
  store.set("pf-moi", null); location.href = "index.html";
});

/* Plusieurs recherches : la liste, et celle qui est ouverte (pf-recherche reste l'active, lue partout) */
const R = {
  all(){ let l = store.get("pf-recherches"); const q = store.get("pf-recherche"); if (!Array.isArray(l)) l = q ? [q] : []; if (q && !l.includes(q)) l.unshift(q); return l.filter(Boolean).slice(0, 4); },
  save(l, q){ store.set("pf-recherches", l); store.set("pf-recherche", q || null); }
};
let mode = "edit";
let backendSearchText = "";
let backendListings = null;
const count = c => Math.max(9, Math.round(c.budget / 9) - c.extras.length * 9 - (c.when ? 6 : 0));
/* Ta recherche, réécrite par l'Agent : tes mots en clair, ses ajouts en roux */
const ADDS = [["Meublé", "meublé"], ["Calme", "calme"], ["Balcon", "avec balcon"], ["Lumineux", "lumineux"], ["Près des transports", "près d'un tram ou d'un métro"], ["Animaux acceptés", "animaux acceptés"], ["Vélo ou parking", "avec un parking vélo"]];
function better(c){
  const Y = s => `<mark class="y">${esc(s)}</mark>`, A = s => `<mark class="a">${esc(s)}</mark>`;
  const what = {Studio: "un studio", T1: "un T1", T2: "un T2", Coloc: "une chambre en colocation", Chambre: "une chambre"}[c.type] || "un studio";
  const m2 = {T2: 30, T1: 20, Coloc: 10, Chambre: 10}[c.type] || 18;
  const tr = c.extras.includes("Près des transports") ? Y("près des transports") : A("à moins de 25 min du centre en transports");
  const ex = c.extras.filter(x => x !== "Près des transports").map(x => x.toLowerCase());
  return `Je cherche ${Y(what)} à ${Y(c.city)}, ${Y(fmt(c.budget) + " € max")} ${A("charges comprises")}, ${c.when ? Y(c.when.toLowerCase()) : A("dès que possible")}, ${tr}. `
    + (ex.length ? `Je tiens à : ${ex.map(Y).join(", ")}. ` : "")
    + `${A(`Au moins ${m2} m²`)}, ${A("DPE de A à D")}, ${A("une visite avant de signer")}. ${A("J'écarte les annonces qui demandent de l'argent avant la visite, et les loyers anormalement bas.")}`;
}
function rsList(){
  const l = R.all(), cur = store.get("pf-recherche"), i = l.indexOf(cur);
  $("rs-n").textContent = l.length ? `${l.length} sur 4` : "";
  $("rh-k").textContent = l.length > 1 ? `Ta recherche · ${i + 1} sur ${l.length}` : "Ta recherche";
  $("rs-l").innerHTML = l.map((q, k) => { const c = parse(q), on = q === cur;
    return `<div class="rs-i${on ? " on" : ""}"><button type="button" class="rs-b" data-q="${k}"><img src="photos/annonce-${[6, 2, 4, 8][k % 4]}.jpg" alt=""><span><b>${esc(typeLabel(c.type))} à ${esc(c.city)}</b><small>${fmt(c.budget)} € max${c.when ? " · " + esc(c.when.replace(/^Pour /, "")) : ""}${on ? "" : " · " + count(c) + " annonces"}</small></span>${on ? "<em>Ouverte</em>" : ""}</button>${l.length > 1 ? `<button type="button" class="rs-x" data-x="${k}" aria-label="Retirer cette recherche"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7l10 10M17 7L7 17"/></svg></button>` : ""}</div>`; }).join("");
  $("rs-new").hidden = l.length >= 4;
}
$("rs-l").addEventListener("click", e => {
  const l = R.all(), b = e.target.closest("[data-q],[data-x]"); if (!b) return;
  if (b.dataset.x != null) { const cur = store.get("pf-recherche"), gone = l.splice(+b.dataset.x, 1)[0]; R.save(l, gone === cur ? l[0] : cur); }
  else R.save(l, l[+b.dataset.q]);
  render();
  void syncBackendSearch(store.get("pf-recherche"));
});
$("pr-adds").addEventListener("click", e => {
  const b = e.target.closest("[data-add]"); if (!b) return;
  const l = R.all(), cur = store.get("pf-recherche"), x = ADDS.find(a => a[0] === b.dataset.add)[1];
  const v = cur.trim().replace(/[.\s]+$/, "") + ", " + x; l[l.indexOf(cur)] = v; R.save(l, v); render();
});
$("rs-new").addEventListener("click", () => {
  mode = "new"; show(0); clearTimeout(tyT); inp.value = ""; syncHas(); $("ideas").hidden = false;
  ph.textContent = "Ta nouvelle recherche : une autre ville, un autre budget…";
  inp.focus();
});

function render(){
  const q = store.get("pf-recherche");
  const has = !!(q && q.trim());
  /* Le champ reste au centre : ta recherche de l'accueil s'y réécrit tout de suite */
  $("c-ask").hidden = false; $("ideas").hidden = has;
  $("rech-empty").hidden = has; ["quote", "tiles", "chips"].forEach(k => $(k).hidden = !has); $("edit").hidden = !has;
  marks(has); rsList();
  if (!has) {
    $("hi-em").textContent = "on s'y met ?";
    $("hi-p").textContent = "Première étape : dis ce que tu cherches. Tes agents s'occupent du reste.";
    $("live").hidden = true;
    $("ag-pill").className = "pill wait"; $("ag-pill").textContent = "En attente de ta recherche";
    $("c-ag").classList.remove("on");
    $("ag-b").textContent = "Trois agents, une mission."; $("ag-p").textContent = "Dès que tu as écrit ta recherche, ils savent quoi chercher.";
    wall(parse(EX[0]), true);
    startTyping();
    return;
  }
  const c = parse(q);
  $("hi-em").textContent = "tes agents sont prêts.";
  $("hi-p").textContent = "Ta recherche est bien là. Précise-la quand tu veux, tes agents suivront.";
  retype(q.trim());
  $("live").hidden = false;
  $("live-t").textContent = `${typeLabel(c.type)} à ${c.city}, ${fmt(c.budget)} € max`;
  $("quote").textContent = `« ${q.trim()} »`;
  const T = [["Où", c.city], ["Quoi", typeLabel(c.type)], ["Budget max", `${fmt(c.budget)} €`], ["Pour quand", c.when ? c.when.replace(/^Pour /, "") : ""]];
  $("tiles").innerHTML = T.map(([k, v]) => `<div class="tile${v ? "" : " empty"}"><small>${k}</small><b>${esc(v || "Dès que possible")}</b></div>`).join("");
  $("chips").innerHTML = c.extras.map(x => `<span>${esc(x)}</span>`).join("") || '<span class="add">Aucun critère en plus</span>';
  $("pr-txt").innerHTML = better(c);
  $("pr-adds").innerHTML = ADDS.filter(([l]) => !c.extras.includes(l)).slice(0, 6).map(([l]) => `<button type="button" data-add="${esc(l)}">+ ${esc(l)}</button>`).join("");
  $("pr-cnt").textContent = count(c);
  $("ag-pill").className = "pill ok"; $("ag-pill").textContent = "Prêts";
  $("c-ag").classList.add("on");
  $("ag-b").textContent = "Ils savent quoi chercher.";
  $("ag-p").textContent = `${typeLabel(c.type)} à ${c.city}, jusqu'à ${fmt(c.budget)} €. Ils démarrent à l'ouverture du service.`;
  wall(c, false, backendSearchText === q ? backendListings : null);
}

/* Le premier branchement réel : la recherche est enregistrée côté serveur,
   puis le flux d'annonces est relu avec la session du candidat. Le localStorage
   reste un cache de transition pour ne pas casser l'expérience visuelle. */
async function syncBackendSearch(q){
  if (!q || !q.trim()) return;
  const c = parse(q), type = ({Studio: "studio", T1: "apartment", T2: "apartment", Coloc: "shared", Chambre: "room"})[c.type] || "any";
  backendSearchText = q;
  backendListings = null;
  try {
    const profile = await fetch("api/recherches", {method: "POST", credentials: "same-origin", headers: {"Content-Type": "application/json"}, body: JSON.stringify({texte: q, cities: [c.city], max_budget_eur: c.budget, housing_type: type})});
    if (!profile.ok) return;
    const feed = await fetch("api/annonces", {credentials: "same-origin", headers: {"Accept": "application/json"}});
    if (feed.ok) backendListings = await feed.json();
    if (store.get("pf-recherche") === q) render();
  } catch (x) {
    /* Le prototype garde son aperçu local si le backend est indisponible. */
  }
}

/* Les onglets : le fil relie les étapes, la coche dit ce qui est fait, l'onglet ouvert montre une seule carte */
const TABS = [...document.querySelectorAll("#rail [role=tab]")];
const CHECK = '<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';
let picked = -1;
function marks(has){
  const pro = store.get("pf-profil") || {}, proOk = !!pro.situation;
  const done = [false, proOk, has, false, false, false];
  TABS.forEach((t, k) => t.classList.toggle("done", done[k]));
  $("pro-pill").className = proOk ? "pill ok" : "pill wait"; $("pro-pill").textContent = proOk ? "Complet" : "À compléter";
  /* Le tableau de bord suit ta recherche */
  const c = has ? parse(store.get("pf-recherche")) : null;
  $("k-bud").textContent = c ? `${fmt(c.budget)} €` : "–"; $("k-city").textContent = c ? c.city : "–"; $("k-type").textContent = c ? typeLabel(c.type) : "–";
  if (c) { const Q = QUART[c.city] || GENERIC; $("f-rent").textContent = `${fmt(Math.max(280, Math.round((c.budget - 10) / 5) * 5))} €`; $("f-what").textContent = `${typeLabel(c.type)} · ${Q[0]}`; }
  /* Les pages des onglets */
  const m = store.get("pf-moi") || {}, nm = (pro.prenom || m.prenom || "toi").trim();
  $("pp-name").textContent = nm.charAt(0).toUpperCase() + nm.slice(1); $("fd-name").textContent = $("pp-name").textContent;
  $("pp-line").textContent = proOk ? [pro.situation, pro.ville && `vit à ${pro.ville}`, pro.revenus].filter(Boolean).join(" · ") : "Complète-le une fois, il accompagne chacune de tes candidatures.";
  const pct = 20 + ["tel", "ville", "situation", "revenus"].filter(k => pro[k]).length * 20; $("pp-pct").textContent = `${pct} %`;
  const TG = [pro.situation, pro.revenus && `Revenus ${pro.revenus.toLowerCase()}`, pro.ville && `Vit à ${pro.ville}`, "E-mail vérifié"].filter(Boolean);
  $("pp-tags").innerHTML = TG.map(t => `<span>${esc(t)}</span>`).join("") + (proOk ? "" : '<span class="add">+ Ta situation</span><span class="add">+ Tes revenus</span>');
  $("rh-t").textContent = c ? `${typeLabel(c.type)} à ${c.city}` : "À écrire"; $("rh-bud").textContent = c ? `${fmt(c.budget)} €` : "–";
  $("sd-ag").textContent = has ? "Prêts, démarrent à l'ouverture" : "En attente de ta recherche"; $("sd-ag").classList.toggle("ok", has);
  $("sd-st").textContent = proOk ? pro.situation : "Candidat·e";
  show(picked < 0 ? 0 : picked, false);
}
function show(k, user = true){
  if (user) picked = k;
  TABS.forEach((t, j) => { const on = j === k; t.setAttribute("aria-selected", String(on)); t.tabIndex = on ? 0 : -1; $(t.getAttribute("aria-controls")).hidden = !on; });
  if (innerWidth <= 900) { const r = $("rail"), t = TABS[k]; r.scrollTo({left: t.offsetLeft - (r.clientWidth - t.offsetWidth) / 2, behavior: user && !reduced ? "smooth" : "auto"}); }
  if (user && innerWidth <= 900) { const y = document.querySelector(".dash").getBoundingClientRect().top + scrollY - 70; if (scrollY > y) scrollTo({top: y}); }
}
document.querySelector(".dash .col").addEventListener("click", e => { const g = e.target.closest("[data-go]"); if (!g) return; const k = +g.dataset.go; if (k === 2 && !store.get("pf-recherche")) { inp.focus(); return; } show(k); });
TABS.forEach((t, k) => t.addEventListener("click", () => show(k)));
$("sd-out").addEventListener("click", () => $("me-out").click());
document.querySelectorAll(".side-w [data-go]").forEach(b => b.addEventListener("click", () => show(+b.dataset.go)));
$("rail").addEventListener("keydown", e => {
  const k = TABS.findIndex(t => t.getAttribute("aria-selected") === "true"), d = /Right|Down/.test(e.key) ? 1 : /Left|Up/.test(e.key) ? -1 : 0;
  if (!d) return; e.preventDefault(); const n = (k + d + TABS.length) % TABS.length; show(n); TABS[n].focus();
});

/* Les petites courbes et le calendrier du tableau de bord */
const BARS = [[.4,.7,.5,.9,.6,.8,.45,.95,.7,.55,.85,.6], [.3,.5,.8,.6,.9,.4,.7,.5,.85,.65,.75,.9]];
["sb-1", "sb-2"].forEach((id, k) => $(id).innerHTML = BARS[k].map((v, j) => `<i style="--h:${v};--d:${j * .04}s"></i>`).join(""));
(function cal(){
  const d = new Date(), y = d.getFullYear(), m = d.getMonth(), today = d.getDate();
  const M = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"];
  $("cal-m").textContent = `${M[m]} ${y}`;
  const first = (new Date(y, m, 1).getDay() + 6) % 7, n = new Date(y, m + 1, 0).getDate();
  const vis = [today + 5, today + 8].filter(x => x <= n), open = Math.min(n, today + 12);
  let h = ["Lu", "Ma", "Me", "Je", "Ve", "Sa", "Di"].map(x => `<small>${x}</small>`).join("") + "<span></span>".repeat(first);
  for (let i = 1; i <= n; i++) h += `<span class="${i === today ? "td" : vis.includes(i) ? "vi" : i === open ? "op" : i < today ? "past" : ""}">${i}</span>`;
  $("cal-g").innerHTML = h; $("cal-g2").innerHTML = h; $("cal-m2").textContent = `${M[m]} ${y}`;
  const J = ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."], fmtD = x => { const t = new Date(y, m, x); return `${J[t.getDay()]} ${x} ${M[m].toLowerCase()}`; };
  const V = [[3, "T2 lumineux", vis[0], "18 h 30"], [5, "Studio rénové", vis[1], "12 h 15"]].filter(v => v[2]);
  $("vv-tbl").innerHTML = '<div class="tr th"><span>Date</span><span>Logement</span><span>Heure</span><span>Statut</span></div>' + V.concat([[1, "Chambre en coloc", Math.min(n, today + 10), "17 h 00"]]).map(([ph, t, x, hr], k) => `<div class="tr${k ? "" : " hot"}"><span>${fmtD(x)}</span><span><img src="photos/annonce-${ph}.jpg" alt=""><b>${t}</b></span><span>${hr}</span><span><em class="${k === 2 ? "" : "ok"}">${k === 2 ? "En attente" : "Confirmée"}</em></span></div>`).join("");
  $("vis-l").innerHTML = V.map(([ph, t, x, hr]) => `<button type="button" class="vi-i" data-go="5"><img src="photos/annonce-${ph}.jpg" alt=""><span><em>Exemple</em><b>${t}</b><small>${fmtD(x)} · ${hr}</small></span></button>`).join("");
})();

/* Ton dossier : un grand dossier, les pièces rangées dedans, on en sort une pour la voir */
const PIECES = [
  {t: "Pièce d'identité", d: "Recto et verso, carte ou passeport", ck: "Authenticité, date de validité, ton nom", ic: '<rect x="3" y="5" width="18" height="14" rx="2.5"/><circle cx="9" cy="11" r="2.2"/><path d="M5.8 16c.6-1.6 1.8-2.4 3.2-2.4s2.6.8 3.2 2.4M14.5 10h4M14.5 13.5h3"/>'},
  {t: "Justificatif d'activité", d: "Contrat de travail, d'alternance, ou certificat de scolarité", ck: "Dates, employeur ou école, cohérence avec ton profil", ic: '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M10 12h5M10 15.5h5"/>', hot: true},
  {t: "Tes revenus", d: "Tes dernières fiches de paie, ou ton attestation de bourse", ck: "Montants, dates récentes, même nom partout", ic: '<path d="M6 3h12v18l-2-1.4-2 1.4-2-1.4-2 1.4-2-1.4L6 21z"/><path d="M9 8h6M9 11.5h6M9 15h3"/>'},
  {t: "Ton garant", d: "Visale, gratuit, ou une personne qui se porte garante", ck: "Visa Visale valide, ou les pièces de ton garant", ic: '<path d="M12 3l7.5 3v5.5c0 4.6-3.2 8.2-7.5 9.5-4.3-1.3-7.5-4.9-7.5-9.5V6z"/><path d="M8.8 12.2l2.2 2.2 4.3-4.3"/>'},
  {t: "Avis d'imposition", d: "Le tien, ou celui de tes parents", ck: "Année, lisibilité, numéro fiscal", ic: '<path d="M7 3h10v18H7z"/><path d="M10 7h4M10 11h4M10 15h2"/>'}
];
let pz = 1;
/* Documents complémentaires : tu les nommes, l'Agent les vérifie (aperçu : le fichier reste sur ton appareil) */
const DOCT = ["Attestation employeur", "Quittances de loyer", "Lettre de recommandation", "Attestation de bourse", "Autre"];
const ADD_IC = '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M12.5 11v6M9.5 14h6"/>';
let serverDocs = null;
const docs = () => Array.isArray(serverDocs) ? serverDocs : (store.get("pf-docs") || []);
function normaliseDocument(d){
  return {id: d.id, nom: d.nom, type: d.type, file: d.filename || d.file || "", size: Number(d.size_bytes || d.size || 0) / 1048576, server: true, status: d.status || "received"};
}
async function loadDocuments(){
  try {
    const r = await fetch("api/dossier", {credentials: "same-origin", headers: {"Accept": "application/json"}});
    if (!r.ok) return;
    serverDocs = (await r.json()).map(normaliseDocument);
    store.set("pf-docs", serverDocs);
    papers();
  } catch (x) {}
}
function checks(d){
  const ext = (d.file || "").split(".").pop().toLowerCase(), okExt = ["pdf", "jpg", "jpeg", "png", "heic"].includes(ext);
  return [
    ["Nom clair", d.nom.length >= 3, d.nom.length >= 3 ? "Précis" : "3 lettres minimum"],
    ["Type reconnu", !!d.type, d.type ? "Reconnu" : "Choisis ce que c'est"],
    ["Format accepté", d.file ? okExt : null, d.file ? (okExt ? ext.toUpperCase() : "PDF ou photo seulement") : "Fichier à joindre"],
    ["Taille", d.file ? d.size <= 10 : null, d.file ? (d.size <= 10 ? `${d.size.toFixed(1).replace(".", ",")} Mo` : "10 Mo maximum") : "–"],
    ["Nom sur le document", null, "À l'ouverture"]
  ];
}
function papers(){
  const D = docs(), all = PIECES.concat(D.map(d => ({t: d.nom, d: d.type, ic: ADD_IC, extra: d}))), n = all.length + (D.length < 3 ? 1 : 0), mid = (n - 1) / 2;
  const received = D.length, percent = Math.min(100, Math.round(received / 5 * 100));
  $("doc-count").textContent = `${received} sur 5 pièces`;
  $("doc-progress-label").textContent = `${received} sur 5 pièces reçues`;
  $("doc-progress").style.setProperty("--p", percent);
  $("doc-count").className = `pill ${received ? "ok" : "wait"}`;
  if (pz >= n) pz = 1;
  $("papers").innerHTML = all.map((x, k) => `<button type="button" class="paper${k === pz ? " on" : ""}${x.hot ? " hot" : ""}${x.extra ? " ex" : ""}" data-p="${k}" style="--i:${(k - mid).toFixed(2)}"><span class="pa-h"><i><svg viewBox="0 0 24 24" aria-hidden="true">${x.ic}</svg></i><em>${x.hot ? "Commence ici" : x.extra ? "Ajouté" : "À déposer"}</em></span><b>${esc(x.t)}</b><span class="pa-l"><i></i><i></i><i></i><i></i></span></button>`).join("")
    + (D.length < 3 ? `<button type="button" class="paper add${pz === all.length ? " on" : ""}" data-p="${all.length}" style="--i:${(all.length - mid).toFixed(2)}"><span class="pa-plus"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg></span><b>Document complémentaire</b><small>Tu le nommes, l'Agent le vérifie</small></button>` : "");
  if (pz === all.length) { addForm(); return; }
  const x = all[pz];
  if (x.extra) { $("fd").className = "fd fd-x"; $("fd").innerHTML = docHead(x.extra) + verif(x.extra); return; }
  $("fd").className = "fd";
  $("fd").innerHTML = `<i class="fd-i"><svg viewBox="0 0 24 24" aria-hidden="true">${x.ic}</svg></i><span class="fd-t"><b>${x.t}</b><small>${x.d}</small></span><span class="fd-c"><small>L'Agent vérifie</small><b>${x.ck}</b></span><em class="${x.hot ? "rust" : ""}">${x.hot ? "Commence ici" : "À déposer"}</em>`;
}
const docHead = d => `<div class="fd-r"><i class="fd-i"><svg viewBox="0 0 24 24" aria-hidden="true">${ADD_IC}</svg></i><span class="fd-t"><b>${esc(d.nom)}</b><small>${esc(d.type)}${d.file ? " · " + esc(d.file) : ""}</small></span><button type="button" class="ghost sm" data-del="${esc(d.id)}">Retirer</button></div>`;
function verif(d){
  const C = checks(d), bad = C.filter(c => c[1] === false), todo = C.filter(c => c[1] === null && c[0] !== "Nom sur le document" && c[0] !== "Taille");
  const sum = bad.length ? `À corriger : ${bad.map(c => c[0].toLowerCase()).join(", ")}` : todo.length ? "Il manque le fichier" : "Prêt à joindre à tes candidatures";
  const note = d.server ? "Fichier reçu par Piaule Fiction. Le contrôle approfondi sera relancé avant chaque envoi." : "Aperçu local : le fichier n'est pas envoyé tant que tu ne l'ajoutes pas au dossier.";
  return `<div class="vf"><span class="vf-s ${bad.length ? "ko" : todo.length ? "wait" : "ok"}"><b>${d.server ? "Pièce reçue" : "L'Agent a vérifié"}</b>${sum}</span><ul>${C.map(([l, ok, v], k) => `<li class="${ok === true ? "ok" : ok === false ? "ko" : "wait"}" style="--d:${k * .12}s"><i>${ok === true ? "✓" : ok === false ? "!" : "…"}</i><span><small>${l}</small><b>${esc(v)}</b></span></li>`).join("")}</ul><small class="vf-n">${note}</small></div>`;
}
function addForm(){
  $("fd").className = "fd fd-x";
  $("fd").innerHTML = `<form class="df" id="df" novalidate><label class="df-n"><small>Nom du document</small><input name="nom" maxlength="48" placeholder="Ex. Attestation de mon employeur" required></label>
    <label class="df-t"><small>C'est quoi ?</small><select name="type"><option value="">Choisis</option>${DOCT.map(t => `<option>${t}</option>`).join("")}</select></label>
    <label class="df-f"><small>Fichier</small><span class="df-fb"><input type="file" name="file" accept=".pdf,image/*"><b>Choisir</b><em>PDF ou photo</em></span></label>
    <button class="btn" type="submit">Ajouter au dossier</button></form><div id="df-v"></div>`;
  const f = $("df"), live = () => { const v = read(f); $("df-v").innerHTML = (v.nom || v.type || v.file) ? verif(v) : ""; };
  f.addEventListener("input", live); f.addEventListener("change", e => { if (e.target.type === "file") f.querySelector(".df-fb em").textContent = f.file.files[0] ? f.file.files[0].name : "PDF ou photo"; live(); });
  f.addEventListener("submit", async e => {
    e.preventDefault(); const v = read(f), file = f.file.files[0];
    if (v.nom.length < 3 || !v.type || !file || file.size > 10 * 1048576) { live(); (v.nom.length < 3 ? f.nom : !v.type ? f.type : f.file).focus(); return; }
    const form = new FormData(); form.append("nom", v.nom); form.append("type", v.type); form.append("file", file);
    const button = f.querySelector("button[type=submit]"); button.disabled = true; button.textContent = "Réception…";
    try {
      const r = await fetch("api/dossier/pieces", {method: "POST", credentials: "same-origin", body: form});
      if (!r.ok) { const j = await r.json().catch(() => ({})); throw new Error(j.detail || j.erreur || "La pièce n'a pas pu être reçue."); }
      serverDocs = null;
      await loadDocuments();
      pz = PIECES.length + docs().length - 1; papers();
    } catch (x) {
      $("df-v").innerHTML = `<p class="form-error">${esc(x.message)}</p>`;
      button.disabled = false; button.textContent = "Ajouter au dossier";
    }
  });
}
const read = f => { const fl = f.file.files[0]; return {id: String(Date.now()), nom: f.nom.value.trim(), type: f.type.value, file: fl ? fl.name : "", size: fl ? fl.size / 1048576 : 0}; };
papers();
$("papers").addEventListener("click", e => { const b = e.target.closest("[data-p]"); if (!b) return; pz = +b.dataset.p; papers(); if (b.classList.contains("add")) $("df").nom.focus({preventScroll: true}); });
$("start-dossier").addEventListener("click", () => { show(3); pz = PIECES.length + docs().length; papers(); setTimeout(() => $("df")?.nom.focus({preventScroll: true}), 0); });
$("fd").addEventListener("click", async e => {
  const b = e.target.closest("[data-del]"); if (!b) return;
  if (!confirm("Retirer cette pièce du dossier ?")) return;
  try {
    const r = await fetch(`api/dossier/pieces/${encodeURIComponent(b.dataset.del)}`, {method: "DELETE", credentials: "same-origin"});
    if (!r.ok) throw new Error("La pièce n'a pas pu être retirée.");
    serverDocs = null; await loadDocuments(); pz = 1; papers();
  } catch (x) {
    const D = docs().filter(d => d.id !== b.dataset.del); serverDocs = D; store.set("pf-docs", D); pz = 1; papers();
  }
});

/* Ton profil : enregistré sur cet appareil pour l'instant */
const OPTS = {situation: ["En études", "En alternance", "En CDI", "En CDD ou intérim", "À mon compte", "Autre"], revenus: ["Moins de 1 000 €", "1 000 à 1 500 €", "1 500 à 2 500 €", "Plus de 2 500 €"]};
const pro = $("pro");
pro.querySelectorAll(".opts").forEach(o => { const k = o.dataset.k; o.innerHTML = OPTS[k].map(v => `<label><input type="radio" name="${k}" value="${esc(v)}"><span>${esc(v)}</span></label>`).join(""); });
function fillPro(){
  const p = store.get("pf-profil") || {}, m = store.get("pf-moi") || {};
  $("pro-pn").value = p.prenom || m.prenom || ""; $("pro-em").value = m.email || "";
  ["tel", "ville"].forEach(k => pro.elements[k].value = p[k] || "");
  Object.keys(OPTS).forEach(k => pro.querySelectorAll(`[name=${k}]`).forEach(r => r.checked = r.value === p[k]));
}
async function loadProfile(){
  try {
    const r = await fetch("api/profil", {credentials: "same-origin", headers: {"Accept": "application/json"}});
    if (!r.ok) return;
    store.set("pf-profil", await r.json()); fillPro(); render();
  } catch (x) {}
}
pro.addEventListener("submit", async e => {
  e.preventDefault();
  const f = pro.elements, p = {prenom: f.prenom.value.trim(), tel: f.tel.value.trim(), ville: f.ville.value.trim(), situation: f.situation.value, revenus: f.revenus.value};
  try {
    const r = await fetch("api/profil", {method: "PUT", credentials: "same-origin", headers: {"Content-Type": "application/json"}, body: JSON.stringify(p)});
    if (!r.ok) throw new Error("Ton profil n'a pas pu être enregistré.");
    store.set("pf-profil", await r.json());
    $("pro-ok").hidden = false; setTimeout(() => $("pro-ok").hidden = true, 2600); render();
  } catch (x) { $("pro-ok").textContent = x.message; $("pro-ok").hidden = false; }
});
$("password-form").addEventListener("submit", async e => {
  e.preventDefault();
  const form = e.currentTarget, f = form.elements, error = $("password-error"), ok = $("password-ok");
  error.hidden = true; ok.hidden = true;
  try {
    const r = await fetch("api/mot-de-passe", {method: "POST", credentials: "same-origin", headers: {"Content-Type": "application/json"}, body: JSON.stringify({current_mdp: f.current_mdp.value, nouveau_mdp: f.nouveau_mdp.value})});
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.erreur || j.detail || "Le mot de passe n'a pas pu être modifié.");
    form.reset(); ok.hidden = false; ok.textContent = "Modifié · reconnecte-toi";
    setTimeout(() => { location.href = "index.html"; }, 1200);
  } catch (x) { error.textContent = x.message; error.hidden = false; }
});

/* Le mur d'annonces : des annonces fictives qui suivent ta recherche, l'une est écartée */
function wall(c, demo, remote){
  const Q = QUART[c.city] || GENERIC;
  const matching = Array.isArray(remote) ? remote.filter(x => norm(x.city || "") === norm(c.city)) : [];
  const source = matching.length ? matching : (Array.isArray(remote) ? remote : []);
  const base = source.length ? source.map((x, k) => {
    const ph = [2, 7, 1, 4, 5, 8][k % 6], rent = Number(x.monthly_rent_eur) || c.budget;
    const out = x.risk_level === "high";
    return [ph, 18 + k * 3, rent - c.budget, out ? 0 : Math.max(78, 95 - k * 5), x.title || "Annonce connectée", x.source || "source connectée", x.risk_level || "unknown"];
  }) : [[2, 23, -85, 94], [7, 21, -60, 88], [6, 31, -260, 0], [1, 19, -120, 91], [4, 24, -10, 83], [5, 20, -95, 86], [3, 18, -140, 90], [8, 22, -40, 89]];
  $("rh-source").textContent = source.length ? "Backend connecté · annonces synthétiques" : "Aperçu · annonces fictives";
  const items = base.map(([ph, m2, d, s], k) => {
    const out = s === 0, rent = Math.max(280, Math.round((c.budget + d) / 5) * 5);
    return `<div class="lc${out ? " out" : ""}"><img src="photos/annonce-${ph}.jpg" alt=""><span><b>${esc(typeLabel(c.type))} · ${m2} m² · ${fmt(rent)} €</b><small>${esc(Q[k % 8])}${Q === GENERIC ? ", " + esc(c.city) : ""}</small></span><em>${out ? "Arnaque écartée" : s + " %"}</em></div>`;
  }).join("");
  const tr = $("w-track"); tr.innerHTML = items + items;
  /* Le même fil, en petit, sur l'écran du mur */
  const mini = base.map(([ph, m2, d, s], k) => {
    const out = s === 0, rent = Math.max(280, Math.round((c.budget + d) / 5) * 5);
    return `<div class="pc${out ? " out" : ""}"><img src="photos/annonce-${ph}.jpg" alt=""><b>${m2} m² · ${fmt(rent)} €</b><small>${esc(Q[k % 8])}</small><em>${out ? "Arnaque écartée" : s + " % pour toi"}</em></div>`;
  }).join("");
  /* La liste « Annonces pour toi » de l'onglet recherche */
  $("rh-tbl").innerHTML = '<div class="tr th"><span>#</span><span>Logement</span><span>Quartier</span><span>Loyer</span><span>Pour toi</span></div>' + base.slice(0, 5).map(([ph, m2, d, s], k) => {
    const out = s === 0, rent = Math.max(280, Math.round((c.budget + d) / 5) * 5);
    return `<div class="tr${k === 1 ? " hot" : ""}${out ? " out" : ""}"><span>${String(k + 1).padStart(2, "0")}</span><span><img src="photos/annonce-${ph}.jpg" alt=""><b>${esc(typeLabel(c.type))} · ${m2} m²</b></span><span>${esc(Q[k % 8])}</span><span>${fmt(rent)} €</span><span><em class="${out ? "rust" : "ok"}">${out ? "Arnaque écartée" : s + " %"}</em></span></div>`;
  }).join("");
  $("rh-seen").innerHTML = base.slice(5, 8).map(([ph, m2, d], k) => `<button type="button" class="sn" data-go="4"><img src="photos/annonce-${ph}.jpg" alt=""><span><b>${esc(typeLabel(c.type))} · ${m2} m²</b><small>${esc(Q[(k + 5) % 8])}</small></span><em>${fmt(Math.max(280, Math.round((c.budget + d) / 5) * 5))} €</em></button>`).join("");
  const pt = $("p-track"); pt.innerHTML = mini + mini; pt.style.setProperty("--dur", `${demo ? 48 : 38}s`);
  tr.style.setProperty("--dur", `${demo ? 44 : 34}s`);
}

/* Étape 1 : écrire sa recherche */
const ask = $("ask"), inp = $("ask-in"), ph = $("ask-ph");
let tyT = 0, tyI = 0;
function startTyping(){
  clearTimeout(tyT);
  if (reduced) { ph.textContent = EX[0]; return; }
  let i = 0, del = false;
  const step = () => {
    const t = EX[tyI % EX.length];
    if (!del) { i++; ph.textContent = t.slice(0, i); if (i >= t.length) { del = true; tyT = setTimeout(step, 2200); return; } tyT = setTimeout(step, 38); }
    else { i -= 2; ph.textContent = t.slice(0, Math.max(0, i)); if (i <= 0) { del = false; tyI++; tyT = setTimeout(step, 400); return; } tyT = setTimeout(step, 14); }
  };
  step();
}
/* Ta recherche se réécrit sous tes yeux, lettre par lettre */
function retype(v){
  clearTimeout(tyT);
  if (inp.value === v) return;
  if (reduced) { inp.value = v; syncHas(); return; }
  let i = 0; inp.value = ""; syncHas();
  const step = () => { i += 1 + (i > 30); inp.value = v.slice(0, i); syncHas(); if (i < v.length) tyT = setTimeout(step, 26); };
  tyT = setTimeout(step, 500);
}
const syncHas = () => ask.classList.toggle("has", inp.value.length > 0);
inp.addEventListener("input", syncHas);
inp.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask.requestSubmit(); } });
$("ideas").insertAdjacentHTML("beforeend", EX.map(x => `<button type="button">${esc(x)}</button>`).join(""));
$("ideas").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; inp.value = b.textContent; syncHas(); inp.focus(); });
ask.addEventListener("submit", e => {
  e.preventDefault();
  const v = inp.value.trim();
  if (v.length < 6) { $("ask-err").textContent = "Écris quelques mots : la ville, le budget, le type de logement."; $("ask-err").hidden = false; inp.focus(); return; }
  $("ask-err").hidden = true;
  const l = R.all(), cur = store.get("pf-recherche");
  if (mode === "new" || !cur) l.push(v); else l[l.indexOf(cur)] = v;
  R.save([...new Set(l)].slice(-4), v); mode = "edit";
  clearTimeout(tyT);
  render(); inp.blur(); void syncBackendSearch(v);
});
$("edit").addEventListener("click", () => {
  mode = "edit"; show(0);
  inp.value = store.get("pf-recherche") || ""; syncHas();
  $("hi-p").textContent = "Change ce que tu veux, tes agents suivront.";
  scrollTo({top: 0, behavior: reduced ? "auto" : "smooth"});
  inp.focus({preventScroll: true});
});

/* ---------- La pièce : sa journée en boucle, l'écran du mur et le réveil suivent la vidéo ---------- */
/* Montage de la journée : début de chaque passage (s) et l'heure qu'il est à ce moment-là */
const DAY = {starts: [0, 4.67, 9.6, 15.04, 19.3, 23.85, 28.98, 33.74, 37.54, 42.93, 48.02, 53.63], hours: [3, 7, 7.5, 8.25, 10, 13, 16.5, 18.5, 19.5, 21, 22, 27]};
/* Le tableau dans l'image (coins en fraction de l'image 16:9) et le réveil */
const QUAD = [[.8621, .125], [.9457, .0542], [.9457, .5056], [.8621, .4792]], CLK = [.731, .165];
const room = $("room"), rv = $("room-v"), panel = $("panel"), clock = $("clock");
const small = () => innerWidth <= 760;
/* Sur téléphone, une version carrée recadrée sur la droite de la pièce (x de 0.4375 à 1) */
const EXT = document.createElement("video").canPlayType('video/webm; codecs="vp9"') ? "webm" : "mp4";
const SRC = () => small() ? {src: `journee-m.${EXT}`, x0: .4375, w: .5625, ar: 1} : {src: `journee.${EXT}`, x0: 0, w: 1, ar: 16 / 9};
let cur = null;
function homography(w, h, p){
  const [[x0, y0], [x1, y1], [x2, y2], [x3, y3]] = p;
  const sx = x0 - x1 + x2 - x3, sy = y0 - y1 + y2 - y3, dx1 = x1 - x2, dx2 = x3 - x2, dy1 = y1 - y2, dy2 = y3 - y2, den = dx1 * dy2 - dx2 * dy1;
  const g = (sx * dy2 - dx2 * sy) / den, k = (dx1 * sy - sx * dy1) / den;
  const a = x1 - x0 + g * x1, b = x3 - x0 + k * x3, d = y1 - y0 + g * y1, e = y3 - y0 + k * y3;
  return `matrix3d(${[a / w, d / w, 0, g / w, b / h, e / h, 0, k / h, 0, 0, 1, 0, x0, y0, 0, 1].map(v => +v.toFixed(6)).join(",")})`;
}
const POSX = () => small() ? .5 : 1;
function placeRoom(){
  const s = SRC(); if (!cur || cur.src !== s.src) { cur = s; rv.poster = s.src.replace(/\.\w+$/, ".webp"); rv.src = s.src; rv.play().catch(() => {}); }
  const RW = room.clientWidth, RH = room.clientHeight, VW = s.ar, VH = 1, sc = Math.max(RW / VW, RH / VH), dw = VW * sc, dh = VH * sc;
  const ox = (RW - dw) * POSX(), oy = (RH - dh) * .5;
  rv.style.objectPosition = `${POSX() * 100}% 50%`;
  const P = ([x, y]) => [ox + (x - s.x0) / s.w * dw, oy + y * dh];
  panel.style.transform = homography(220, 520, QUAD.map(P));
  const [cx, cy] = P(CLK); clock.style.left = cx + "px"; clock.style.top = cy + "px"; clock.style.fontSize = Math.max(12, dw / s.w * .0148) + "px";
}
let lastClk = "";
function tick(){
  if (rv.readyState >= 2) {
    const t = rv.currentTime, S = DAY.starts; let i = 0; while (i < S.length - 2 && t >= S[i + 1]) i++;
    const f = Math.min(1, Math.max(0, (t - S[i]) / (S[i + 1] - S[i]))), h = (DAY.hours[i] + (DAY.hours[i + 1] - DAY.hours[i]) * f) % 24;
    const txt = `${String(Math.floor(h)).padStart(2, "0")}<i>:</i>${String(Math.floor(h % 1 * 60)).padStart(2, "0")}`;
    if (txt !== lastClk) { lastClk = txt; $("clk").innerHTML = txt; }
  }
  if (!document.hidden) requestAnimationFrame(tick);
}
rv.muted = true; rv.playsInline = true;
rv.addEventListener("playing", () => { rv.classList.add("on"); panel.classList.add("on"); clock.classList.add("on"); });
addEventListener("resize", placeRoom);
document.addEventListener("visibilitychange", () => { if (!document.hidden) { rv.play().catch(() => {}); requestAnimationFrame(tick); } });
/* Lecture bloquée (économie d'énergie) : on relance au premier geste */
["pointerdown", "touchstart", "scroll", "keydown"].forEach(e => addEventListener(e, () => { if (rv.paused) rv.play().catch(() => {}); }, {passive: true, once: true}));

/* Le tableau de bord se met à l'échelle de la fenêtre : tout tient à l'écran, sans défilement */
/* Fermer la fenêtre : l'espace s'efface, on regarde sa journée en grand. Échap rouvre. */
function cine(on){
  document.body.classList.toggle("cine", on); $("cine").setAttribute("aria-pressed", String(on));
  if (!on) $("cine").blur();
}
$("cine").addEventListener("click", () => cine(!document.body.classList.contains("cine")));
addEventListener("keydown", e => { if (e.key === "Escape" && document.body.classList.contains("cine")) cine(false); });
function fit(){ const k = Math.min(innerWidth * .955 / 1392, (innerHeight * .93 - 34) / 846, 1.4); document.documentElement.style.setProperty("--k", Math.max(.4, k).toFixed(4)); }
fit(); addEventListener("resize", fit);

/* Démarrage (en dernier : tout est déclaré). La session serveur est la source de vérité. */
async function boot(){
  let moi = null;
  try {
    const r = await fetch("api/moi", {credentials: "same-origin", headers: {"Accept": "application/json"}});
    if (r.ok) moi = await r.json();
  } catch (x) {}
  if (!moi) {
    store.set("pf-moi", null);
    $("gate").hidden = false;
    return;
  }
  store.set("pf-moi", moi);
  $("app").hidden = false; $("me").hidden = false;
  const pn = (moi.prenom || "").trim() || "toi";
  const P = pn.charAt(0).toUpperCase() + pn.slice(1);
  $("me-av").textContent = P.charAt(0); $("me-nm").textContent = P; $("me-pn").textContent = P; $("me-em").textContent = moi.email || "";
  $("hi").firstChild.textContent = `Bonjour ${P},`;
  $("sd-av").textContent = P.charAt(0); $("sd-pn").textContent = P; $("h-hi").innerHTML = `Bonjour, <b>${esc(P)}</b>`;
  fillPro();
  render();
  void loadProfile();
  void loadDocuments();
  void syncBackendSearch(store.get("pf-recherche"));
  if (!reduced) { placeRoom(); requestAnimationFrame(tick); } else { room.hidden = true; }
}
boot();
