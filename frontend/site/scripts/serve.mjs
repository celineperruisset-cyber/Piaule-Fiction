// Serveur de développement Piaule Fiction : aucune dépendance, Node 18+.
// - sert le site statique (dossier racine du projet), avec les requêtes Range pour les vidéos ;
// - répond à /api/* soit avec une API simulée en mémoire (API_MODE=mock, par défaut),
//   soit en relayant vers le backend canonique (API_MODE=proxy, API_TARGET=http://127.0.0.1:8000).
// Lancer : npm run dev   (ou : node scripts/serve.mjs)
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

// Lit .env s'il existe (sans écraser les variables déjà définies)
try {
  for (const line of fs.readFileSync(path.join(ROOT, ".env"), "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/);
    if (m && !(m[1] in process.env)) process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
} catch {}

const PORT = Number(process.env.PORT || 5173);
const HOST = process.env.HOST || "127.0.0.1";
const API_MODE = process.env.API_MODE || "mock";
const API_TARGET = process.env.API_TARGET || "http://127.0.0.1:8000";

// Dossiers du projet qui ne font pas partie du site publié
const PRIVATE = new Set(["scripts", "docs", "src", "node_modules", ".git"]);

const TYPES = {
  ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
  ".json": "application/json", ".svg": "image/svg+xml", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
  ".webp": "image/webp", ".mp4": "video/mp4", ".webm": "video/webm", ".woff2": "font/woff2", ".ico": "image/x-icon", ".txt": "text/plain; charset=utf-8"
};

function sendJSON(res, code, obj, cookie) {
  const b = Buffer.from(JSON.stringify(obj));
  const h = { "Content-Type": "application/json", "Cache-Control": "no-store", "Content-Length": b.length };
  if (cookie) h["Set-Cookie"] = cookie;
  res.writeHead(code, h); res.end(b);
}

// ---------- API simulée : même contrat que backend/main.py ----------
const comptes = new Map(); // email -> {prenom, sel, mdp}
const sessions = new Map(); // jeton -> email
const liste = new Set();
const recherches = new Map(); // email -> profiles
const profils = new Map(); // email -> profile
const documents = new Map(); // email -> document metadata
const mockListings = [
  {id: "listing-demo-001", title: "T2 lumineux, Lyon 6e", city: "Lyon", monthly_rent_eur: 890, source: "demo-source", risk_level: "low"},
  {id: "listing-demo-002", title: "Studio calme, Bordeaux Chartrons", city: "Bordeaux", monthly_rent_eur: 690, source: "demo-source", risk_level: "unknown"}
];
const EMAIL = /^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$/;
const hash = (mdp, sel) => crypto.scryptSync(mdp, sel, 32);

function multipartFields(req, body) {
  const match = String(req.headers["content-type"] || "").match(/boundary=([^;]+)/i);
  if (!match) return {};
  const boundary = `--${match[1].replace(/^"|"$/g, "")}`;
  const fields = {};
  for (const rawPart of body.toString("latin1").split(boundary).slice(1)) {
    const clean = rawPart.replace(/^(--)?\r\n/, "").replace(/\r\n(--)?\r\n?$/, "");
    const sep = clean.indexOf("\r\n\r\n");
    if (sep < 0) continue;
    const headers = clean.slice(0, sep);
    const content = clean.slice(sep + 4);
    const name = headers.match(/name="([^"]+)"/i)?.[1];
    if (!name) continue;
    const filename = headers.match(/filename="([^"]*)"/i)?.[1] || "";
    fields[name] = {value: content.replace(/\r\n$/, ""), filename, size: Buffer.byteLength(content, "latin1")};
  }
  return fields;
}

function mockApi(req, res, body) {
  const p = req.url.split("?")[0];
  if (req.method === "GET" && p === "/api/moi") {
    const cookie = String(req.headers.cookie || "").match(/(?:^|;\s*)pf_s=([^;]+)/)?.[1];
    const email = cookie ? sessions.get(cookie) : null;
    const compte = email ? comptes.get(email) : null;
    return compte ? sendJSON(res, 200, { prenom: compte.prenom, email }) : sendJSON(res, 401, { ok: false, erreur: "Connexion requise." });
  }
  const sessionCookie = String(req.headers.cookie || "").match(/(?:^|;\s*)pf_s=([^;]+)/)?.[1];
  const sessionEmail = sessionCookie ? sessions.get(sessionCookie) : null;
  if (req.method === "GET" && p === "/api/annonces") {
    return sessionEmail ? sendJSON(res, 200, mockListings) : sendJSON(res, 401, { ok: false, erreur: "Connexion requise." });
  }
  if (req.method === "GET" && p === "/api/recherches") {
    return sessionEmail ? sendJSON(res, 200, recherches.get(sessionEmail) || []) : sendJSON(res, 401, { ok: false, erreur: "Connexion requise." });
  }
  if (req.method === "GET" && p === "/api/profil") {
    return sessionEmail ? sendJSON(res, 200, profils.get(sessionEmail) || {prenom: comptes.get(sessionEmail)?.prenom || ""}) : sendJSON(res, 401, {ok: false, erreur: "Connexion requise."});
  }
  if (req.method === "GET" && p === "/api/dossier") {
    return sessionEmail ? sendJSON(res, 200, documents.get(sessionEmail) || []) : sendJSON(res, 401, {ok: false, erreur: "Connexion requise."});
  }
  if (!sessionEmail && (p === "/api/profil" || p === "/api/dossier" || p.startsWith("/api/dossier/") || p === "/api/mot-de-passe")) return sendJSON(res, 401, {ok: false, erreur: "Connexion requise."});
  if (req.method === "PUT" && p === "/api/profil") {
    let d; try { d = JSON.parse(body.toString("utf8") || "{}"); } catch { return sendJSON(res, 400, {ok: false}); }
    const profile = {prenom: String(d.prenom || comptes.get(sessionEmail)?.prenom || "").slice(0, 40), tel: String(d.tel || "").slice(0, 30), ville: String(d.ville || "").slice(0, 80), situation: String(d.situation || "").slice(0, 80), revenus: String(d.revenus || "").slice(0, 80)};
    profils.set(sessionEmail, profile); if (comptes.has(sessionEmail)) comptes.get(sessionEmail).prenom = profile.prenom;
    return sendJSON(res, 200, profile);
  }
  if (req.method === "POST" && p === "/api/mot-de-passe") {
    let d; try { d = JSON.parse(body.toString("utf8") || "{}"); } catch { return sendJSON(res, 400, {ok: false}); }
    const c = comptes.get(sessionEmail), next = String(d.nouveau_mdp || "");
    if (!c || !crypto.timingSafeEqual(c.mdp, hash(String(d.current_mdp || ""), c.sel))) return sendJSON(res, 401, {ok: false, erreur: "Ton mot de passe actuel est incorrect."});
    if (next.length < 8 || next.length > 128) return sendJSON(res, 400, {ok: false, erreur: "Ton mot de passe doit faire au moins 8 caractères."});
    c.sel = crypto.randomBytes(16); c.mdp = hash(next, c.sel); for (const [token, email] of sessions) if (email === sessionEmail) sessions.delete(token);
    return sendJSON(res, 200, {ok: true}, "pf_s=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax");
  }
  if (req.method === "POST" && p === "/api/dossier/pieces") {
    const fields = multipartFields(req, body), file = fields.file || {}, name = String(fields.nom?.value || "").trim(), type = String(fields.type?.value || "");
    if (name.length < 3 || !type || !file.filename) return sendJSON(res, 400, {ok: false, detail: "Nomme la pièce, choisis son type et joins un fichier."});
    const ext = path.extname(file.filename).slice(1).toLowerCase(); if (!["pdf", "jpg", "jpeg", "png", "heic"].includes(ext)) return sendJSON(res, 415, {ok: false, detail: "Format accepté : PDF, JPG, PNG ou HEIC."});
    const doc = {id: `doc-${crypto.randomBytes(12).toString("hex")}`, nom: name.slice(0, 80), type: type.slice(0, 80), filename: file.filename.slice(0, 180), size_bytes: file.size, status: "received"};
    documents.set(sessionEmail, [doc, ...(documents.get(sessionEmail) || [])]); return sendJSON(res, 201, doc);
  }
  const deletion = p.match(/^\/api\/dossier\/pieces\/([^/]+)$/);
  if (req.method === "DELETE" && deletion) {
    const current = documents.get(sessionEmail) || [], next = current.filter(d => d.id !== decodeURIComponent(deletion[1]));
    if (next.length === current.length) return sendJSON(res, 404, {ok: false}); documents.set(sessionEmail, next); return sendJSON(res, 200, {ok: true});
  }
  let d = {};
  try { d = JSON.parse(body.toString("utf8") || "{}"); } catch { return sendJSON(res, 400, { ok: false }); }
  if (req.method !== "POST") return sendJSON(res, 405, { ok: false });
  if (p === "/api/inscription") {
    const email = String(d.email || "").trim().toLowerCase();
    if (!EMAIL.test(email)) return sendJSON(res, 400, { ok: false });
    liste.add(email); return sendJSON(res, 200, { ok: true });
  }
  if (p === "/api/recherches") {
    if (!sessionEmail) return sendJSON(res, 401, { ok: false, erreur: "Connexion requise." });
    if (typeof d.texte !== "string" || d.texte.trim().length < 6) return sendJSON(res, 400, { ok: false, erreur: "Décris un peu ta recherche." });
    const profile = {id: `profile-${crypto.randomBytes(5).toString("hex")}`, candidate_id: sessionEmail, cities: Array.isArray(d.cities) ? d.cities : [], max_budget_eur: d.max_budget_eur ?? null, housing_type: d.housing_type || "any", move_in: d.move_in || null, status: "draft"};
    recherches.set(sessionEmail, [...(recherches.get(sessionEmail) || []), profile]);
    return sendJSON(res, 201, profile);
  }
  if (p !== "/api/compte") return sendJSON(res, 404, { ok: false });
  const action = d.action;
  if (action === "deconnexion") {
    const cookie = String(req.headers.cookie || "").match(/(?:^|;\s*)pf_s=([^;]+)/)?.[1];
    if (cookie) sessions.delete(cookie);
    return sendJSON(res, 200, { ok: true }, "pf_s=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax");
  }
  if (d.site) return sendJSON(res, 400, { ok: false, erreur: "Inscription refusée." });
  const email = String(d.email || "").trim().toLowerCase(), mdp = String(d.mdp || "");
  if (!EMAIL.test(email)) return sendJSON(res, 400, { ok: false, erreur: "Cette adresse e-mail ne semble pas complète." });
  let prenom;
  if (action === "creer") {
    prenom = String(d.prenom || "").trim().slice(0, 40);
    if (mdp.length < 8 || mdp.length > 128) return sendJSON(res, 400, { ok: false, erreur: "Ton mot de passe doit faire au moins 8 caractères." });
    if (!prenom) return sendJSON(res, 400, { ok: false, erreur: "Dis-nous ton prénom." });
    if (comptes.has(email)) return sendJSON(res, 409, { ok: false, erreur: "Un compte existe déjà avec cet e-mail. Connecte-toi." });
    const sel = crypto.randomBytes(16);
    comptes.set(email, { prenom, sel, mdp: hash(mdp, sel) });
  } else if (action === "connexion") {
    const c = comptes.get(email);
    if (!c || mdp.length > 128 || !crypto.timingSafeEqual(c.mdp, hash(mdp, c.sel)))
      return sendJSON(res, 401, { ok: false, erreur: "E-mail ou mot de passe incorrect." });
    prenom = c.prenom;
  } else return sendJSON(res, 400, { ok: false });
  const jeton = crypto.randomBytes(24).toString("base64url");
  sessions.set(jeton, email);
  sendJSON(res, 200, { ok: true, prenom, email }, `pf_s=${jeton}; Path=/; Max-Age=2592000; HttpOnly; SameSite=Lax`);
}

function proxyApi(req, res, body) {
  const u = new URL(req.url, API_TARGET);
  const r = http.request(u, { method: req.method, headers: { ...req.headers, host: u.host, "x-forwarded-proto": "http" } }, up => {
    res.writeHead(up.statusCode || 502, up.headers); up.pipe(res);
  });
  r.on("error", () => sendJSON(res, 502, { ok: false, erreur: "Le backend ne répond pas (" + API_TARGET + ")." }));
  r.end(body);
}

// ---------- Fichiers statiques ----------
function serveStatic(req, res) {
  let rel;
  try { rel = decodeURIComponent(req.url.split("?")[0]); } catch { res.writeHead(400); return res.end(); }
  if (rel.endsWith("/")) rel += "index.html";
  const file = path.normalize(path.join(ROOT, rel));
  const first = path.relative(ROOT, file).split(path.sep)[0];
  if (!file.startsWith(ROOT + path.sep) || PRIVATE.has(first) || path.basename(file).startsWith(".")) { res.writeHead(404); return res.end("Introuvable"); }
  fs.stat(file, (err, st) => {
    if (err || !st.isFile()) { res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" }); return res.end("Introuvable"); }
    const type = TYPES[path.extname(file).toLowerCase()] || "application/octet-stream";
    const range = req.headers.range && /^bytes=(\d*)-(\d*)$/.exec(req.headers.range);
    if (range) {
      let a = range[1] === "" ? st.size - Number(range[2]) : Number(range[1]);
      let b = range[1] !== "" && range[2] !== "" ? Number(range[2]) : st.size - 1;
      a = Math.max(0, a); b = Math.min(b, st.size - 1);
      if (a > b) { res.writeHead(416, { "Content-Range": `bytes */${st.size}` }); return res.end(); }
      res.writeHead(206, { "Content-Type": type, "Accept-Ranges": "bytes", "Content-Range": `bytes ${a}-${b}/${st.size}`, "Content-Length": b - a + 1 });
      return req.method === "HEAD" ? res.end() : fs.createReadStream(file, { start: a, end: b }).pipe(res);
    }
    res.writeHead(200, { "Content-Type": type, "Accept-Ranges": "bytes", "Content-Length": st.size, "Cache-Control": "no-cache" });
    req.method === "HEAD" ? res.end() : fs.createReadStream(file).pipe(res);
  });
}

http.createServer((req, res) => {
  if (req.url.startsWith("/api/")) {
    const chunks = []; let n = 0;
    req.on("data", c => { n += c.length; if (n > 65536) req.destroy(); else chunks.push(c); });
    req.on("end", () => {
      const body = Buffer.concat(chunks);
      API_MODE === "proxy" ? proxyApi(req, res, body) : mockApi(req, res, body);
    });
    return;
  }
  serveStatic(req, res);
}).listen(PORT, HOST, () => {
  console.log(`Piaule Fiction : http://${HOST}:${PORT}/  (API ${API_MODE === "proxy" ? "relayée vers " + API_TARGET : "simulée en mémoire"})`);
});
