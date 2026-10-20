(() => {
"use strict";
/* Piaule Fiction · accueil en pages. Données fictives, aucune connexion réelle.
   Simulé : la lecture du prompt, les agents, les annonces, la régie, l'envoi.
   Plus tard : le prompt part vers le vrai service de recherche (voir sendSearch). */
const $ = id => document.getElementById(id);
const de = document.documentElement;
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const cl = v => v < 0 ? 0 : v > 1 ? 1 : v, sm = v => v * v * (3 - 2 * v), lerp = (a, b, t) => a + (b - a) * t;
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const narrow = () => innerWidth < 760;
const fmt = n => new Intl.NumberFormat("fr-FR").format(n);
history.scrollRestoration = "manual";

/* ---------- Les titres arrivent mot par mot ---------- */
document.querySelectorAll("[data-split]").forEach(el => {
  const base = parseFloat(el.dataset.split) || 0; let k = 0;
  const walk = node => [...node.childNodes].forEach(n => {
    if (n.nodeType === 3) {
      const frag = document.createDocumentFragment();
      n.textContent.split(/(\s+)/).forEach(p => {
        if (!p) return;
        if (/^\s+$/.test(p)) { frag.appendChild(document.createTextNode(p)); return; }
        const s = document.createElement("span"); s.className = "w a bl"; s.style.setProperty("--d", (base + k++ * .055).toFixed(3)); s.textContent = p; frag.appendChild(s);
      });
      n.replaceWith(frag);
    } else if (n.nodeType === 1) walk(n);
  });
  walk(el);
});

/* ---------- Tes biens : ce qu'on comprend de ta phrase ---------- */
const CITIES = {lyon: "Lyon", villeurbanne: "Lyon", paris: "Paris", bordeaux: "Bordeaux", lille: "Lille", toulouse: "Toulouse", marseille: "Marseille", nantes: "Nantes", montpellier: "Montpellier", rennes: "Rennes", grenoble: "Grenoble", strasbourg: "Strasbourg", nice: "Nice", angers: "Angers", dijon: "Dijon", tours: "Tours"};
const QUART = {
  Lyon: ["Gratte-Ciel", "Monplaisir", "Croix-Rousse", "Guillotière", "Jean Macé", "Vaise", "Part-Dieu", "Perrache"],
  Paris: ["Paris 11e", "Paris 18e", "Paris 13e", "Paris 20e", "Paris 15e", "Paris 19e", "Paris 10e", "Paris 14e"],
  Bordeaux: ["Chartrons", "Saint-Michel", "Bastide", "Victoire", "Saint-Genès", "Nansouty", "Bacalan", "Capucins"],
  Lille: ["Wazemmes", "Vauban", "Fives", "Moulins", "Vieux-Lille", "Saint-Maurice", "Gambetta", "Bois-Blancs"],
  Toulouse: ["Saint-Cyprien", "Capitole", "Rangueil", "Saint-Agne", "Carmes", "Minimes", "Compans", "Jean-Jaurès"],
  Marseille: ["Cours Julien", "Le Panier", "Castellane", "Saint-Charles", "Vauban", "Cinq-Avenues", "Baille", "Endoume"],
  Nantes: ["Bouffay", "Chantenay", "Île de Nantes", "Talensac", "Zola", "Saint-Félix", "Doulon", "Hauts-Pavés"],
  Montpellier: ["Écusson", "Beaux-Arts", "Boutonnet", "Antigone", "Figuerolles", "Arceaux", "Port Marianne", "Gambetta"],
  Rennes: ["Thabor", "Sainte-Anne", "Colombier", "Villejean", "Saint-Hélier", "Cleunay", "Sud-Gare", "Beaulieu"],
  Grenoble: ["Championnet", "Île Verte", "Berriat", "Saint-Bruno", "Notre-Dame", "Europole", "Mutualité", "Abbaye"],
  Strasbourg: ["Krutenau", "Neudorf", "Esplanade", "Gare", "Orangerie", "Robertsau", "Cronenbourg", "Petite France"]
};
const GENERIC = ["Centre", "Gare", "Université", "Vieille ville", "Les Halles", "Saint-Michel", "Jean-Jaurès", "Les Quais"];
const norm = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
let CRIT = {type: "Studio", city: "Lyon", budget: 600, extras: ["Près d'un métro"], when: "", example: true};
function parse(txt){
  const n = norm(txt), c = {type: "Studio", city: "Lyon", budget: 600, extras: [], when: "", example: false};
  let m = n.match(/(\d[\d\s.]{1,6})\s*(?:€|e\b|eur|euros?)/) || n.match(/(?:max(?:imum)?|budget|moins de|jusqu'a)\s*:?\s*(\d{3,4})/);
  if (m) { const v = parseInt(m[1].replace(/[\s.]/g, ""), 10); if (v >= 200 && v <= 5000) c.budget = v; }
  let found = false;
  for (const k in CITIES) if (new RegExp("\\b" + k + "\\b").test(n)) { c.city = CITIES[k]; found = true; break; }
  if (!found) { const mm = txt.match(/\b(?:à|a|sur|vers|près de)\s+([A-ZÀ-Ý][A-Za-zÀ-ÿ'-]{2,})/); if (mm) c.city = mm[1]; }
  if (/coloc/.test(n)) c.type = "Coloc"; else if (/chambre/.test(n)) c.type = "Chambre"; else if (/\bt2\b|2 pieces|deux pieces/.test(n)) c.type = "T2"; else if (/\bt1\b|\bf1\b|1 piece/.test(n)) c.type = "T1";
  const X = [[/meubl/, "Meublé"], [/metro|tram|transport|bus\b/, "Près des transports"], [/calme/, "Calme"], [/balcon|terrasse/, "Balcon"], [/lumin|soleil/, "Lumineux"], [/\bfac\b|universit|campus|ecole|iut/, "Près de ton école"], [/parking|velo/, "Vélo ou parking"], [/animal|chat|chien/, "Animaux acceptés"]];
  X.forEach(([r, l]) => { if (r.test(n)) c.extras.push(l); });
  const W = [[/des que possible|asap|urgent|vite|maintenant/, "Dès que possible"], [/septembre|rentree/, "Pour septembre"], [/janvier/, "Pour janvier"], [/octobre/, "Pour octobre"], [/novembre/, "Pour novembre"], [/decembre/, "Pour décembre"], [/juillet|ete/, "Pour juillet"], [/aout/, "Pour août"]];
  for (const [r, l] of W) if (r.test(n)) { c.when = l; break; }
  return c;
}
const typeLabel = t => ({Studio: "Studio", T1: "T1", T2: "T2", Coloc: "Chambre en coloc", Chambre: "Chambre"})[t] || "Studio";
const typeLower = t => ({Studio: "studio", T1: "T1", T2: "T2", Coloc: "chambre en colocation", Chambre: "chambre"})[t] || "studio";
const quart = (city, i) => (QUART[city] || GENERIC)[i % 8] + (QUART[city] ? "" : ", " + city);

/* Les annonces de la nuit : photos banales, notes honnêtes */
const AG = {E: ["L'Agent", "#3653D9"], D: ["L'Agent", "#3653D9"], P: ["L'Agent", "#3653D9"]};
const BASE = [
  {ph: 2, m2: 23, d: -85, q: 0, s: 94, a: "D", say: "Photo prise au flash. J'ai demandé une vidéo au propriétaire."},
  {ph: 7, m2: 21, d: -60, q: 1, s: 88, a: "E", say: "Seule la cuisine est en photo : j'ai demandé le reste."},
  {ph: 6, m2: 31, d: -260, q: 2, out: true, a: "D", say: "Virement demandé avant la visite. On ne participante pas."},
  {ph: 1, m2: 19, d: -120, q: 3, s: 91, a: "E", say: "Résidence étudiante, laverie en bas. Libre au 1er novembre."},
  {ph: 4, m2: 24, d: -10, q: 4, s: 83, a: "E", say: "Le hall est en travaux, l'appartement non. 3e sans ascenseur."},
  {ph: 5, m2: 20, d: -95, q: 5, s: 86, a: "P", say: "Papier peint daté, mais 80 € sous le prix du quartier."},
  {ph: 3, m2: 18, d: -140, q: 6, s: 90, a: "D", say: "Ce sont bien les photos du logement. Publiée il y a 2 h."},
  {ph: 8, m2: 22, d: -40, q: 7, s: 89, a: "P", say: "Salle d'eau refaite. Ta participanture est prête."}
];
let LIST = [];
function buildList(){
  const t = CRIT.type;
  LIST = BASE.map((b, i) => {
    const kind = t === "Studio" ? (i === 4 || i === 7 ? "T1" : "Studio") : t;
    const rent = Math.max(250, Math.round((CRIT.budget + (b.out ? -Math.round(CRIT.budget * .42) : b.d)) / 5) * 5);
    return Object.assign({}, b, {kind, rent, where: quart(CRIT.city, b.q), m2: kind === "Chambre" || kind === "Coloc" ? b.m2 - 7 : b.m2});
  });
}

/* ---------- Le jeu de pages ---------- */
const PAGES = [
  {id: "recherche", len: 1.3, T: 0, hold: .38, label: "Tes biens"},
  {id: "nuit", len: 1.9, T: 1, hold: .8, label: "Jour et nuit"},
  {id: "dossier", len: 5.2, T: 2, hold: .94, label: "Dossiers reçus"},
  {id: "participanture", len: 3.2, T: 3, hold: .82, label: "Ta participanture"},
  {id: "visite", len: 2.5, T: 4, hold: .8, label: "La visite"},
  {id: "garanties", len: 3, T: 4.66, hold: 1, label: "Tes garanties"}
];
const ALL = [...PAGES.map(p => ({id: p.id, label: p.label})), {id: "fin", label: "J'ai le bail"}];
const deck = $("deck"), els = PAGES.map(p => $(p.id)), fin = $("fin");
/* Chaque titre arrive seul au milieu de l'écran, puis remonte et rétrécit pour laisser la place à la scène */
const TTL = els.map(el => el.querySelector(".ttl")), TTL_END = .07, SC_AT = .055;
let VH = innerHeight, starts = [], pin = 0, deckTop = 0, cur = -1, pS = 0, pT = 0, TT = [];
function layout(){
  VH = innerHeight; let acc = 0;
  starts = PAGES.map(p => { const s = acc; acc += p.len * VH; return s; });
  pin = acc; deck.style.height = `${Math.round(pin + VH)}px`;
  deckTop = deck.getBoundingClientRect().top + scrollY;
  const ts = narrow() ? .8 : .6;
  TT = TTL.map((t, i) => {
    if (!t) return null;
    const top = parseFloat(getComputedStyle(t).top) || 84, eb = t.querySelector(".eb"), h2 = t.querySelector(".h2");
    const keep = (eb ? eb.offsetHeight + parseFloat(getComputedStyle(eb).marginBottom) : 0) + h2.offsetHeight;
    els[i].style.setProperty("--sc-top", `${Math.round(top + keep * ts + (narrow() ? 14 : 24))}px`);
    return {ty0: Math.max(0, VH / 2 - top - t.offsetHeight / 2), ts};
  });
}
function applyTitle(){
  const t = TTL[cur], q = TT[cur]; if (!t || !q) return;
  const k = sm(cl(pS / TTL_END));
  t.style.setProperty("--ty", `${(q.ty0 * (1 - k)).toFixed(1)}px`);
  t.style.setProperty("--ts", (1 - (1 - q.ts) * k).toFixed(4));
  t.style.setProperty("--k", k.toFixed(3));
}
/* Repères à droite */
const rail = $("rail");
rail.innerHTML = ALL.map((p, i) => `<a href="#${p.id}" data-go="${i}"><span>${p.label}</span><i></i></a>`).join("");
const railLinks = [...rail.querySelectorAll("a")];
let railCur = -1;
function setRail(i){
  if (i === railCur) return; railCur = i;
  railLinks.forEach((a, k) => a.setAttribute("aria-current", String(k === i)));
  drLinks.forEach((a, k) => a.setAttribute("aria-current", String(k === i)));
}
/* ---------- Le menu à trois barres : un panneau qui glisse depuis la droite ---------- */
const drawer = $("drawer"), mbtn = $("mbtn");
$("dr-nav").innerHTML = PAGES.map((p, i) => `<a href="#${p.id}" data-go="${i}" style="--k:${i}">${p.label}<i aria-hidden="true"></i></a>`).join("");
const drLinks = [...$("dr-nav").querySelectorAll("a")];
let drT = 0;
function setMenu(open){
  clearTimeout(drT);
  mbtn.setAttribute("aria-expanded", String(open)); mbtn.setAttribute("aria-label", open ? "Fermer le menu" : "Ouvrir le menu");
  de.classList.toggle("menu-open", open);
  if (open) { drawer.hidden = false; void drawer.offsetWidth; drawer.classList.add("open"); setTimeout(() => (drLinks[Math.max(0, railCur)] || drLinks[0]).focus({preventScroll: true}), 350); }
  else { drawer.classList.remove("open"); drT = setTimeout(() => { drawer.hidden = true; }, reduced ? 0 : 560); }
}
mbtn.addEventListener("click", () => setMenu(true));
$("dr-x").addEventListener("click", () => { setMenu(false); mbtn.focus({preventScroll: true}); });
$("dr-scrim").addEventListener("click", () => setMenu(false));
drLinks.forEach(a => a.addEventListener("click", () => setMenu(false)));
$("dr-tr").addEventListener("click", () => setMenu(false));
$("dr-go").addEventListener("click", () => { setMenu(false); goTo(0); setTimeout(() => $("ask-in").focus({preventScroll: true}), reduced ? 50 : 900); });
addEventListener("keydown", e => { if (e.key === "Escape" && !drawer.hidden) { setMenu(false); mbtn.focus({preventScroll: true}); } });
function goTo(i){
  const y = i >= PAGES.length ? fin.getBoundingClientRect().top + scrollY - 10 : deckTop + starts[i] + (i ? 4 : 0);
  scrollTo({top: y, behavior: reduced ? "auto" : "smooth"});
}
document.addEventListener("click", e => {
  const a = e.target.closest("[data-go]"); if (!a) return;
  e.preventDefault(); goTo(+a.dataset.go);
  if (a.id === "m-cta") setTimeout(() => $("ask-in").focus({preventScroll: true}), reduced ? 50 : 1400);
});

let fieldT = 0;
function setPage(i){
  if (i === cur) return false;
  cur = i;
  els.forEach((el, k) => {
    el.classList.toggle("on", k === i); el.classList.toggle("past", k < i);
    if (k !== i) el.classList.remove("out");
    el.inert = k !== i; el.setAttribute("aria-hidden", String(k !== i));
  });
  if (i !== 0) closeGuide();
  typer(i === 0);
  /* Safari peut garder à l'écran des calques flous même masqués : hors de sa page, le champ d'annonces disparaît du rendu */
  clearTimeout(fieldT);
  if (i === 1) $("field").style.display = "";
  else fieldT = setTimeout(() => { if (cur !== 1) $("field").style.display = "none"; }, 900);
  if (i === 1) { dayT0 = 0; dayLast = -1; minLast = -1; actI = -1; evI = 0; $("feed").innerHTML = ""; }
  return true;
}

const HOOK = {}, CONT = {};
function frame(){
  const y = scrollY - deckTop;
  let i = 0; for (let k = 0; k < PAGES.length; k++) if (y >= starts[k]) i = k;
  const p = PAGES[i], f = cl((y - starts[i]) / (p.len * VH)), s = cl(f / p.hold);
  const changed = setPage(i);
  els[i].classList.toggle("out", p.hold < 1 && f > p.hold + .012);
  els[i].classList.toggle("sc", s > SC_AT);
  pT = s; if (changed) pS = s;
  if (HOOK[p.id]) HOOK[p.id](s, f);
  let T = p.T;
  if (y > pin) T = PAGES[PAGES.length - 1].T + (5 - PAGES[PAGES.length - 1].T) * sm(cl((y - pin) / (VH * .85)));
  else if (p.hold < 1 && f > p.hold) T = p.T + (PAGES[i + 1].T - p.T) * sm(cl((f - p.hold) / (1 - p.hold)));
  filmTo(T);
  setRail(y > pin + VH * .45 ? 6 : i);
}

/* ---------- Le film de la clé : de la nuit à l'aube, piloté par la page ---------- */
const FILM_CLIPS = window.PF_FILM_CLIPS || [48, 48, 48, 48, 48];
const film = $("film"), keys = [...film.querySelectorAll(".fk")], cv = $("fcv"), g = cv.getContext("2d");
const SEQ = FILM_CLIPS.map((n, c) => Array.from({length: n}, (_, i) => ({src: `film/t${c + 1}/${String(i + 1).padStart(3, "0")}.webp`, img: null, ok: false})));
const FLAT = SEQ.flat();
let loading = 0, curG = 0, fW = 0, fH = 0, dpr = 1, shownT = 0, targetT = 0, raf = 0;
/* La porte s'ouvre (dernier plan) : les images 17 à 30 montrent la clé des deux côtés de la porte.
   On les saute : la porte fermée se fond dans la porte ouverte, dans un éclat de lumière. */
const DOOR = {c: 4, a: .3, b: .46, i0: 15, i1: 30};
const clipIdx = (c, f, n) => {
  if (c !== DOOR.c || n < 48) return Math.round(f * (n - 1));
  if (f <= DOOR.a) return Math.round(f / DOOR.a * DOOR.i0);
  if (f >= DOOR.b) return Math.round(DOOR.i1 + (f - DOOR.b) / (1 - DOOR.b) * (n - 1 - DOOR.i1));
  return f < (DOOR.a + DOOR.b) / 2 ? DOOR.i0 : DOOR.i1;
};
const gIndex = t => { const c = Math.min(SEQ.length - 1, Math.floor(t)), f = t - c; let b = 0; for (let k = 0; k < c; k++) b += SEQ[k].length; return b + clipIdx(c, f, SEQ[c].length); };
const AHEAD = 60;
let drawn = null;
function pump(){
  while (loading < 6) {
    let best = -1, bd = 1e9;
    /* Seulement les images proches de l'endroit où l'on est : le reste arrive au fil du défilement */
    for (let i = 0; i < FLAT.length; i++) if (!FLAT[i].img) { const d = Math.abs(i - curG); if (d < bd) { bd = d; best = i; } }
    if (best < 0 || bd > AHEAD) return;
    const fr = FLAT[best]; fr.img = new Image(); fr.img.decoding = "async"; loading++;
    const done = () => { fr.ok = true; loading--; if (Math.abs(best - curG) < 3) { drawn = null; paint(shownT); } pump(); };
    fr.img.onload = () => { const d = fr.img.decode ? fr.img.decode() : Promise.resolve(); d.then(done, done); };
    fr.img.onerror = () => { loading--; pump(); };
    fr.img.src = fr.src;
  }
}
function frameAt(t){ const i = gIndex(t); for (let d = 0; d < 24; d++) { const a = FLAT[i - d], b = FLAT[i + d]; if (a && a.ok) return a.img; if (b && b.ok) return b.img; } return null; }
/* Le canevas n'a pas besoin d'être plus fin que les images du film (1440 × 810) */
function fsize(){ const r = film.getBoundingClientRect(); fW = r.width; fH = r.height; dpr = Math.min(2, devicePixelRatio || 1, Math.max(1, 1440 / fW, 810 / fH)); cv.width = Math.round(fW * dpr); cv.height = Math.round(fH * dpr); drawn = null; }
/* Où l'image est cadrée : la clé bien à droite au début, puis le cadrage du film */
/* Cadrage du début : la clé reste entière à l'écran, quelle que soit la forme de la fenêtre (haute, carrée ou large) */
const keyFx = (w, h) => {
  if (narrow()) return .8;
  const dw = 1440 * Math.max(w / 1440, h / 810); if (dw - w < 1) return .08;
  const r = w / dw, want = .52 + .3 * cl((r - .34) / .55);
  return Math.max(.08, Math.min(1, (want * w - .705 * dw) / (w - dw)));
};
const fxAt = t => narrow() ? .8 : (t < 1 ? lerp(keyFx(fW, fH), .72, sm(cl(t))) : .72);
function paint(t){
  const img = frameAt(t), fx = fxAt(t);
  const c0 = Math.floor(t), f0 = t - c0, inDoor = c0 === DOOR.c && f0 > DOOR.a && f0 < DOOR.b;
  const key = img && !inDoor ? img.src + "|" + fx.toFixed(4) : null;
  if (img && key && key === drawn) { /* même image, même cadrage : rien à redessiner */ }
  else if (img) {
    drawn = key;
    const iw = img.naturalWidth, ih = img.naturalHeight, s = Math.max(fW / iw, fH / ih), dw = iw * s, dh = ih * s;
    g.setTransform(dpr, 0, 0, dpr, 0, 0); g.drawImage(img, (fW - dw) * fx, (fH - dh) * .5, dw, dh);
    const c = Math.floor(t), f = t - c;
    if (c === DOOR.c && f > DOOR.a && f < DOOR.b && SEQ[c].length >= 48) {
      const base = gIndex(c), A = FLAT[base + DOOR.i0], B = FLAT[base + DOOR.i1], x = sm((f - DOOR.a) / (DOOR.b - DOOR.a));
      if (A && A.ok && B && B.ok) {
        g.drawImage(A.img, (fW - dw) * fx, (fH - dh) * .5, dw, dh);
        g.globalAlpha = x; g.drawImage(B.img, (fW - dw) * fx, (fH - dh) * .5, dw, dh);
        g.globalAlpha = .42 * Math.sin(Math.PI * x); g.fillStyle = "#FFF7EC"; g.fillRect(0, 0, fW, fH); g.globalAlpha = 1;
      }
    }
    cv.style.opacity = "1";
  } else {
    const tq = Math.floor(t) + sm(cl((t - Math.floor(t) - .55) / .45));
    keys.forEach((fr, k) => {
      const d = tq - k, ad = Math.abs(d), op = ad >= 1 ? 0 : sm(1 - ad);
      fr.style.opacity = op.toFixed(3); fr.style.visibility = op > .002 ? "visible" : "hidden"; fr.style.objectPosition = `${fx * 100}% 50%`;
      if (!reduced) fr.style.transform = `scale(${(d >= 0 ? 1 + d * .45 : 1 + d * .1).toFixed(4)})`;
    });
  }
  const L = sm(cl((t - 1.35) / .5));
  $("veil-d").style.opacity = (1 - L).toFixed(3); $("veil-l").style.opacity = L.toFixed(3);
  film.style.background = `rgb(${[20, 26, 54].map((v, j) => Math.round(v + ([246, 241, 234][j] - v) * L)).join(",")})`;
  de.classList.toggle("lt", L > .5);
}
function filmTo(T){ targetT = T; kick(); }
function kick(){ if (!raf) raf = requestAnimationFrame(loop); }
function loop(now){
  raf = 0;
  shownT = reduced ? targetT : shownT + (targetT - shownT) * .1;
  if (Math.abs(targetT - shownT) < .0008) shownT = targetT;
  curG = gIndex(shownT); pump(); paint(shownT);
  /* La page suit le défilement avec un léger amorti */
  const d = pT - pS; pS = reduced || Math.abs(d) < .0004 ? pT : pS + d * .14;
  let busy = false;
  if (cur >= 0) { applyTitle(); const c = CONT[PAGES[cur].id]; if (c) busy = c(pS, now || performance.now()); }
  if (shownT !== targetT || pS !== pT || busy) raf = requestAnimationFrame(loop);
}
/* Un peu de profondeur : le décor suit doucement la souris */
if (!reduced && matchMedia("(pointer:fine)").matches) {
  addEventListener("pointermove", e => {
    film.style.setProperty("--mx", `${((.5 - e.clientX / innerWidth) * 16).toFixed(1)}px`);
    film.style.setProperty("--my", `${((.5 - e.clientY / innerHeight) * 10).toFixed(1)}px`);
  }, {passive: true});
}

/* ---------- Le prompt ---------- */
const ask = $("ask"), inp = $("ask-in"), ph = $("ask-ph"), help = $("help"), guide = $("guide");
const EX = ["Un studio à Lyon, 600 € max, près d'un métro, pour septembre", "Une coloc à Paris pour mon alternance, 750 € max", "Un T1 meublé à Bordeaux, calme, moins de 650 €", "Une chambre à Lille près de la fac, 450 € max"];
let tyOn = false, tyT = 0, tyI = 0, tyC = 0, tyDir = 1;
function typer(on){
  if (on === tyOn) return; tyOn = on; clearTimeout(tyT);
  if (on && !reduced) tyStep(); else if (reduced) ph.textContent = EX[0];
}
function tyStep(){
  if (!tyOn) return;
  const s = EX[tyI];
  tyC += tyDir; ph.textContent = s.slice(0, tyC);
  let wait = tyDir > 0 ? 38 + Math.random() * 40 : 14;
  if (tyDir > 0 && tyC >= s.length) { tyDir = -1; wait = 2300; }
  else if (tyDir < 0 && tyC <= 0) { tyDir = 1; tyI = (tyI + 1) % EX.length; wait = 450; }
  tyT = setTimeout(tyStep, wait);
}
const syncHas = () => ask.classList.toggle("has", inp.value.length > 0);
inp.addEventListener("input", syncHas);
inp.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask.requestSubmit ? ask.requestSubmit() : ask.dispatchEvent(new Event("submit", {cancelable: true})); } });
/* « Je ne sais pas quoi écrire » : quatre questions, la phrase s'écrit toute seule */
const GA = {city: "", type: "", budget: "", when: ""};
/* Le bandeau monte du bas : il vit dans <body> (aucun parent transformé) et la recherche remonte juste au-dessus */
const hero = ask.closest(".hero");
function liftHero(){
  if (guide.hidden) { hero.style.translate = ""; return; }
  hero.style.translate = "";
  /* hauteur réelle, sans l'animation d'entrée qui décale le bandeau */
  const a = ask.getBoundingClientRect(), gTop = innerHeight - (parseFloat(getComputedStyle(guide).bottom) || 0) - guide.offsetHeight;
  const lift = Math.max(0, Math.min(a.bottom + 16 - gTop, a.top - 12));
  hero.style.translate = lift ? `0 ${-Math.round(lift)}px` : "";
}
function openGuide(){
  if (guide.parentNode !== document.body) document.body.appendChild(guide);
  guide.hidden = false; help.setAttribute("aria-expanded", "true");
  liftHero();
}
function closeGuide(){ guide.hidden = true; help.setAttribute("aria-expanded", "false"); liftHero(); }
addEventListener("resize", () => { if (!guide.hidden) liftHero(); });
help.addEventListener("click", () => guide.hidden ? openGuide() : closeGuide());
$("g-ok").addEventListener("click", () => { closeGuide(); inp.focus(); });
guide.addEventListener("click", e => {
  const b = e.target.closest("button[aria-pressed]"); if (!b) return;
  const q = b.closest(".gq").dataset.q, on = b.getAttribute("aria-pressed") !== "true";
  b.parentElement.querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", "false"));
  b.setAttribute("aria-pressed", String(on)); GA[q] = on ? b.textContent : "";
  const parts = [];
  parts.push(`Je cherche ${GA.type ? GA.type.toLowerCase().replace("un t1", "un T1") : "un logement"}${GA.city ? ` à ${GA.city}` : ""}`);
  if (GA.budget) parts.push(`${GA.budget} max charges comprises`);
  if (GA.when) parts.push(GA.when === "Dès que possible" ? "dès que possible" : `pour ${GA.when.toLowerCase()}`);
  inp.value = parts.join(", ") + "."; syncHas();
  $("g-ph").textContent = inp.value;
});
addEventListener("keydown", e => { if (e.key === "Escape" && !guide.hidden) closeGuide(); });
document.addEventListener("pointerdown", e => { if (!guide.hidden && !ask.contains(e.target) && !guide.contains(e.target)) closeGuide(); });

/* « Essayer maintenant » et « Lancer les agents de gestion » : on crée son compte, puis on arrive dans l'workspace propriétaire.
   La recherche tapée ici est gardée : dans l'espace, on ne la redemande pas. */
const esp = $("esp"), cptF = $("cpt-f");
let cptMode = "creer", cptBack = null;
const store = {
  get(k){ try { return JSON.parse(localStorage.getItem(k)); } catch (x) { return null; } },
  set(k, v){ try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, JSON.stringify(v)); } catch (x) {} }
};
function cptSetMode(m){
  cptMode = m;
  const login = m === "connexion";
  $("cpt-h").textContent = login ? "Content de te revoir." : "Crée ton compte.";
  $("cpt-em").textContent = login ? "Tes agents t'attendent." : "Tes agents s'occupent du reste.";
  $("cpt-p").hidden = login;
  $("cpt-pre").hidden = login; $("cpt-acc").hidden = login;
  cptF.mdp.autocomplete = login ? "current-password" : "new-password";
  cptF.mdp.placeholder = login ? "Ton mot de passe" : "8 caractères minimum";
  $("cpt-gol").textContent = login ? "Me connecter" : "Créer mon compte";
  $("forgot-go").hidden = !login;
  $("reset-f").hidden = true;
  $("cpt-swt").textContent = login ? "Pas encore de compte ?" : "Déjà un compte ?";
  $("cpt-sw").textContent = login ? "Créer un compte" : "Se connecter";
  $("cpt-err").hidden = true;
}
function openEsp(from){
  /* Déjà connecté : on va directement dans l'espace */
  if (store.get("pf-moi")) { goEspace(); return; }
  cptBack = from || $("try");
  const q = store.get("pf-recherche");
  $("cpt-q").hidden = !q; $("cpt-qt").textContent = q ? `« ${q} »` : "";
  cptSetMode("creer");
  esp.hidden = false; de.classList.add("lock");
  (cptF.prenom).focus({preventScroll: true});
}
function closeEsp(){ if (esp.hidden) return; esp.hidden = true; de.classList.remove("lock"); if (cptBack) cptBack.focus({preventScroll: true}); }
function goEspace(){ location.href = "espace.html"; }
$("try").addEventListener("click", e => { e.preventDefault(); openEsp($("try")); });
/* Barre du haut : « Viens essayer », ou « Mon espace » quand on a déjà un compte */
$("tcta").addEventListener("click", () => openEsp($("tcta")));
if (store.get("pf-moi")) $("tcta-l").textContent = "Mon espace";
$("esp-x").addEventListener("click", closeEsp);
esp.addEventListener("click", e => { if (e.target === esp) closeEsp(); });
addEventListener("keydown", e => { if (e.key === "Escape") closeEsp(); });
$("esp-go").addEventListener("click", () => { closeEsp(); goTo(1); });
$("cpt-sw").addEventListener("click", () => { cptSetMode(cptMode === "creer" ? "connexion" : "creer"); (cptMode === "creer" ? cptF.prenom : cptF.email).focus(); });
$("forgot-go").addEventListener("click", () => { $("reset-f").hidden = false; $("reset-email").focus(); });
$("reset-f").addEventListener("submit", async e => {
  e.preventDefault();
  const email = $("reset-email").value.trim(), prenom = $("reset-prenom").value.trim(), msg = $("reset-msg");
  msg.hidden = false; msg.textContent = "Préparation du lien…";
  try {
    const r = await fetch("api/mot-de-passe-oublie", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({email, prenom})});
    const j = await r.json().catch(() => ({}));
    msg.textContent = r.ok ? (j.message || "Si les informations correspondent, un lien sera envoyé.") : (j.detail || "Impossible de préparer le lien.");
  } catch (x) { msg.textContent = "Le serveur ne répond pas. Réessaie dans un instant."; }
});
$("cpt-eye").addEventListener("click", e => {
  const on = cptF.mdp.type === "password"; cptF.mdp.type = on ? "text" : "password";
  e.currentTarget.setAttribute("aria-pressed", String(on));
  e.currentTarget.setAttribute("aria-label", on ? "Masquer le mot de passe" : "Afficher le mot de passe");
});
/* Le compte est créé par le serveur du site (api/compte) : mot de passe chiffré, jamais gardé dans le navigateur.
   Si le serveur ne répond pas, on le dit : on n'ouvre jamais l'espace sans que le compte existe. */
const COMPTE_URL = "api/compte";
cptF.addEventListener("submit", async e => {
  e.preventDefault();
  const f = cptF, err = $("cpt-err"), btn = $("cpt-go"), login = cptMode === "connexion";
  const d = {action: cptMode, prenom: f.prenom.value.trim(), email: f.email.value.trim(), mdp: f.mdp.value, site: f.site.value};
  const say = m => { err.textContent = m; err.hidden = !m; };
  if (!login && !d.prenom) return say("Dis-nous ton prénom."), f.prenom.focus();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(d.email)) return say("Cette adresse e-mail ne semble pas complète."), f.email.focus();
  if (!login && d.mdp.length < 8) return say("Ton mot de passe doit faire au moins 8 caractères."), f.mdp.focus();
  if (login && !d.mdp) return say("Entre ton mot de passe."), f.mdp.focus();
  if (!login && !f.accord.checked) return say("Coche la case pour qu'on puisse créer ton compte.");
  say(""); btn.disabled = true; btn.classList.add("busy");
  try {
    const r = await fetch(COMPTE_URL, {method: "POST", credentials: "same-origin", headers: {"Content-Type": "application/json"}, body: JSON.stringify(d)});
    const j = await r.json().catch(() => ({}));
    if (!r.ok) { say(j.erreur || "Ton compte n'a pas pu être créé. Réessaie dans un instant."); return; }
    store.set("pf-moi", {prenom: j.prenom || d.prenom, email: j.email || d.email});
    goEspace();
  } catch (x) {
    say("Le serveur ne répond pas. Réessaie dans un instant.");
  } finally { btn.disabled = false; btn.classList.remove("busy"); }
});

/* Plus tard : la phrase part vers le service de recherche. Aujourd'hui, on la lit ici. */
function sendSearch(text){ return Promise.resolve(parse(text)); }
ask.addEventListener("submit", e => {
  e.preventDefault();
  /* La phrase tapée est gardée pour l'workspace propriétaire. Rien d'écrit : l'espace la demandera en premier. */
  const v = inp.value.trim();
  closeGuide();
  store.set("pf-recherche", v || null);
  if (v) sendSearch(v).then(c => { CRIT = c; personalize(); });
  openEsp($("go"));
});

/* ---------- Dossiers reçus : les pièces arrivent, entrent dans le dossier, sont vérifiées, certifiées,
   puis le même dossier part avec chaque participanture ----------
   Tout suit le défilement (on avance, ça avance ; on remonte, ça rembobine). Pièces et données fictives,
   marquées « Spécimen », sans logo officiel. Plus tard : les vraies pièces déposées et un vrai service de vérification. */
const dst = $("dstage"), dz = $("dz"), DOCS = [...dst.querySelectorAll(".doc")];
const DSZ = DOCS.map(d => d.classList.contains("card") ? [236, 149] : [190, 269]);
const AGT = {D: ["L'Agent", "#8EA2FF"], G: ["L'Agent", "#8EA2FF"]};
/* Ce que vérifie chaque agent ; chaque repère pointe l'élément data-a="n" de la pièce. La miniature = la pièce comparée */
const CHK = [
  {a: "D", c: [["Photo conforme"], ["Numéro de document valide"], ["Bande MRZ lisible et cohérente"]]},
  {a: "G", c: [["Entreprise active, SIRET vérifié"], ["Contrat jusqu'en août 2027"], ["Signé par l'employeur et par toi"]]},
  {a: "G", c: [["Même employeur", "ton contrat"], ["Net cohérent avec le salaire", "ton contrat"], ["Trois mois consécutifs"]]},
  {a: "D", c: [["QR code authentique"], ["Même nom", "ta pièce d'identité"], ["Couvre ton loyer"]]},
  {a: "G", c: [["Revenus cohérents", "tes fiches de paie"], ["Référence de l'avis vérifiée"], ["C'est bien l'avis 2026"]]}
];
const CAP = ["L'Agent examine ta pièce d'identité, recto et verso.", "L'Agent lit ton contrat d'apprentissage.", "L'Agent rapproche tes fiches de paie de ton contrat.", "L'Agent authentifie ton visa Visale.", "L'Agent croise ton avis d'imposition avec tes fiches de paie."];
/* Deux mises en scène : écran large et téléphone. Coordonnées de la scène (W × H) */
const LAYS = {
  d: {W: 1200, H: 660, back: [380, 330, 440, 290], front: [366, 452, 468, 208], foldS: .74,
      fold: [[535, 418, -6], [572, 404, -2], [610, 404, 2], [648, 412, 6], [600, 410, 0]],
      fan: [[200, 205, -9, 16], [468, 185, -3, 6], [735, 185, 3, -6], [1002, 205, 9, -16]], fanS: .9,
      ver: [600, 236], verS: 1.42, seal: [790, 500], bub: [790, 90], co: "side",
      from: [[-280, -180, -55, 45, -70], [1480, -220, 50, 40, 70], [-320, 860, 40, -45, -60], [1520, 840, -45, -50, 60], [600, 1080, 12, 30, 0]],
      ru: {cards: [[200, 110], [200, 236], [200, 362], [1000, 110], [1000, 236], [1000, 362]], from: [600, 456], stat: [600, 236], half: 140}},
  m: {W: 400, H: 600, back: [40, 402, 320, 186], front: [28, 470, 344, 130], foldS: .5,
      fold: [[158, 446, -6], [184, 440, -2], [212, 440, 2], [238, 444, 6], [200, 442, 0]],
      fan: [[110, 150, -7, 10], [292, 140, 5, -8], [112, 318, 4, 8], [292, 310, -6, -10]], fanS: .62,
      ver: [200, 165], verS: .98, seal: [318, 458], bub: [44, 268], co: "below",
      from: [[-220, -180, -55, 45, -70], [640, -200, 50, 40, 70], [-240, 820, 40, -45, -60], [640, 800, -45, -50, 60], [200, 1000, 12, 30, 0]],
      ru: {cards: [[104, 44], [296, 44], [104, 118], [296, 118], [104, 192], [296, 192]], from: [200, 474], stat: [200, 300], half: 93}}
};
/* Le calendrier de la page (en part de la page) */
/* Seules trois pièces sont vérifiées : la carte d'identité, les fiches de paie et l'avis d'impôt.
   Le contrat et le visa entrent dans le dossier sans passer au contrôle. */
const VER = [0, 2];
const TL = {arr: .045, arrStep: .025, arrDur: .1, into: .2, intoStep: .017, intoDur: .055, V0: .3, VW: .12,
            miss: .54, av: [.575, .615, .69, .72], cert: .73, R0: .78, Rstep: .025, Rdur: .045};
let LY = LAYS.d, coKey = "", coDoc = -1, coN = 0, capKey = "", dLast = "", RP = [];
function layD(){
  LY = narrow() ? LAYS.m : LAYS.d;
  dst.style.width = `${LY.W}px`; dst.style.height = `${LY.H}px`;
  const r = dz.getBoundingClientRect();
  dst.style.setProperty("--sk", Math.min(1.25, r.width / LY.W, (r.height - 46) / LY.H).toFixed(4));
  const box = (el, b) => { el.style.left = `${b[0]}px`; el.style.top = `${b[1]}px`; el.style.width = `${b[2]}px`; el.style.height = `${b[3]}px`; };
  box($("fback"), LY.back); box($("ffront"), LY.front);
  const [w, h] = DSZ[4], S = LY.verS;
  box($("ghost"), [LY.ver[0] - w * S / 2, LY.ver[1] - h * S / 2, w * S, h * S]);
  const sl = $("seal2"); sl.style.left = `${LY.seal[0]}px`; sl.style.top = `${LY.seal[1]}px`;
  const gb = $("gbub"); gb.style.left = `${LY.bub[0]}px`; gb.style.top = `${LY.bub[1]}px`;
  $("leads").setAttribute("viewBox", `0 0 ${LY.W} ${LY.H}`);
  $("rpaths").setAttribute("viewBox", `0 0 ${LY.W} ${LY.H}`);
  const rs = $("rstat"); rs.style.left = `${LY.ru.stat[0]}px`; rs.style.top = `${LY.ru.stat[1]}px`;
  buildReuse();
  coKey = ""; coDoc = -2;
}
/* Les participantures qui reçoivent le même dossier (celles de la nuit, d'après ta recherche) */
function buildReuse(){
  const ru = LY.ru, items = LIST.filter(l => !l.out).slice(0, 6), box = $("reuse"), svg = $("rpaths");
  box.innerHTML = items.map((l, k) => `<div class="rc" style="left:${ru.cards[k][0]}px;top:${ru.cards[k][1]}px"><img src="photos/annonce-${l.ph}.jpg" alt=""><span><b>${esc(typeLabel(l.kind))} · ${esc(l.where.split(",")[0])}</b><small><i><svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></i>Dossier joint</small></span></div>`).join("");
  svg.innerHTML = "";
  RP = items.map((_, k) => {
    const [cx, cy] = ru.cards[k], left = cx < LY.W / 2, ex = cx + (left ? ru.half : -ru.half), [fx, fy] = ru.from;
    const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
    p.setAttribute("d", `M${fx} ${fy} Q${(fx + ex) / 2} ${Math.min(fy, cy) - (narrow() ? 30 : 70)} ${ex} ${cy}`);
    svg.appendChild(p);
    const fly = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    fly.setAttribute("class", "fly"); fly.setAttribute("width", "10"); fly.setAttribute("height", "13"); fly.setAttribute("rx", "1.5"); fly.style.opacity = "0";
    svg.appendChild(fly);
    const len = p.getTotalLength ? p.getTotalLength() : 400;
    p.style.strokeDasharray = `${len}`; p.style.strokeDashoffset = `${len}`;
    return {p, fly, len, card: box.children[k], q: -1};
  });
}
function anc(i, j){
  const d = DOCS[i], el = d.querySelector(`[data-a="${j}"]`); if (!el) return [.5, .5];
  let x = el.offsetWidth / 2, y = el.offsetHeight / 2, e = el;
  while (e && e !== d) { x += e.offsetLeft; y += e.offsetTop; e = e.offsetParent; }
  const [w, h] = DSZ[i]; return [x / w, y / h];
}
const Pz = (x, y, rz = 0, rx = 0, ry = 0, sc = 1) => ({x, y, rz, rx, ry, sc});
const mixP = (a, b, t) => ({x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t), rz: lerp(a.rz, b.rz, t), rx: lerp(a.rx, b.rx, t), ry: lerp(a.ry, b.ry, t), sc: lerp(a.sc, b.sc, t)});
function docState(i, s, now){
  const L = LY, Kf = L.fold[i], K = Pz(Kf[0], Kf[1], Kf[2], 0, 0, L.foldS), V = Pz(L.ver[0], L.ver[1], 0, 0, 0, L.verS);
  if (i === 4) {
    /* La pièce manquante arrive par le bas, comme envoyée depuis ton téléphone */
    const [a0, a1, r0, r1] = TL.av, a = sm(cl((s - a0) / (a1 - a0))), r = sm(cl((s - r0) / (r1 - r0)));
    if (a <= 0) return null;
    const A = L.from[4];
    let p = mixP(Pz(A[0], A[1], A[2], A[3], A[4], 1.2), V, a);
    if (r > 0) { p = mixP(p, K, r); p.rx -= Math.sin(r * Math.PI) * 14; }
    const hold = a >= 1 && r <= 0;
    return {p, inF: r > .28, hold, flip: false, v: cl((s - a1) / (r0 - a1)), ok: s > r0 - .005};
  }
  const A = L.from[i], F = L.fan[i];
  const a = sm(cl((s - (TL.arr + i * TL.arrStep)) / TL.arrDur)), b = sm(cl((s - (TL.into + i * TL.intoStep)) / TL.intoDur));
  if (a <= 0) return null;
  let p = mixP(Pz(A[0], A[1], A[2], A[3], A[4], 1.15), Pz(F[0], F[1], F[2], 0, F[3], L.fanS), a);
  const float = a * (1 - b);
  p.y += Math.sin(now / 760 + i * 1.7) * 6 * float; p.rz += Math.sin(now / 900 + i) * 1.3 * float;
  if (b > 0) { p = mixP(p, K, b); p.rx -= Math.sin(b * Math.PI) * 16; }
  let inF = b > .02, hold = false, v = 0;
  const wi = VER.indexOf(i), vv = wi < 0 ? -1 : (s - (TL.V0 + wi * TL.VW)) / TL.VW;
  if (vv > 0 && vv < 1) {
    const up = sm(cl(vv / .2)), dn = sm(cl((vv - .8) / .2));
    p = mixP(K, V, up); p.rx = Math.sin(up * Math.PI) * 22;
    if (dn > 0) { p = mixP(p, K, dn); p.rx = -Math.sin(dn * Math.PI) * 18; }
    inF = !(up > .72 && dn < .28);
    hold = up >= 1 && dn <= 0; v = vv;
  }
  /* L'Agent retourne la carte pour lire la bande au verso */
  return {p, inF, hold, flip: i === 0 && hold && v > .52, v, ok: wi >= 0 && s > TL.V0 + wi * TL.VW + TL.VW * .72};
}
let coShown = new Set();
function drawCO(i, vis){
  const box = $("callouts"), svg = $("leads"), cu = $("dcur");
  box.innerHTML = ""; svg.innerHTML = "";
  if (i !== coDoc) { coDoc = i; coShown = new Set(); }
  if (i < 0) { cu.classList.remove("on"); return; }
  const L = LY, [w, h] = DSZ[i], S = L.verS, cx = L.ver[0], cy = L.ver[1];
  const left = cx - w * S / 2, top = cy - h * S / 2, right = cx + w * S / 2, bottom = cy + h * S / 2, ag = AGT[CHK[i].a];
  cu.style.setProperty("--c", ag[1]); cu.querySelector("span").textContent = ag[0]; cu.classList.add("on");
  const used = {l: [], r: []};
  let last = [cx - 30, top + 24], row = 0;
  vis.forEach(j => {
    const [txt, ref] = CHK[i].c[j], [ax, ay] = anc(i, j), px = left + ax * w * S, py = top + ay * h * S;
    let x, y, cls, ex, ey;
    if (L.co === "side") {
      cls = ax < .5 ? "l" : "r"; x = cls === "l" ? left - 72 : right + 72; y = py;
      /* La bulle de L'Agent occupe la droite : la vérification passe juste en dessous */
      const gb = $("gbub");
      if (cls === "r" && gb.classList.contains("on")) y = Math.max(y, L.bub[1] + gb.offsetHeight + 34);
      used[cls].forEach(u => { if (Math.abs(u - y) < 52) y = u + 52; }); used[cls].push(y);
      ex = x; ey = y;
    } else { cls = "c"; x = cx; y = bottom + 30 + row++ * 42; ex = px + (x - px) * .5; ey = y - 15; }
    last = [px, py];
    const stay = coShown.has(j) ? " stay" : "";
    const gg = document.createElementNS("http://www.w3.org/2000/svg", "g"), len = Math.ceil(Math.hypot(ex - px, ey - py));
    if (stay) gg.setAttribute("class", "stay");
    gg.innerHTML = `<line x1="${px.toFixed(1)}" y1="${py.toFixed(1)}" x2="${ex.toFixed(1)}" y2="${ey.toFixed(1)}" style="stroke-dasharray:${len};stroke-dashoffset:${stay ? 0 : len}"/><circle class="pulse" cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="5"/><circle class="dot" cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="4.5"/>`;
    svg.appendChild(gg);
    const c = document.createElement("span"); c.className = `co ${cls}${stay}`; c.style.left = `${x.toFixed(1)}px`; c.style.top = `${y.toFixed(1)}px`;
    c.innerHTML = `<i><svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></i><span>${esc(txt)}</span>${ref ? `<em>${esc(ref)}</em>` : ""}`;
    box.appendChild(c);
  });
  coShown = new Set(vis);
  cu.style.transform = `translate3d(${(last[0] + 4).toFixed(0)}px,${(last[1] + 2).toFixed(0)}px,0)`;
}
function renderDoss(s, now){
  let holdI = -1, holdV = 0, nOk = 0;
  DOCS.forEach((el, i) => {
    const st = docState(i, s, now);
    if (!st) { el.classList.remove("shown", "ok", "scan", "flip"); return; }
    el.classList.add("shown");
    const p = st.p, [w, h] = DSZ[i];
    el.style.transform = `translate3d(${(p.x - w / 2).toFixed(1)}px,${(p.y - h / 2).toFixed(1)}px,0) rotateX(${p.rx.toFixed(2)}deg) rotateY(${p.ry.toFixed(2)}deg) rotateZ(${p.rz.toFixed(2)}deg) scale(${p.sc.toFixed(4)})`;
    el.classList.toggle("in", st.inF); el.classList.toggle("scan", st.hold); el.classList.toggle("ok", st.ok); el.classList.toggle("flip", st.flip);
    if (st.ok) nOk++;
    if (st.hold) { holdI = i; holdV = st.v; }
  });
  /* Les repères visibles : sur la carte, ceux du recto puis, une fois retournée, celui du verso */
  let vis = [];
  if (holdI >= 0) {
    const th = holdI === 4 ? [.1, .36, .62] : holdI === 0 ? [.26, .4, .66] : [.26, .41, .56];
    vis = [0, 1, 2].filter(j => holdV > th[j]);
    if (holdI === 0) vis = holdV > .52 ? vis.filter(j => j === 2) : vis.filter(j => j < 2);
  }
  const key = holdI < 0 ? "" : `${holdI}:${vis.join("")}`;
  if (key !== coKey) { coKey = key; drawCO(holdI, vis); }
  $("ghost").classList.toggle("on", s > TL.miss && s < TL.av[0] + .005);
  const gb = $("gbub"), recv = s > TL.av[0] + .005;
  gb.classList.toggle("on", s > TL.miss + .005 && s < TL.av[2] - .025);
  if (gb.classList.contains("done") !== recv) {
    gb.classList.toggle("done", recv);
    $("gbub-t").textContent = recv ? "Reçu. Je vérifie qu'il colle avec tes fiches de paie." : "Il me manque ton avis d'impôt 2026. Tu le trouves sur impots.gouv, rubrique Documents.";
    $("gbub-b").textContent = recv ? "✓ Déposée" : "Déposer la pièce";
  }
  const cert = s > TL.cert; dst.classList.toggle("cert", cert);
  /* Le même dossier part avec chaque participanture */
  let sent = 0;
  RP.forEach((r, k) => {
    const q = cl((s - (TL.R0 + k * TL.Rstep)) / TL.Rdur);
    if (q === r.q) { if (q >= .95) sent++; return; }
    r.q = q;
    r.p.style.strokeDashoffset = `${(r.len * (1 - q)).toFixed(1)}`;
    if (q > 0 && q < 1) { const pt = r.p.getPointAtLength(r.len * q); r.fly.setAttribute("x", (pt.x - 5).toFixed(1)); r.fly.setAttribute("y", (pt.y - 6.5).toFixed(1)); r.fly.style.opacity = "1"; }
    else r.fly.style.opacity = "0";
    r.card.classList.toggle("on", q >= .95);
    if (q >= .95) sent++;
  });
  const reuse = s > TL.R0 - .005;
  $("rstat").classList.toggle("on", reuse); $("rs-n").textContent = sent;
  const lbl = reuse ? `Certifié · joint à ${sent} participanture${sent > 1 ? "s" : ""}` : cert ? "Dossier certifié" : (s > TL.miss && nOk < 3) ? `${nOk} / 3 · il manque une pièce` : `${nOk} / 3 pièces vérifiées`;
  if (lbl !== dLast) { dLast = lbl; $("ff-n").textContent = lbl; $("ff-bar").style.width = `${(nOk / 3 * 100).toFixed(1)}%`; }
  let cap, col = "#8EA2FF";
  if (s < TL.into) cap = "Photo, scan ou PDF : tout arrive au même endroit.";
  else if (s < TL.V0 - .005) cap = "Classées, puis mises à l'abri.";
  else if (s < TL.miss) { const i = VER[Math.max(0, Math.min(VER.length - 1, Math.floor((s - TL.V0) / TL.VW)))]; cap = CAP[i]; col = AGT[CHK[i].a][1]; }
  else if (s < TL.av[0]) { cap = "Il manque une pièce : on te dit laquelle et où la trouver."; col = "#E0855F"; }
  else if (s < TL.cert) { cap = CAP[4]; col = AGT.G[1]; }
  else if (s < TL.R0 - .005) { cap = "Identité, revenus, impôts : tout concorde."; col = "#7CE0A3"; }
  else { cap = "Ensuite, tes agents l'envoient pour chaque logement retenu."; col = "#7CE0A3"; }
  if (cap !== capKey) { capKey = cap; const sp = $("dcap").firstElementChild; sp.textContent = cap; sp.style.setProperty("--c", col); sp.classList.remove("swap"); void sp.offsetWidth; sp.classList.add("swap"); }
  return !reduced && s > .03 && s < .32;
}
CONT.dossier = renderDoss;
/* Un QR code de démonstration, toujours le même */
(() => {
  let h = ""; const R = (x, y, w, hh) => { h += `<rect x="${x}" y="${y}" width="${w}" height="${hh}"/>`; };
  const fin_ = (x, y) => { R(x, y, 7, 1); R(x, y + 6, 7, 1); R(x, y, 1, 7); R(x + 6, y, 1, 7); R(x + 2, y + 2, 3, 3); };
  fin_(0, 0); fin_(14, 0); fin_(0, 14);
  let seed = 7; const rnd = () => (seed = (seed * 9301 + 49297) % 233280) / 233280;
  for (let y = 0; y < 21; y++) for (let x = 0; x < 21; x++) { if ((x < 8 && y < 8) || (x > 12 && y < 8) || (x < 8 && y > 12)) continue; if (rnd() > .52) R(x, y, 1, 1); }
  $("qr").innerHTML = `<g fill="#1E2133">${h}</g>`;
})();

/* ---------- Jour et nuit : on traverse les annonces de la nuit ----------
   Les annonces flottent à différentes profondeurs ; en défilant, on avance entre elles.
   Les agents sont des points bleus qui clignotent : dans le décor (des dizaines au travail)
   et sur les photos qu'ils sont en train de vérifier. Photos fictives, étalonnées à la lumière du film ;
   au survol, la photo d'origine. */
const field = $("field");
/* Sur chaque photo : où regardent les agents (en % de la photo) et cadrage le plus flatteur */
const SPOT = {1: {d: [[22, 56], [72, 26], [55, 74]], op: "40% 50%"}, 2: {d: [[52, 24], [72, 64], [30, 60]], op: "55% 45%"}, 3: {d: [[50, 26], [30, 62], [72, 58]], op: "50% 50%"},
              4: {d: [[28, 34], [72, 40], [46, 76]], op: "40% 50%"}, 5: {d: [[40, 44], [22, 28], [66, 70]], op: "45% 55%"}, 6: {d: [[50, 52], [28, 30], [72, 64]], op: "50% 50%"},
              7: {d: [[38, 60], [62, 30], [24, 40]], op: "45% 50%"}, 8: {d: [[64, 46], [34, 38], [56, 76]], op: "55% 45%"}};
const FG = {
  d: {cw: 420, F: 1100, Z: 700, cam0: -1700, sx: 1, cy: .5, pos: [[-480, -30], [480, 60], [-360, 90], [540, -80], [-560, 20], [420, -30], [-450, 80], [500, -90]], fly: [1150, 420]},
  m: {cw: 226, F: 820, Z: 580, cam0: -1250, sx: 1, cy: .53, pos: [[-102, -150], [104, 118], [-98, 160], [108, -150], [-108, -26], [100, 36], [-100, 150], [104, -140]], fly: [440, 380]}
};
let FC = [], FLY = [], FLEN = 0;
function buildField(){
  const g = narrow() ? FG.m : FG.d;
  field.innerHTML = LIST.map((l, i) => {
    const [an, ac] = AG[l.a], sp = SPOT[l.ph] || {d: [[50, 50]], op: "50% 50%"};
    return `<article class="fc${l.out ? " out" : ""}" style="--cw:${g.cw}px" aria-label="${esc(typeLabel(l.kind))}, ${l.m2} m², ${esc(l.where)}, ${l.rent} € par mois. ${esc(an)} : ${esc(l.say)}">
      <div class="fph"><img src="photos/annonce-${l.ph}.jpg" alt="" loading="lazy" draggable="false" style="object-position:${sp.op}">
        ${[0, 1].map(k => `<i class="adot${l.out ? " bad" : ""}" style="left:${sp.d[k % sp.d.length][0]}%;top:${sp.d[k % sp.d.length][1]}%;--dd:${(k * .8).toFixed(2)}s"></i>`).join("")}
        ${l.out ? `<span class="fstamp">Écartée</span>` : `<span class="fscore"><i></i>${l.s} % pour toi</span>`}
        <span class="forig">Photo d'origine</span></div>
      <div class="fcap"><b>${esc(typeLabel(l.kind))} · ${l.m2} m² · ${fmt(l.rent)} €</b><small>${esc(l.where)}${QUART[CRIT.city] ? ", " + esc(CRIT.city) : ""}</small>
        <p class="fnote" style="--ac:${ac}"><span>${esc(an)}</span>${esc(l.say)}</p></div>
    </article>`;
  }).join("") + Array.from({length: narrow() ? 18 : 30}, () => `<span class="ffly"><i style="animation-delay:${(Math.random() * 2.4).toFixed(2)}s"></i></span>`).join("");
  FC = [...field.querySelectorAll(".fc")];
  FLEN = (FC.length - 1) * g.Z + 2600;
  let seed = 11; const rnd = () => (seed = (seed * 9301 + 49297) % 233280) / 233280;
  FLY = [...field.querySelectorAll(".ffly")].map((el, i) => ({el, x: (rnd() * 2 - 1), y: (rnd() * 2 - 1), z: g.cam0 + rnd() * FLEN, ph: rnd() * 6.28, s: .6 + rnd() * .8, sp: .7 + rnd() * .8, sx: null, sy: null}));
  FC.forEach((c, i) => { c._dots = [...c.querySelectorAll(".adot")]; c._sp = (SPOT[LIST[i].ph] || {d: [[50, 50]]}).d; });
}
/* ---------- Une journée de ta vie, qui passe toute seule ----------
   À gauche, toi (le ciel, l'heure, ce que tu fais) ; à droite, ce que tes agents font au même moment.
   La journée tourne en boucle (7 h → 7 h en 24 secondes) et on avance entre les annonces au même rythme,
   sans avoir à faire défiler la page. Les annonces tombent surtout en journée. */
const ICO = {cup: '<path d="M5 9h11v5a5 5 0 0 1-5 5h-1a5 5 0 0 1-5-5zM16 10h1.5a2.5 2.5 0 0 1 0 5H16M8.5 3.5v2.5M12 3.5v2.5"/>',
  book: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5zM4 20.5v-15M8.5 7.5h7"/>',
  fork: '<path d="M7 3v8M5 3v4.5a2 2 0 0 0 4 0V3M7 11v10M17.5 3c-2 2-3 5-3 8h3v10"/>',
  bag: '<rect x="3" y="7" width="18" height="13" rx="2.5"/><path d="M8.5 7V5.5a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2V7M3 12.5h18"/>',
  run: '<path d="M6 8v8M3 10v4M18 8v8M21 10v4M6 12h12"/>',
  glass: '<path d="M7 3h10l-1.2 6.5a3.9 3.9 0 0 1-7.6 0zM12 13.5V21M8.5 21h7"/>',
  moon: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>'};
const DAY = [[0, "Café", "cup"], [90, "En cours", "book"], [330, "Déjeuner", "fork"], [405, "Au bureau", "bag"], [660, "Sport", "run"], [780, "Dîner", "glass"], [1050, "Sommeil", "moon"]];
/* La lumière de chaque moment, derrière le mot */
const MOOD = ["rgba(246,196,150,.55)", "rgba(176,190,255,.5)", "rgba(248,214,128,.55)", "rgba(190,200,228,.55)", "rgba(142,162,255,.55)", "rgba(240,166,120,.5)", "rgba(96,110,214,.42)"];
const hm = m => { const t = 7 * 60 + m; return `${String(Math.floor(t / 60) % 24).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`; };
/* Un moment arrive : le mot se compose lettre à lettre, l'icône se dessine, la lumière change */
function showMoment(ai){
  const [st, label, ic] = DAY[ai], en = ai + 1 < DAY.length ? DAY[ai + 1][0] : 1440, w = $("mo-w");
  w.querySelectorAll(".mo-i:not(.leave)").forEach(o => { o.classList.add("leave"); setTimeout(() => o.remove(), 900); });
  const el = document.createElement("p"); el.className = "mo-i";
  el.innerHTML = `<svg class="mo-ic" viewBox="0 0 24 24" aria-hidden="true">${ICO[ic].replace(/<(path|rect)/g, '<$1 pathLength="1"')}</svg>`
    + `<span class="mo-t" aria-label="${label}">${[...label].map((ch, k) => `<span style="--i:${k}" aria-hidden="true">${ch === " " ? "&nbsp;" : ch}</span>`).join("")}</span>`;
  w.appendChild(el);
  $("mo-r").textContent = `${hm(st)} – ${hm(en)}`;
  $("you").style.setProperty("--mood", MOOD[ai]);
}
const CUM = (() => { const a = [0]; for (let m = 0; m < 1440; m++) { const h = (7 + m / 60) % 24; a.push(a[m] + (h >= 9 && h < 20 ? 1 : h >= 7 && h < 9 || h >= 20 && h < 23 ? .45 : .15)); } return a.map(v => v / a[1440]); })();
const DAYMS = 36000;
let EV = [], dayT0 = 0, dayLast = -1, actI = -1, evI = 0, minLast = -1;
/* Ce que font les agents pendant ce temps (minutes depuis 7 h) ; les lieux suivent ta recherche */
function buildEvents(){
  const ok = LIST.filter(l => !l.out), lab = l => `${typeLabel(l.kind)} ${l.m2} m², ${l.where.split(",")[0]}`;
  EV = [
    [40, "b", `Nouvelle annonce · ${lab(ok[1])} · lue en 30 s`],
    [115, "r", "Annonce écartée : virement demandé avant la visite"],
    [140, "g", `Retenue pour toi · ${lab(ok[0])} · ${ok[0].s} %`],
    [185, "b", "Photo prise au flash : vidéo demandée au propriétaire"],
    [270, "b", `Nouvelle annonce · ${lab(ok[2])} · lue en 1 min`],
    [345, "g", `Retenue pour toi · ${lab(ok[1])} · ${ok[1].s} %`],
    [430, "b", "Doublon repéré sur deux plateformes : ignoré"],
    [510, "g", "Candidature prête, elle attend ton accord"],
    [590, "r", "Loyer au-dessus du quartier : écartée"],
    [680, "b", `Nouvelle annonce · ${lab(ok[3])} · lue en 20 s`],
    [760, "g", `Retenue pour toi · ${lab(ok[2])} · ${ok[2].s} %`],
    [855, "g", "La régie a répondu : visite possible samedi"],
    [990, "b", `Nouvelle annonce · ${lab(ok[4])} · lue en 45 s`],
    [1150, "b", "Annonce republiée à l'identique : ignorée"],
    [1360, "g", `Retenue pour toi · ${lab(ok[3])} · ${ok[3].s} %`]
  ];
  dayLast = -1;
}
const SKY_UNUSED = [[0, [255, 214, 186]], [120, [178, 205, 255]], [600, [150, 176, 255]], [780, [238, 160, 130]], [900, [72, 80, 140]], [1080, [26, 30, 70]], [1340, [60, 64, 120]], [1440, [255, 214, 186]]];
function skyAt(m){ for (let k = 1; k < SKY.length; k++) if (m <= SKY[k][0]) { const [a, ca] = SKY[k - 1], [b, cb] = SKY[k], t = (m - a) / (b - a); return ca.map((v, j) => Math.round(v + (cb[j] - v) * t)); } return SKY[0][1]; }
function pushEv(ev){
  const feed = $("feed"), [mm, kind, txt] = ev, min = 7 * 60 + mm;
  const li = document.createElement("li"); li.className = `ev ${kind}`;
  li.innerHTML = `<time>${String(Math.floor(min / 60) % 24).padStart(2, "0")}:${String(min % 60).padStart(2, "0")}</time><i></i><span>${esc(txt)}</span>`;
  feed.prepend(li);
  while (feed.children.length > 3) feed.lastElementChild.remove();
  [...feed.children].forEach((c, k) => c.style.setProperty("--k", k));
}
function renderDay(now){
  if (!dayT0) dayT0 = now;
  const p = reduced ? .38 : ((now - dayT0) / DAYMS) % 1, mm = Math.floor(p * 1440);
  if (mm < dayLast) { $("feed").innerHTML = ""; evI = 0; }
  dayLast = mm;
  while (evI < EV.length && EV[evI][0] <= mm) pushEv(EV[evI++]);
  if (mm !== minLast) {
    minLast = mm;
    const min = 7 * 60 + mm;
    $("clock").textContent = `${String(Math.floor(min / 60) % 24).padStart(2, "0")}:${String(min % 60).padStart(2, "0")}`;
    const c = CUM[mm];
    $("c-read").textContent = fmt(Math.round(1286 * c)); $("c-out").textContent = Math.round(9 * c);
    $("c-keep").textContent = EV.filter(e => e[0] <= mm && e[1] === "g" && /Retenue/.test(e[2])).length;
    let ai = 0; DAY.forEach(([st], k) => { if (mm >= st) ai = k; });
    if (ai !== actI) { actI = ai; showMoment(ai); }
  }
  /* Les aiguilles : la journée passe en accéléré */
  const hrs = 7 + p * 24;
  $("hh").setAttribute("transform", `rotate(${((hrs % 12) * 30).toFixed(2)} 100 100)`);
  $("mh").setAttribute("transform", `rotate(${((hrs % 1) * 360).toFixed(2)} 100 100)`);
  /* Le temps passé dans le moment en cours */
  if (actI >= 0) { const st = DAY[actI][0], en = actI + 1 < DAY.length ? DAY[actI + 1][0] : 1440; $("mo-bar").style.transform = `scaleX(${cl((p * 1440 - st) / (en - st)).toFixed(3)})`; }
  /* Le rétroéclairage se voit davantage le soir */
  const hd = hrs % 24, night = hd >= 20 || hd < 6.5;
  const gl = $("cglow"); if (gl._n !== night) { gl._n = night; gl.setAttribute("opacity", night ? "1" : ".7"); $("cglow2").setAttribute("opacity", night ? ".95" : ".45"); }
  return p;
}
HOOK.nuit = () => {};
let keptLast = -1;
function renderField(s, now){
  if (!FC.length) return false;
  const p = renderDay(now);
  const g = narrow() ? FG.m : FG.d, W = innerWidth, H = innerHeight, F = g.F, sx = narrow() ? 1 : Math.max(1, W / 1440);
  /* On avance entre les annonces au rythme de la journée, en boucle sans couture */
  const L = FC.length * g.Z, cam = (reduced ? .38 : (now - dayT0) / DAYMS) * L, FO = F * .35, dmin = -F * .55;
  let best = null;
  FC.forEach((c, i) => {
    const d = ((i * g.Z - cam - dmin + 1500) % L + L) % L + dmin;
    if (d > 6000) { if (c.style.visibility !== "hidden") c.style.visibility = "hidden"; return; }
    if (c.style.visibility) c.style.visibility = "";
    const k = F / (F + d), [X, Y] = g.pos[i];
    const x = W / 2 + X * k * sx, y = H * g.cy + Y * k;
    const op = cl((L + dmin - 300 - d) / 900) * cl((d - dmin) / (F * .32));
    const blur = Math.min(7, d > FO ? (d - FO) / 430 : (FO - d) / 240);
    c.style.transform = `translate3d(${(x - g.cw / 2).toFixed(1)}px,${(y - g.cw * .5).toFixed(1)}px,0) scale(${k.toFixed(4)})`;
    c.style.opacity = op.toFixed(3);
    c.style.filter = blur > .3 ? `blur(${blur.toFixed(1)}px)` : "none";
    c.style.zIndex = String(Math.round(10000 - d));
    c.style.setProperty("--fog", (cl((d - 900) / 3200) * .75).toFixed(3));
    c.style.setProperty("--kb", (1.12 - .1 * cl(k)).toFixed(4));
    const insp = d > -F * .25 && d < F * .9;
    if (insp !== c.classList.contains("insp")) c.classList.toggle("insp", insp);
    if (insp) {
      /* Les agents passent d'un détail à l'autre de la photo : ils s'arrêtent, regardent, repartent */
      const P = c._sp, n = P.length;
      c._dots.forEach((dot, j) => {
        const ph = now / 1000 * .55 + j * (n / 2) + i * .37, seg = Math.floor(ph) % n, f = ph - Math.floor(ph), m = sm(cl((f - .42) / .58));
        const A = P[seg], B = P[(seg + 1) % n], wob = Math.sin(now / 420 + j * 2) * 1.2;
        dot.style.left = `${lerp(A[0], B[0], m) + wob}%`; dot.style.top = `${lerp(A[1], B[1], m) + Math.cos(now / 510 + j) * 1.2}%`;
      });
      if (!best || Math.abs(d - FO) < best.dd) best = {c, dd: Math.abs(d - FO), x, y, k};
    }
  });
  /* Les agents au travail : des points bleus qui volent ; une partie de l'essaim rejoint l'annonce qu'on regarde */
  const [SX, SY] = g.fly;
  let tgt = null;
  if (best) { const h = g.cw * .75 + 70, ph = g.cw * .375; tgt = {x: best.x, y: (best.y - g.cw * .5 + h / 2) + (ph - h / 2) * best.k, r: g.cw * .62 * best.k}; }
  FLY.forEach((f, i) => {
    let d = f.z - cam; while (d < -F * .5) { f.z += FLEN; d = f.z - cam; } while (d > FLEN - F * .5) { f.z -= FLEN; d = f.z - cam; }
    const k = F / (F + d), tt = now / 1000 * f.sp;
    let nx = W / 2 + (f.x * SX * sx + Math.sin(tt * .9 + f.ph) * 110 + Math.sin(tt * 2.3 + f.ph * 2) * 24) * k;
    let ny = H * g.cy + (f.y * SY + Math.cos(tt * .7 + f.ph) * 70 + Math.cos(tt * 1.9 + f.ph) * 16) * k;
    let sc = k * f.s, op = cl((5200 - d) / 1600) * cl((d + F * .5) / (F * .3)) * .95;
    if (tgt && i < 9) {
      const a = tt * 1.3 + i * .7, rr = tgt.r * (.55 + .45 * Math.sin(i * 1.7 + tt * .6));
      nx = tgt.x + Math.cos(a) * rr * 1.25; ny = tgt.y + Math.sin(a) * rr * .7; sc = .9 + .3 * Math.sin(tt * 2 + i); op = .95;
    }
    if (f.sx === null || reduced) { f.sx = nx; f.sy = ny; } else { f.sx += (nx - f.sx) * .06; f.sy += (ny - f.sy) * .06; }
    f.el.style.transform = `translate3d(${f.sx.toFixed(1)}px,${f.sy.toFixed(1)}px,0) scale(${sc.toFixed(3)})`;
    f.el.style.opacity = op.toFixed(3);
  });
  return !reduced;
}
CONT.nuit = renderField;


/* ---------- Ta participanture ---------- */
const cand = $("cand"), mbody = $("m-body");
let BODY = "", bodyN = -1;
/* Trois temps : la notif arrive (1), tu dis oui (2), le mail s'écrit (3), ton dossier se joint (4), c'est envoyé (5) */
const CCAP = [["Ton téléphone vibre : une annonce pour toi.", ""], ["Ton téléphone vibre : une annonce pour toi.", ""], ["Tu réponds oui, d'un geste.", ""],
  ["L'Agent écrit à la régie à ta place.", ""], ["Dossiers reçus complet est joint d'office.", ""], ["Envoyé à 07:42. L'Agent suit la réponse.", "ok"]];
let ccapT = "";
HOOK.participanture = s => {
  const k = s < .05 ? 0 : s < .19 ? 1 : s < .31 ? 2 : s < .7 ? 3 : s < .82 ? 4 : 5;
  if (cand.dataset.k !== String(k)) cand.dataset.k = k;
  const cap = CCAP[k];
  if (cap[0] !== ccapT) {
    ccapT = cap[0]; const sp = $("ccap").firstElementChild; sp.textContent = cap[0]; sp.className = cap[1];
    sp.style.setProperty("--c", cap[1] ? "var(--ok)" : "var(--blue)"); void sp.offsetWidth; sp.classList.add("swap");
  }
  const t = k < 3 ? 0 : cl((s - .35) / .31), n = Math.round(BODY.length * t);
  if (n !== bodyN) { bodyN = n; mbody.textContent = BODY.slice(0, n); }
  mbody.classList.toggle("typing", t > 0 && t < 1);
};

/* ---------- La visite ---------- */
const vis = $("vis");
HOOK.visite = s => {
  const k = s < .08 ? 0 : s < .32 ? 1 : s < .55 ? 2 : s < .76 ? 3 : 4;
  if (vis.dataset.k !== String(k)) { vis.dataset.k = k; $("call-st").textContent = k <= 1 ? "Appel entrant…" : k === 2 ? "En appel · 00:42" : "Appel terminé · 3 min"; }
};

/* ---------- Tes questions : une seule ouverte à la fois ---------- */
{
  const fqs = [...document.querySelectorAll("#faq .fq")];
  fqs.forEach(f => f.querySelector(".fq-q").addEventListener("click", () => {
    const open = !f.classList.contains("open");
    fqs.forEach(o => { const on = o === f && open; o.classList.toggle("open", on); o.querySelector(".fq-q").setAttribute("aria-expanded", String(on)); });
  }));
  /* Laisse ta question : simulé. Plus tard, la question partira vers l'équipe (même principe que sendSearch) */
  const fin = $("fq-in"), fsend = document.querySelector(".fq-send");
  if (fin) {
    fin.addEventListener("input", () => { fsend.disabled = !fin.value.trim(); fin.style.height = "auto"; fin.style.height = `${Math.min(180, Math.max(76, fin.scrollHeight))}px`; });
    $("fq-f").addEventListener("submit", e => { e.preventDefault(); if (!fin.value.trim()) return; $("fq-f").hidden = true; $("fq-done").hidden = false; });
  }
}
/* ---------- Tes garanties : les cartes défilent avec la page ; celle du centre joue sa scène ---------- */
const gt = $("gt"), gtr = $("gt-track"), GC = [...gtr.children], GB = [...$("gt-bar").children];
let gcW = 0, gcGap = 28, gcI = -1, gcDone = 0;
/* Chaque carte reçoit sa coche verte et son sceau « Garanti » */
GC.forEach((c, k) => {
  const h = c.querySelector("h3"); h.insertAdjacentHTML("afterbegin", '<span class="gv-ok" aria-hidden="true"></span>');
  c.insertAdjacentHTML("beforeend", `<span class="g-seal" aria-hidden="true"><svg viewBox="0 0 100 100"><defs><path id="gsp${k}" d="M50 50 m-37 0 a37 37 0 1 1 74 0 a37 37 0 1 1 -74 0"/></defs><circle class="gs-o" cx="50" cy="50" r="48"/><circle class="gs-r" cx="50" cy="50" r="44"/><circle class="gs-i" cx="50" cy="50" r="26"/><text><textPath href="#gsp${k}">GARANTI · PIAULE FICTION ·</textPath></text><path class="gs-k" d="M39 50.5l7.5 7.5 15-16"/></svg></span>`);
});
function layGT(){ gcW = GC[0].offsetWidth; gcGap = parseFloat(getComputedStyle(gtr).columnGap) || 28; gcI = -1; }
CONT.garanties = s => {
  if (!gcW) layGT();
  const p = cl((s - .08) / .8) * (GC.length - 1), W = gt.clientWidth;
  gtr.style.transform = `translate3d(${(W / 2 - gcW / 2 - p * (gcW + gcGap)).toFixed(1)}px,0,0)`;
  GC.forEach((c, i) => c.style.setProperty("--d", Math.min(1, Math.abs(i - p)).toFixed(3)));
  /* La carte arrivée au centre joue sa scène (une seule à la fois) ; tant que la page n'est pas là, aucune ne joue */
  const i = s > SC_AT ? Math.round(p) : -1;
  if (i !== gcI) {
    gcI = i; GC.forEach((c, k) => c.classList.toggle("on", k === i)); GB.forEach((b, k) => b.classList.toggle("on", k <= i));
    /* Une fois sa scène jouée, la carte garde son sceau */
    clearTimeout(gcDone); if (i >= 0) gcDone = setTimeout(() => GC[i].classList.add("done"), reduced ? 0 : 2950);
  }
  return false;
};

/* ---------- Tes biens se retrouve dans les pages suivantes ---------- */
function personalize(){
  buildList();
  const c = CRIT;
  buildEvents();
  buildField();
  const l = LIST[0], where = l.where, tl = typeLabel(l.kind);
  $("n-title").textContent = `Nouveau · ${tl} · ${l.m2} m² · ${fmt(l.rent)} € · ${where}`;
  $("n-text").textContent = `${l.s} % avec ta recherche. Ta participanture est prête.`;
  $("n-ph").src = `photos/annonce-${l.ph}.jpg`;
  $("m-obj").textContent = `Demande de visite · ${tl} ${l.m2} m², ${where}`;
  BODY = `Bonjour Madame Durand,\n\nVotre ${typeLower(l.kind)} de ${l.m2} m² à ${where} m'intéresse et je souhaite effectuer une visite. J'en profite pour vous joindre mon dossier complet.\n\nJe suis disponible dès cette semaine, aux horaires qui vous conviennent.\n\nBien à vous,\nLéa Martin`;
  bodyN = -1;
  $("call-s").textContent = `${c.city} · à propos du ${typeLower(l.kind)}, ${where}`;
  $("cal-t").textContent = `10:00 · Visite du ${typeLower(l.kind)}, ${where}`;
  $("vis-rent").textContent = `${fmt(c.budget)} € charges comprises`;
  buildReuse();
}

/* ---------- Bande-annonce ---------- */
const asBlob = (url, type) => fetch(url).then(r => r.ok ? r.blob() : Promise.reject()).then(b => URL.createObjectURL(b.type ? b : new Blob([b], {type})));
{
  const loopV = $("tc-loop");
  if (loopV && !reduced && !narrow()) {
    asBlob("intro/boucle.mp4", "video/mp4").catch(() => "intro/boucle.mp4").then(u => { loopV.src = u; loopV.play().catch(() => {}); });
    document.addEventListener("visibilitychange", () => { document.hidden ? loopV.pause() : loopV.play().catch(() => {}); });
  }
}
let trailerSrc = null, trailerFrom = null;
function trailerSource(){
  /* Fichier allégé (14 Mo, index en tête) : il se lit pendant qu'il se charge */
  return Promise.resolve("intro/intro-hd.mp4");
}
function openTrailer(from){
  const box = $("trailer"), v = $("trailer-v"), wait = $("trailer-wait");
  trailerFrom = from || null;
  box.hidden = false; de.classList.add("lock"); $("trailer-x").focus({preventScroll: true});
  if (v.src) { v.currentTime = 0; v.muted = false; v.play().catch(() => { v.muted = true; v.play().catch(() => {}); }); return; }
  wait.hidden = false;
  trailerSource().then(src => {
    if (box.hidden) return;
    v.preload = "auto"; v.src = src; v.muted = false;
    const ready = () => { wait.hidden = true; };
    v.addEventListener("playing", ready, {once: true}); v.addEventListener("canplay", ready, {once: true});
    v.play().catch(() => { v.muted = true; v.play().catch(() => {}); });
  });
}
function closeTrailer(){
  const box = $("trailer"); if (box.hidden) return;
  $("trailer-v").pause(); box.hidden = true; de.classList.remove("lock");
  if (trailerFrom) trailerFrom.focus({preventScroll: true});
}
document.querySelectorAll(".js-trailer").forEach(b => b.addEventListener("click", () => openTrailer(b)));
$("trailer-x").addEventListener("click", closeTrailer);
$("trailer-v").addEventListener("ended", closeTrailer);
/* Les crédits des musiques ne s'affichent que quand la vidéo est en pause, pas pendant la lecture */
["play", "playing"].forEach(ev => $("trailer-v").addEventListener(ev, () => $("trailer").classList.remove("paused")));
$("trailer-v").addEventListener("pause", () => $("trailer").classList.add("paused"));
addEventListener("keydown", e => { if (e.key === "Escape") closeTrailer(); });

/* ---------- Le lendemain matin : c'est toi qui envoies le message ---------- */
const convo = $("convo"), after = $("after"), compose = $("compose"), sendBtn = $("send"), ring = $("ring"), cText = $("c-text");
const MSG = "Papa, maman, j'ai le bail.", RING = 132, HOLD_MS = 900;
let holding = false, holdStart = 0, sentDone = false, timers = [], lastFrom = "";
const later = (ms, fn) => timers.push(setTimeout(fn, reduced ? Math.min(ms, 250) : ms));
const ARROW = '<path d="M12 19V5.5M6.5 11 12 5.5 17.5 11"/>', CHECK = '<path d="M6 12.5l4 4 8-9"/>';
function addMsg(side, text, from){
  const m = document.createElement("div"); m.className = `msg ${side} pop-now`;
  const label = side === "in" && from && from !== lastFrom ? `<span class="from">${from}</span>` : "";
  lastFrom = side === "in" ? from : "";
  m.innerHTML = `${label}<p class="bub">${text}</p>`; after.appendChild(m); follow(m); return m;
}
function addTyping(from){
  const m = document.createElement("div"); m.className = "msg in typing pop-now";
  const label = from !== lastFrom ? `<span class="from">${from}</span>` : "";
  m.innerHTML = `${label}<p class="bub" aria-label="${from} écrit"><i></i><i></i><i></i></p>`; after.appendChild(m); follow(m); return m;
}
function reply(from, text, wait){ const t = addTyping(from); later(wait, () => { t.remove(); addMsg("in", text, from); flash("c-ping"); }); }
/* La discussion défile dans son cadre, comme une vraie conversation : la page ne bouge pas */
function follow(){ const bd = $("chat-body"); bd.scrollTo({top: bd.scrollHeight, behavior: reduced ? "auto" : "smooth"}); }
const flash = c => { const ch = $("chat"); ch.classList.remove(c); void ch.offsetWidth; ch.classList.add(c); };
const setRing = k => { ring.style.strokeDashoffset = String(RING * (1 - k)); };
function holdFrame(now){ if (!holding) return; const k = cl((now - holdStart) / HOLD_MS); setRing(k); if (k >= 1) { send(); return; } requestAnimationFrame(holdFrame); }
function startHold(){ if (sentDone || holding) return; holding = true; holdStart = performance.now(); compose.classList.add("holding"); $("c-hint").textContent = "Garde le doigt dessus…"; requestAnimationFrame(holdFrame); }
function cancelHold(){ if (!holding) return; holding = false; compose.classList.remove("holding"); setRing(0); $("c-hint").textContent = "Presque. Garde le doigt dessus jusqu'au bout du cercle."; }
sendBtn.addEventListener("pointerdown", e => { e.preventDefault(); try { sendBtn.setPointerCapture(e.pointerId); } catch (err) {} startHold(); });
["pointerup", "pointercancel", "lostpointercapture"].forEach(ev => sendBtn.addEventListener(ev, cancelHold));
sendBtn.addEventListener("contextmenu", e => e.preventDefault());
sendBtn.addEventListener("keydown", e => { if ((e.key === " " || e.key === "Enter") && !e.repeat) { e.preventDefault(); startHold(); } });
sendBtn.addEventListener("keyup", e => { if (e.key === " " || e.key === "Enter") cancelHold(); });
function send(){
  holding = false; sentDone = true; compose.classList.remove("holding");
  try { navigator.vibrate && navigator.vibrate(18); } catch (err) {}
  setRing(1); sendBtn.disabled = true; sendBtn.classList.add("done"); $("send-ico").innerHTML = CHECK; sendBtn.setAttribute("aria-label", "Message envoyé");
  cText.textContent = ""; $("c-hint").textContent = "Envoyé."; lastFrom = ""; flash("c-sent");
  const out = addMsg("out", MSG), meta = document.createElement("span"); meta.className = "meta"; meta.textContent = "Distribué";
  later(250, () => burst(out.querySelector(".bub")));
  later(500, () => out.appendChild(meta));
  later(1500, () => { meta.textContent = "Lu à 09:14"; setRing(0); });
  later(1900, () => reply("Papa", "QUOI ?!", 1000));
  later(3050, () => { const tb = document.createElement("span"); tb.className = "tapback"; tb.textContent = "!!"; tb.setAttribute("aria-label", "Papa a réagi"); out.querySelector(".bub").appendChild(tb); });
  later(3500, () => reply("Maman", "On est tellement fiers de toi.", 1300));
  later(5300, () => reply("Papa", "On arrive samedi avec les cartons.", 1100));
  later(7000, () => reply("Maman", "Et la crémaillère, c'est quand ?", 1000));
  later(8400, () => { morph(true); $("resend").hidden = false; $("c-hint").textContent = "Ta famille est au courant."; });
}
$("resend").addEventListener("click", () => {
  timers.forEach(clearTimeout); timers = []; after.innerHTML = ""; lastFrom = ""; sentDone = false; $("chat").classList.remove("c-sent");
  sendBtn.disabled = false; sendBtn.classList.remove("done"); $("send-ico").innerHTML = ARROW; sendBtn.setAttribute("aria-label", "Maintiens pour envoyer le message");
  setRing(0); cText.textContent = MSG; $("c-hint").innerHTML = "Maintiens le bouton pour envoyer. <em>Celui-là, c'est toi qui l'envoies.</em>";
  $("resend").hidden = true; morph(false); compose.scrollIntoView({behavior: reduced ? "auto" : "smooth", block: "center"});
});
const cf = $("confetti"), cfx = cf.getContext("2d");
function burst(fromEl){
  if (reduced || !fromEl) return;
  const dp = Math.min(2, devicePixelRatio || 1);
  cf.hidden = false; cf.width = innerWidth * dp; cf.height = innerHeight * dp; cfx.setTransform(dp, 0, 0, dp, 0, 0);
  const r = fromEl.getBoundingClientRect(), ox = r.left + r.width / 2, oy = r.top + r.height / 2;
  const cols = ["#3653D9", "#8EA2FF", "#ffffff", "#B9532F", "#c9d0f0"];
  const ps = Array.from({length: 150}, () => { const a = -Math.PI / 2 + (Math.random() - .5) * Math.PI * 1.3, v = 6 + Math.random() * 9; return {x: ox, y: oy, vx: Math.cos(a) * v, vy: Math.sin(a) * v, w: 5 + Math.random() * 6, h: 3 + Math.random() * 5, rot: Math.random() * 6.28, vr: (Math.random() - .5) * .4, c: cols[Math.floor(Math.random() * cols.length)]}; });
  const t0 = performance.now();
  const step = now => {
    const el = now - t0; cfx.clearRect(0, 0, innerWidth, innerHeight);
    for (const p of ps) { p.vx *= .985; p.vy = p.vy * .985 + .32; p.x += p.vx; p.y += p.vy; p.rot += p.vr; cfx.save(); cfx.globalAlpha = Math.max(0, 1 - el / 2600); cfx.translate(p.x, p.y); cfx.rotate(p.rot); cfx.fillStyle = p.c; cfx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h); cfx.restore(); }
    if (el < 2600) requestAnimationFrame(step); else { cfx.clearRect(0, 0, innerWidth, innerHeight); cf.hidden = true; }
  };
  requestAnimationFrame(step);
}
const chip = $("morph"), cmWord = chip.querySelector(".cm-word");
let morphed = false, settleT = 0;
const chipWidth = () => cmWord.offsetWidth + parseFloat(getComputedStyle(chip).paddingLeft) * 2;
function morph(on){ morphed = on; clearTimeout(settleT); chip.classList.toggle("morphed", on); chip.classList.remove("settled"); chip.style.width = on ? `${chip.offsetHeight}px` : `${chipWidth()}px`; if (on) settleT = setTimeout(() => chip.classList.add("settled"), reduced ? 0 : 450); }
chip.style.width = `${chipWidth()}px`;
chip.addEventListener("click", () => morph(!morphed));
if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { if (!morphed) chip.style.width = `${chipWidth()}px`; layout(); layD(); layGT(); frame(); kick(); });
if ("IntersectionObserver" in window) {
  const io = new IntersectionObserver(es => es.forEach(e => {
    if (!e.isIntersecting) return; io.unobserve(e.target);
    if (e.target === convo) {
      convo.classList.add("play");
      if (!reduced && !sentDone) {
        cText.textContent = ""; cText.classList.add("typing"); let i = 0;
        timers.push(setTimeout(function type(){ i++; cText.textContent = MSG.slice(0, i); if (i < MSG.length && !sentDone) timers.push(setTimeout(type, 55)); else cText.classList.remove("typing"); }, 2300));
      }
    } else if (e.target === $("m-end") && !sentDone) setTimeout(() => { if (!morphed) morph(true); }, 700);
  }), {threshold: .35});
  io.observe(convo); io.observe($("m-end"));
} else convo.classList.add("play");

/* Le compteur d'agents bouge un peu, comme un vrai service la nuit */
setInterval(() => { if (cur === 0 && !document.hidden) { const n = $("live-n"); n.textContent = String(12 + Math.floor(Math.random() * 6)); } }, 4200);

/* ---------- Démarrage ---------- */
personalize();
let ticking = false;
const onScroll = () => { if (ticking) return; ticking = true; requestAnimationFrame(() => { ticking = false; frame(); }); };
addEventListener("scroll", onScroll, {passive: true});
let rzT = 0;


/* ---------- Ouverture : l'extrait du film en fond ; au défilement, la vidéo devient poussière de lumière ---------- */
{
  const ouv = $("ouverture"), v = $("ouv-v");
  if (ouv) {
    const stage = ouv.querySelector(".ouv-stage");
    if (v) {
      /* Lecture automatique bloquée (iPhone en économie d'énergie, applis) : on relance au premier geste */
      v.muted = true; v.defaultMuted = true; v.playsInline = true; v.setAttribute("muted", ""); v.setAttribute("webkit-playsinline", "");
      v.addEventListener("playing", () => v.classList.add("ready"));
      const go = () => { if (v.src && v.paused && scrollY < innerHeight * .9) { const pr = v.play(); if (pr) pr.catch(() => {}); } };
      const nudge = ["pointerdown", "touchstart", "touchmove", "scroll", "keydown", "wheel"];
      const poke = () => { go(); if (!v.paused || scrollY > innerHeight * 3) nudge.forEach(e => removeEventListener(e, poke, true)); };
      nudge.forEach(e => addEventListener(e, poke, {passive: true, capture: true}));
      v.src = "intro/accueil.mp4"; v.load(); go();
    }
    const pinned = !reduced && ("maskImage" in de.style || "webkitMaskImage" in de.style);
    if (pinned) { de.classList.add("ouv-pin", "ouv-hold"); layout(); }
    const ease = x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
    const dc = document.createElement("canvas"); dc.className = "ouv-dust"; dc.setAttribute("aria-hidden", "true");
    stage.insertBefore(dc, ouv.querySelector(".ouv-in"));
    const dg = dc.getContext("2d"), poster = new Image(); poster.src = "intro/accueil.jpg";
    const FW = 1440, FH = 810, KX0 = .54, KX1 = .87, KY0 = .07, KY1 = .97;
    let targets = null, keyLit = null, keyBloom = null, P = null, pW = 0, pH = 0, step = 6, ddpr = 1;
    /* Un grain = un petit point de lumière doux */
    const spark = document.createElement("canvas"); spark.width = spark.height = 32;
    { const sg = spark.getContext("2d"), gr = sg.createRadialGradient(16, 16, 0, 16, 16, 16);
      gr.addColorStop(0, "rgba(255,255,255,1)"); gr.addColorStop(.25, "rgba(232,238,255,.95)"); gr.addColorStop(.5, "rgba(170,188,255,.3)"); gr.addColorStop(1, "rgba(142,162,255,0)");
      sg.fillStyle = gr; sg.fillRect(0, 0, 32, 32); }
    /* La clé entière, lue dans la première image du film : où vont les grains, et sa lumière quand elle s'éclaire */
    {
      const im = new Image();
      im.onload = () => {
        const w = 720, h = 405, c = document.createElement("canvas"); c.width = w; c.height = h;
        const kg = c.getContext("2d"); kg.drawImage(im, 0, 0, w, h);
        let id; try { id = kg.getImageData(0, 0, w, h); } catch (e) { return; }
        const d = id.data, pts = [];
        for (let y = 0; y < h; y++) {
          let br = 0, bgc = 0, bb = 0, nb = 0;
          for (let x = w * .05 | 0; x < w * .45; x += 3) { const k = (y * w + x) * 4; br += d[k]; bgc += d[k + 1]; bb += d[k + 2]; nb++; }
          br /= nb; bgc /= nb; bb /= nb;
          for (let x = 0; x < w; x++) {
            const k = (y * w + x) * 4, r = d[k], gg = d[k + 1], b = d[k + 2], l = .3 * r + .59 * gg + .11 * b;
            const inKey = x > KX0 * w && x < KX1 * w && y > KY0 * h && y < KY1 * h && Math.abs(r - br) + Math.abs(gg - bgc) + Math.abs(b - bb) > 48 && l > .3 * br + .59 * bgc + .11 * bb + 14;
            if (inKey) { if (Math.random() < .5) pts.push((x + Math.random()) / w, (y + Math.random()) / h); d[k] = Math.min(255, r * .6 + 120); d[k + 1] = Math.min(255, gg * .6 + 130); d[k + 2] = 255; d[k + 3] = Math.min(255, 60 + l * 1.6); }
            else d[k + 3] = 0;
          }
        }
        kg.putImageData(id, 0, 0); keyLit = c;
        const bl = document.createElement("canvas"); bl.width = w / 2; bl.height = h / 2; const bg = bl.getContext("2d");
        bg.filter = "blur(6px)"; bg.drawImage(c, 0, 0, w / 2, h / 2); keyBloom = bl;
        if (pts.length > 400) { targets = pts; P = null; }
      };
      im.src = "film/t1/001.webp";
    }
    const ringPts = () => { const a = []; for (let i = 0; i < 900; i++) { const t = Math.random() * Math.PI * 2, rr = .12 + Math.random() * .012; a.push(.778 + Math.cos(t) * rr * FH / FW, .241 + Math.sin(t) * rr); } return a; };
    /* Même cadrage que le film du fond au début (la clé à droite) */
    /* Les grains visent la clé là où le film la dessine vraiment : on mesure le film à l'écran (barre de défilement et léger mouvement de souris compris) */
    const cover = () => { const r = film.getBoundingClientRect(), sr = stage.getBoundingClientRect(), s2 = Math.max(r.width / FW, r.height / FH), dw = FW * s2, dh = FH * s2;
      return {dw, dh, ox: r.left - sr.left + (r.width - dw) * fxAt(0), oy: r.top - sr.top + (r.height - dh) * .5}; };
    function build(W, H){
      ddpr = Math.min(1.5, devicePixelRatio || 1); pW = W; pH = H;
      dc.width = Math.round(W * ddpr); dc.height = Math.round(H * ddpr);
      step = Math.max(5, Math.round(W / 260));
      const cols = Math.ceil(W / step), rows = Math.ceil(H / step);
      const sc = document.createElement("canvas"); sc.width = cols; sc.height = rows; const sg = sc.getContext("2d");
      const src = v && v.readyState >= 2 && v.videoWidth ? v : poster, iw = src.videoWidth || src.naturalWidth, ih = src.videoHeight || src.naturalHeight;
      let data = null;
      if (iw) { const s = Math.max(cols / iw, rows / ih); sg.drawImage(src, (cols - iw * s) / 2, (rows - ih * s) / 2, iw * s, ih * s); try { data = sg.getImageData(0, 0, cols, rows).data; } catch (e) {} }
      const {dw, dh, ox, oy} = cover(), T = targets || ringPts(), n = T.length / 2;
      P = [];
      for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) {
        const x0 = (i + Math.random()) * step, y0 = (j + Math.random()) * step, k = (Math.random() * n | 0) * 2;
        const tx = ox + T[k] * dw, ty = oy + T[k + 1] * dh;
        const dx = tx - x0, dy = ty - y0, dist = Math.hypot(dx, dy) || 1, sw = (Math.random() - .5) * .9 * dist;
        const q = (j * cols + i) * 4, r = data ? data[q] : 170, gg = data ? data[q + 1] : 180, b = data ? data[q + 2] : 210;
        P.push({x0, y0, tx, ty, cx: (x0 + tx) / 2 - dy / dist * sw, cy: (y0 + ty) / 2 + dx / dist * sw - H * (.12 + Math.random() * .25),
          d: .42 * (x0 / W) + Math.random() * .08, r, g: gg, b, tw: Math.random() * 6.283, z: .6 + Math.random() * .8});
      }
    }
    let dDone = false;
    function dust(u, W, H){
      /* Transition finie : plus rien n'est visible, on efface une fois et on arrête de dessiner (sinon 20 000 grains invisibles par image) */
      if (u >= 1) { if (!dDone) { dg.setTransform(1, 0, 0, 1, 0, 0); dg.clearRect(0, 0, dc.width, dc.height); dDone = true; } return; }
      dDone = false;
      if (u <= 0) { if (P) { dg.setTransform(1, 0, 0, 1, 0, 0); dg.clearRect(0, 0, dc.width, dc.height); } P = null; return; }
      if (!P || pW !== W || pH !== H) build(W, H);
      dg.setTransform(ddpr, 0, 0, ddpr, 0, 0); dg.clearRect(0, 0, W, H);
      const {dw, dh, ox, oy} = cover();
      /* La clé s'éclaire tout entière quand les grains arrivent, puis retrouve son verre */
      const lit = Math.sin(Math.PI * cl((u - .45) / .55));
      if (keyLit && lit > .01) {
        dg.globalCompositeOperation = "lighter";
        dg.globalAlpha = .9 * lit; dg.drawImage(keyBloom, ox, oy, dw, dh);
        dg.globalAlpha = .55 * lit; dg.drawImage(keyLit, ox, oy, dw, dh);
        dg.globalAlpha = 1;
      }
      const fade = 1 - cl((u - .86) / .14), span = .53;
      for (let pass = 0; pass < 2; pass++) {
        dg.globalCompositeOperation = pass ? "lighter" : "source-over";
        for (const o of P) {
          const w = cl((u - o.d) / span); if (w <= 0) continue;
          if ((w < .3) !== !pass) continue;
          const e = ease(w), m = 1 - e;
          const x = m * m * o.x0 + 2 * m * e * o.cx + e * e * o.tx, y = m * m * o.y0 + 2 * m * e * o.cy + e * e * o.ty;
          if (w < .3) {
            /* Début du vol : poussière très fine aux couleurs de la vidéo */
            const sh = cl(w * 10), sz = 2.2 * (1 - sh) + 1.2 * sh, c = cl(w * 3);
            dg.fillStyle = `rgb(${o.r + (205 - o.r) * c | 0},${o.g + (216 - o.g) * c | 0},${o.b + (255 - o.b) * c | 0})`; dg.fillRect(x - sz / 2, y - sz / 2, sz, sz);
          } else {
            /* Ensuite : des points de lumière doux qui scintillent */
            const sz = (1.4 + 1.9 * Math.sin(o.tw + u * 22) ** 2) * o.z * (1 - .3 * e);
            dg.globalAlpha = (.35 + .65 * cl((w - .3) / .2)) * fade * (.6 + .4 * Math.sin(o.tw * 3 + u * 14) ** 2);
            dg.drawImage(spark, x - sz / 2, y - sz / 2, sz, sz);
          }
        }
        dg.globalAlpha = 1;
      }
      dg.globalCompositeOperation = "source-over";
    }
    let oraf = 0, wmBox = null;
    const wm = ouv.querySelector(".ouv-wm .wm"), dock = document.querySelector(".top .lockup .wm");
    const step2 = () => {
      oraf = 0;
      const W = stage.clientWidth || innerWidth, H = stage.offsetHeight;
      const span = Math.max(1, ouv.offsetHeight - H), p = cl(-ouv.getBoundingClientRect().top / (pinned ? span : H));
      de.classList.toggle("at-ouv", p < .85);
      de.classList.toggle("ouv-tx", pinned && p > .22); de.classList.toggle("ouv-gone", pinned && p > .995);
      { const fr = $("fin").getBoundingClientRect(); de.classList.toggle("at-fin", fr.top < innerHeight && fr.bottom > 0); }
      if (pinned) {
        de.classList.toggle("ouv-hold", p < .72);
        const t = cl(p / .2);
        ouv.style.setProperty("--to", (1 - t).toFixed(3));
        ouv.style.setProperty("--ty", (-t * 40).toFixed(1) + "px");
        ouv.style.setProperty("--tb", (t * 8).toFixed(2) + "px");
        /* Le grand nom rétrécit et vole jusqu'au logo du menu */
        if (wm && dock && (wmBox || p > 0)) {
          if (p > 0 && (!wmBox || wmBox.W !== W)) { wm.style.transform = "none"; const a = wm.getBoundingClientRect(); wm.style.transform = ""; wmBox = {W, x: a.left, y: a.top, h: a.height}; }
          const b = dock.getBoundingClientRect(), d = ease(cl((p - .04) / .9)), s0 = b.height / wmBox.h;
          ouv.style.setProperty("--ws", (1 + (s0 - 1) * d).toFixed(4));
          ouv.style.setProperty("--wx", ((b.left - wmBox.x) * d).toFixed(1) + "px");
          ouv.style.setProperty("--wy", ((b.top - wmBox.y) * d).toFixed(1) + "px");
          ouv.style.setProperty("--wo", p < .97 ? "1" : "0");
          de.classList.toggle("wm-fly", p < .97);
        }
        const u = cl((p - .1) / .75);
        ouv.style.setProperty("--fr", (u / .5 * 100 - 6).toFixed(2));
        dust(u, W, H);
      }
      if (v && v.src) { if (p > .1 || document.hidden) { if (!v.paused) v.pause(); } else if (v.paused) v.play().catch(() => {}); }
    };
    const ask2 = () => { if (!oraf) oraf = requestAnimationFrame(step2); };
    addEventListener("scroll", ask2, {passive: true}); addEventListener("resize", () => { wmBox = null; ask2(); });
    document.addEventListener("visibilitychange", ask2);
    step2();
  }
}

addEventListener("resize", () => { clearTimeout(rzT); rzT = setTimeout(() => { layout(); layD(); layGT(); buildField(); fsize(); paint(shownT); frame(); kick(); }, 120); });
layout(); layD(); layGT(); fsize(); paint(0);
scrollTo(0, 0);
requestAnimationFrame(() => requestAnimationFrame(() => { frame(); de.classList.add("ready"); }));
})();
