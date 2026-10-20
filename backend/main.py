"""Piaule Fiction owner workspace API.

The current production-shaped slice preserves account/session primitives and
synthetic source contracts while the domain moves to owner workspaces,
properties, applications, agent actions and approvals. The API is the source
of truth; the browser may keep a display cache but never defines ownership.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .listing_pipeline import SELOGER_SOURCE, demo_listings


PRODUCT = "piaule-fiction"
SESSION_COOKIE = "pf_s"
SESSION_DAYS = 30
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")

STATE_DIRECTORY = Path(os.getenv("PIAULE_STATE_DIRECTORY", ".local-state"))
DATABASE_PATH = Path(
    os.getenv("PIAULE_DATABASE_PATH", str(STATE_DIRECTORY / "piaule-fiction.sqlite3"))
)
UPLOAD_DIRECTORY = Path(os.getenv("PIAULE_UPLOAD_DIRECTORY", str(STATE_DIRECTORY / "uploads")))
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
ALLOWED_DOCUMENT_TYPES = {
    "pdf": {"application/pdf"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "png": {"image/png"},
    "heic": {"image/heic", "image/heif"},
}


app = FastAPI(
    title="Piaule Fiction API",
    version="0.2.0",
    description="Owner workspace API with server-side sessions and normalized source contracts.",
)


class AccountRequest(BaseModel):
    action: Literal["creer", "connexion", "deconnexion"]
    prenom: str = ""
    email: str = ""
    mdp: str = ""
    site: str = ""  # Honeypot field kept for the frontend contract.


class Candidate(BaseModel):
    prenom: str
    email: str
    workspace_id: str


class Workspace(BaseModel):
    id: str
    name: str
    owner_email: str
    role: Literal["owner"] = "owner"
    created_at: str


class WorkspaceUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class WorkspaceMember(BaseModel):
    email: str
    prenom: str
    role: Literal["owner"] = "owner"
    joined_at: str


class PasswordChangeRequest(BaseModel):
    current_mdp: str = Field(min_length=1, max_length=128)
    nouveau_mdp: str = Field(min_length=8, max_length=128)


class CandidateProfile(BaseModel):
    prenom: str = ""
    tel: str = ""
    ville: str = ""
    situation: str = ""
    revenus: str = ""


class DocumentRecord(BaseModel):
    id: str
    nom: str
    type: str
    filename: str
    size_bytes: int
    status: Literal["received", "checking", "ready"] = "received"


class SearchProfileCreate(BaseModel):
    candidate_id: str | None = Field(default=None, min_length=1)
    cities: list[str] = Field(default_factory=list)
    max_budget_eur: int | None = Field(default=None, ge=0)
    housing_type: Literal["studio", "apartment", "room", "shared", "any"] = "any"
    move_in: date | None = None


class SearchProfile(SearchProfileCreate):
    id: str
    status: Literal["draft", "active"] = "draft"


class SearchRequest(BaseModel):
    texte: str = Field(min_length=6, max_length=1000)
    cities: list[str] = Field(default_factory=list)
    max_budget_eur: int | None = Field(default=None, ge=0)
    housing_type: Literal["studio", "apartment", "room", "shared", "any"] = "any"
    move_in: date | None = None


class Listing(BaseModel):
    id: str
    title: str
    city: str
    monthly_rent_eur: int
    source: str
    risk_level: Literal["unknown", "low", "medium", "high"] = "unknown"
    property_type: str = "unknown"
    surface_m2: float | None = None
    rooms: int | None = None
    url: str = ""
    fetched_at: str = ""


class ListingSource(BaseModel):
    id: str
    status: Literal["demo", "planned", "disabled"]
    capabilities: list[str]


class ListingSyncResult(BaseModel):
    source: str
    received: int
    inserted: int
    updated: int
    duplicates: int


class Application(BaseModel):
    id: str
    candidate_id: str
    listing_id: str
    status: Literal["draft", "ready", "submitted", "reply", "visit"] = "draft"
    human_approval_required: bool = True


profiles: dict[str, SearchProfile] = {}
applications: dict[str, Application] = {}


def _clean_text(value: str, maximum: int) -> str:
    """Remove control characters and spreadsheet formula prefixes from text."""

    cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", str(value or "")).strip()
    return cleaned[:maximum].lstrip("=+-@\t")


def _normalise_email(value: str) -> str:
    return _clean_text(value, 254).lower()


def _password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)


def _ensure_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS candidates (
                email TEXT PRIMARY KEY,
                prenom TEXT NOT NULL,
                salt BLOB NOT NULL,
                password_hash BLOB NOT NULL,
                workspace_id TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                owner_email TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS workspace_members (
                workspace_id TEXT NOT NULL,
                email TEXT NOT NULL,
                role TEXT NOT NULL,
                joined_at TEXT NOT NULL,
                PRIMARY KEY (workspace_id, email),
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(email) REFERENCES candidates(email) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS workspace_members_email_idx ON workspace_members(email);
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                expires_at REAL NOT NULL,
                FOREIGN KEY(email) REFERENCES candidates(email) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions(expires_at);
            CREATE TABLE IF NOT EXISTS search_profiles (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                texte TEXT NOT NULL,
                cities_json TEXT NOT NULL,
                max_budget_eur INTEGER,
                housing_type TEXT NOT NULL,
                move_in TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(email) REFERENCES candidates(email) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS search_profiles_email_idx ON search_profiles(email);
            CREATE TABLE IF NOT EXISTS candidate_profiles (
                email TEXT PRIMARY KEY,
                prenom TEXT NOT NULL,
                tel TEXT NOT NULL DEFAULT '',
                ville TEXT NOT NULL DEFAULT '',
                situation TEXT NOT NULL DEFAULT '',
                revenus TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                FOREIGN KEY(email) REFERENCES candidates(email) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                nom TEXT NOT NULL,
                document_type TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                content_type TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(email) REFERENCES candidates(email) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS documents_email_idx ON documents(email);
            CREATE TABLE IF NOT EXISTS listings (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                source_listing_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                city TEXT NOT NULL,
                monthly_rent_eur INTEGER NOT NULL,
                property_type TEXT NOT NULL,
                surface_m2 REAL,
                rooms INTEGER,
                url TEXT NOT NULL DEFAULT '',
                risk_level TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS listings_city_idx ON listings(city);
            CREATE INDEX IF NOT EXISTS listings_source_idx ON listings(source);
            """
        )
        candidate_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(candidates)").fetchall()
        }
        if "workspace_id" not in candidate_columns:
            connection.execute("ALTER TABLE candidates ADD COLUMN workspace_id TEXT")

        # Give legacy accounts a workspace before any workspace-scoped route is used.
        legacy_accounts = connection.execute(
            "SELECT email, prenom FROM candidates WHERE workspace_id IS NULL OR workspace_id = ''"
        ).fetchall()
        for account in legacy_accounts:
            workspace_id = f"ws-{uuid4().hex[:16]}"
            connection.execute(
                "INSERT INTO workspaces(id, name, owner_email, created_at) VALUES (?, ?, ?, datetime('now'))",
                (workspace_id, f"Espace de {account['prenom']}", account["email"]),
            )
            connection.execute(
                "UPDATE candidates SET workspace_id = ? WHERE email = ?",
                (workspace_id, account["email"]),
            )
            connection.execute(
                "INSERT OR IGNORE INTO workspace_members(workspace_id, email, role, joined_at) VALUES (?, ?, 'owner', datetime('now'))",
                (workspace_id, account["email"]),
            )
        for listing in demo_listings():
            connection.execute(
                """
                INSERT OR IGNORE INTO listings(
                    id, source, source_listing_id, fingerprint, title, city,
                    monthly_rent_eur, property_type, surface_m2, rooms, url,
                    risk_level, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuple(listing[field] for field in (
                    "id", "source", "source_listing_id", "fingerprint", "title", "city",
                    "monthly_rent_eur", "property_type", "surface_m2", "rooms", "url",
                    "risk_level", "fetched_at"
                )),
            )
        connection.commit()


def _connect() -> sqlite3.Connection:
    _ensure_database()
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _secure_cookie(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    return request.url.scheme == "https" or forwarded_proto == "https"


def _set_session(response: Response, request: Request, email: str) -> None:
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + SESSION_DAYS * 86400
    with closing(_connect()) as connection:
        connection.execute("DELETE FROM sessions WHERE expires_at < ?", (time.time(),))
        connection.execute(
            "INSERT INTO sessions(token, email, expires_at) VALUES (?, ?, ?)",
            (token, email, expires_at),
        )
        connection.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=_secure_cookie(request),
        path="/",
    )


def _clear_session(response: Response, request: Request, token: str | None) -> None:
    if token:
        with closing(_connect()) as connection:
            connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
            connection.commit()
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=_secure_cookie(request),
        httponly=True,
        samesite="lax",
    )


def _candidate_from_token(token: str | None) -> Candidate:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Connexion requise.")
    with closing(_connect()) as connection:
        row = connection.execute(
            """
            SELECT c.prenom, c.email, c.workspace_id
            FROM sessions s
            JOIN candidates c ON c.email = s.email
            WHERE s.token = ? AND s.expires_at > ?
            """,
            (token, time.time()),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Connexion requise.")
    return Candidate(prenom=row["prenom"], email=row["email"], workspace_id=row["workspace_id"])


def _workspace_for_owner(owner: Candidate) -> Workspace:
    with closing(_connect()) as connection:
        row = connection.execute(
            """
            SELECT w.id, w.name, w.owner_email, w.created_at
            FROM workspaces w
            JOIN workspace_members m ON m.workspace_id = w.id
            WHERE w.id = ? AND m.email = ? AND m.role = 'owner'
            """,
            (owner.workspace_id, owner.email),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace inaccessible.")
    return Workspace(
        id=row["id"],
        name=row["name"],
        owner_email=row["owner_email"],
        created_at=row["created_at"],
    )


def _document_extension(filename: str, content_type: str) -> str | None:
    extension = Path(filename or "").suffix.lower().lstrip(".")
    if extension not in ALLOWED_DOCUMENT_TYPES:
        return None
    if content_type and content_type not in ALLOWED_DOCUMENT_TYPES[extension]:
        return None
    return extension


def _profile_from_row(row: sqlite3.Row | None, candidate: Candidate) -> CandidateProfile:
    if row is None:
        return CandidateProfile(prenom=candidate.prenom)
    return CandidateProfile(
        prenom=row["prenom"],
        tel=row["tel"],
        ville=row["ville"],
        situation=row["situation"],
        revenus=row["revenus"],
    )


def _listing_from_row(row: sqlite3.Row) -> Listing:
    return Listing(
        id=row["id"],
        title=row["title"],
        city=row["city"],
        monthly_rent_eur=row["monthly_rent_eur"],
        source=row["source"],
        risk_level=row["risk_level"] if row["risk_level"] in {"unknown", "low", "medium", "high"} else "unknown",
        property_type=row["property_type"],
        surface_m2=row["surface_m2"],
        rooms=row["rooms"],
        url=row["url"],
        fetched_at=row["fetched_at"],
    )


def _sync_demo_source() -> ListingSyncResult:
    incoming = demo_listings()
    inserted = updated = duplicates = 0
    with closing(_connect()) as connection:
        for listing in incoming:
            existing = connection.execute(
                "SELECT id FROM listings WHERE fingerprint = ?", (listing["fingerprint"],)
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO listings(
                        id, source, source_listing_id, fingerprint, title, city,
                        monthly_rent_eur, property_type, surface_m2, rooms, url,
                        risk_level, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    tuple(listing[field] for field in (
                        "id", "source", "source_listing_id", "fingerprint", "title", "city",
                        "monthly_rent_eur", "property_type", "surface_m2", "rooms", "url",
                        "risk_level", "fetched_at"
                    )),
                )
                inserted += 1
            else:
                connection.execute(
                    """
                    UPDATE listings SET title = ?, city = ?, monthly_rent_eur = ?,
                        property_type = ?, surface_m2 = ?, rooms = ?, url = ?,
                        risk_level = ?, fetched_at = ? WHERE fingerprint = ?
                    """,
                    (
                        listing["title"], listing["city"], listing["monthly_rent_eur"],
                        listing["property_type"], listing["surface_m2"], listing["rooms"],
                        listing["url"], listing["risk_level"], listing["fetched_at"], listing["fingerprint"],
                    ),
                )
                updated += 1
            duplicates += sum(1 for other in incoming if other["fingerprint"] == listing["fingerprint"]) - 1
        connection.commit()
    return ListingSyncResult(
        source="piaule-demo", received=len(incoming), inserted=inserted,
        updated=updated, duplicates=max(0, duplicates),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "product": PRODUCT, "mode": "synthetic"}


@app.post("/api/compte")
def account(payload: AccountRequest, request: Request, response: Response) -> dict[str, object]:
    """Create, authenticate or close a property-owner account."""

    if payload.action == "deconnexion":
        _clear_session(response, request, request.cookies.get(SESSION_COOKIE))
        return {"ok": True}

    if payload.site:
        return JSONResponse(status_code=400, content={"ok": False, "erreur": "Inscription refusée."})

    email = _normalise_email(payload.email)
    password = payload.mdp
    if not EMAIL_RE.fullmatch(email):
        return JSONResponse(
            status_code=400,
            content={"ok": False, "erreur": "Cette adresse e-mail ne semble pas complète."},
        )
    if len(password) > 128 or (payload.action == "creer" and len(password) < 8):
        return JSONResponse(
            status_code=400,
            content={"ok": False, "erreur": "Ton mot de passe doit faire au moins 8 caractères."},
        )

    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT prenom, salt, password_hash FROM candidates WHERE email = ?", (email,)
        ).fetchone()

        if payload.action == "creer":
            prenom = _clean_text(payload.prenom, 40)
            if not prenom:
                return JSONResponse(status_code=400, content={"ok": False, "erreur": "Dis-nous ton prénom."})
            if row is not None:
                return JSONResponse(
                    status_code=409,
                    content={
                        "ok": False,
                        "erreur": "Un compte existe déjà avec cet e-mail. Connecte-toi.",
                    },
                )
            salt = secrets.token_bytes(16)
            workspace_id = f"ws-{uuid4().hex[:16]}"
            connection.execute(
                """
                INSERT INTO candidates(email, prenom, salt, password_hash, workspace_id, created_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                """,
                (email, prenom, salt, _password_hash(password, salt), workspace_id),
            )
            connection.execute(
                "INSERT INTO workspaces(id, name, owner_email, created_at) VALUES (?, ?, ?, datetime('now'))",
                (workspace_id, f"Espace de {prenom}", email),
            )
            connection.execute(
                "INSERT INTO workspace_members(workspace_id, email, role, joined_at) VALUES (?, ?, 'owner', datetime('now'))",
                (workspace_id, email),
            )
        else:
            if row is None:
                return JSONResponse(
                    status_code=401,
                    content={"ok": False, "erreur": "E-mail ou mot de passe incorrect."},
                )
            stored_hash = _password_hash(password, row["salt"])
            if not hmac.compare_digest(stored_hash, row["password_hash"]):
                return JSONResponse(
                    status_code=401,
                    content={"ok": False, "erreur": "E-mail ou mot de passe incorrect."},
                )
            prenom = row["prenom"]
            workspace_id = connection.execute(
                "SELECT workspace_id FROM candidates WHERE email = ?", (email,)
            ).fetchone()["workspace_id"]

        connection.commit()

    _set_session(response, request, email)
    return {"ok": True, "prenom": prenom, "email": email, "workspace_id": workspace_id}


@app.get("/api/moi", response_model=Candidate)
def current_candidate(pf_s: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> Candidate:
    """Return the authenticated owner account or fail with 401."""

    return _candidate_from_token(pf_s)


@app.get("/api/workspace", response_model=Workspace)
def get_workspace(owner: Candidate = Depends(current_candidate)) -> Workspace:
    """Return the isolated workspace belonging to the authenticated owner."""

    return _workspace_for_owner(owner)


@app.put("/api/workspace", response_model=Workspace)
def update_workspace(
    payload: WorkspaceUpdate, owner: Candidate = Depends(current_candidate)
) -> Workspace:
    """Update only the current owner's workspace metadata."""

    workspace = _workspace_for_owner(owner)
    name = _clean_text(payload.name, 80)
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Le nom du workspace est trop court.")
    with closing(_connect()) as connection:
        connection.execute(
            "UPDATE workspaces SET name = ? WHERE id = ? AND owner_email = ?",
            (name, workspace.id, owner.email),
        )
        connection.commit()
    return Workspace(
        id=workspace.id,
        name=name,
        owner_email=workspace.owner_email,
        created_at=workspace.created_at,
    )


@app.get("/api/workspace/membres", response_model=list[WorkspaceMember])
def list_workspace_members(owner: Candidate = Depends(current_candidate)) -> list[WorkspaceMember]:
    """List members of the current workspace without exposing other workspaces."""

    workspace = _workspace_for_owner(owner)
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT c.email, c.prenom, m.role, m.joined_at
            FROM workspace_members m
            JOIN candidates c ON c.email = m.email
            WHERE m.workspace_id = ?
            ORDER BY m.joined_at
            """,
            (workspace.id,),
        ).fetchall()
    return [
        WorkspaceMember(
            email=row["email"],
            prenom=row["prenom"],
            role=row["role"] if row["role"] == "owner" else "owner",
            joined_at=row["joined_at"],
        )
        for row in rows
    ]


@app.post("/api/mot-de-passe")
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    candidate: Candidate = Depends(current_candidate),
) -> JSONResponse:
    """Change the password and revoke every existing session for this account."""

    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT salt, password_hash FROM candidates WHERE email = ?",
            (candidate.email,),
        ).fetchone()
        if row is None or not hmac.compare_digest(
            _password_hash(payload.current_mdp, row["salt"]), row["password_hash"]
        ):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"ok": False, "erreur": "Ton mot de passe actuel est incorrect."},
            )
        salt = secrets.token_bytes(16)
        connection.execute(
            "UPDATE candidates SET salt = ?, password_hash = ? WHERE email = ?",
            (salt, _password_hash(payload.nouveau_mdp, salt), candidate.email),
        )
        connection.execute("DELETE FROM sessions WHERE email = ?", (candidate.email,))
        connection.commit()

    response = JSONResponse(status_code=200, content={"ok": True})
    _clear_session(response, request, request.cookies.get(SESSION_COOKIE))
    return response


@app.get("/api/profil", response_model=CandidateProfile)
def get_profile(candidate: Candidate = Depends(current_candidate)) -> CandidateProfile:
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT prenom, tel, ville, situation, revenus FROM candidate_profiles WHERE email = ?",
            (candidate.email,),
        ).fetchone()
    return _profile_from_row(row, candidate)


@app.put("/api/profil", response_model=CandidateProfile)
def update_profile(
    payload: CandidateProfile, candidate: Candidate = Depends(current_candidate)
) -> CandidateProfile:
    profile = CandidateProfile(
        prenom=_clean_text(payload.prenom, 40) or candidate.prenom,
        tel=_clean_text(payload.tel, 30),
        ville=_clean_text(payload.ville, 80),
        situation=_clean_text(payload.situation, 80),
        revenus=_clean_text(payload.revenus, 80),
    )
    with closing(_connect()) as connection:
        connection.execute(
            """
            INSERT INTO candidate_profiles(email, prenom, tel, ville, situation, revenus, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(email) DO UPDATE SET
                prenom = excluded.prenom,
                tel = excluded.tel,
                ville = excluded.ville,
                situation = excluded.situation,
                revenus = excluded.revenus,
                updated_at = excluded.updated_at
            """,
            (candidate.email, profile.prenom, profile.tel, profile.ville, profile.situation, profile.revenus),
        )
        connection.execute("UPDATE candidates SET prenom = ? WHERE email = ?", (profile.prenom, candidate.email))
        connection.commit()
    return profile


@app.get("/api/dossier", response_model=list[DocumentRecord])
def list_documents(candidate: Candidate = Depends(current_candidate)) -> list[DocumentRecord]:
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT id, nom, document_type, original_filename, size_bytes, status
            FROM documents WHERE email = ? ORDER BY created_at DESC
            """,
            (candidate.email,),
        ).fetchall()
    return [
        DocumentRecord(
            id=row["id"],
            nom=row["nom"],
            type=row["document_type"],
            filename=row["original_filename"],
            size_bytes=row["size_bytes"],
            status=row["status"],
        )
        for row in rows
    ]


@app.post("/api/dossier/pieces", response_model=DocumentRecord, status_code=201)
async def upload_document(
    nom: str = Form(...),
    type: str = Form(...),
    file: UploadFile = File(...),
    candidate: Candidate = Depends(current_candidate),
) -> DocumentRecord:
    document_name = _clean_text(nom, 80)
    document_type = _clean_text(type, 80)
    extension = _document_extension(file.filename or "", file.content_type or "")
    if len(document_name) < 3 or not document_type:
        raise HTTPException(status_code=400, detail="Nomme la pièce et indique son type.")
    if extension is None:
        raise HTTPException(status_code=415, detail="Format accepté : PDF, JPG, PNG ou HEIC.")

    content = await file.read(MAX_DOCUMENT_BYTES + 1)
    if len(content) > MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=413, detail="La pièce ne doit pas dépasser 10 Mo.")

    document_id = f"doc-{uuid4().hex}"
    stored_filename = f"{document_id}.{extension}"
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIRECTORY / stored_filename).write_bytes(content)
    try:
        with closing(_connect()) as connection:
            connection.execute(
                """
                INSERT INTO documents(
                    id, email, nom, document_type, original_filename, stored_filename,
                    size_bytes, content_type, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'received', datetime('now'))
                """,
                (
                    document_id,
                    candidate.email,
                    document_name,
                    document_type,
                    _clean_text(file.filename or f"piece.{extension}", 180),
                    stored_filename,
                    len(content),
                    file.content_type or "application/octet-stream",
                ),
            )
            connection.commit()
    except Exception:
        (UPLOAD_DIRECTORY / stored_filename).unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return DocumentRecord(
        id=document_id,
        nom=document_name,
        type=document_type,
        filename=_clean_text(file.filename or f"piece.{extension}", 180),
        size_bytes=len(content),
        status="received",
    )


@app.delete("/api/dossier/pieces/{document_id}")
def delete_document(document_id: str, candidate: Candidate = Depends(current_candidate)) -> dict[str, bool]:
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT stored_filename FROM documents WHERE id = ? AND email = ?",
            (document_id, candidate.email),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Pièce introuvable.")
        connection.execute("DELETE FROM documents WHERE id = ? AND email = ?", (document_id, candidate.email))
        connection.commit()
    (UPLOAD_DIRECTORY / row["stored_filename"]).unlink(missing_ok=True)
    return {"ok": True}


@app.get("/api/v1/listings", response_model=list[Listing])
def get_listings() -> list[Listing]:
    with closing(_connect()) as connection:
        rows = connection.execute("SELECT * FROM listings ORDER BY fetched_at DESC, id").fetchall()
    return [_listing_from_row(row) for row in rows]


@app.get("/api/v1/sources", response_model=list[ListingSource])
def get_listing_sources() -> list[ListingSource]:
    return [
        ListingSource(id="piaule-demo", status="demo", capabilities=["READ_LISTINGS", "PROVENANCE"]),
        ListingSource(id=SELOGER_SOURCE, status="planned", capabilities=["OFFICIAL_ACCESS_REQUIRED"]),
    ]


@app.post("/api/v1/listings/sync", response_model=ListingSyncResult)
def sync_listings(_: Candidate = Depends(current_candidate)) -> ListingSyncResult:
    """Run the controlled demo adapter; live connectors will use this same boundary."""

    return _sync_demo_source()


def _candidate_listing_feed(candidate: Candidate) -> list[Listing]:
    with closing(_connect()) as connection:
        search = connection.execute(
            """
            SELECT cities_json, max_budget_eur, housing_type
            FROM search_profiles WHERE email = ? ORDER BY created_at DESC LIMIT 1
            """,
            (candidate.email,),
        ).fetchone()
        rows = connection.execute("SELECT * FROM listings ORDER BY fetched_at DESC, id").fetchall()
    if search is None:
        return [_listing_from_row(row) for row in rows]
    cities = {str(city).strip().casefold() for city in json.loads(search["cities_json"])}
    housing_type = search["housing_type"]
    output = []
    for row in rows:
        if cities and row["city"].casefold() not in cities:
            continue
        if search["max_budget_eur"] is not None and row["monthly_rent_eur"] > search["max_budget_eur"]:
            continue
        if housing_type not in {"any", "apartment"} and row["property_type"] != housing_type:
            continue
        output.append(_listing_from_row(row))
    return output


@app.get("/api/annonces", response_model=list[Listing])
def get_candidate_listings(candidate: Candidate = Depends(current_candidate)) -> list[Listing]:
    """Return normalized listings filtered by the candidate's latest search."""

    return _candidate_listing_feed(candidate)


@app.post("/api/v1/search-profiles", response_model=SearchProfile, status_code=201)
def create_search_profile(
    payload: SearchProfileCreate, candidate: Candidate = Depends(current_candidate)
) -> SearchProfile:
    profile = SearchProfile(
        id=f"profile-{uuid4().hex[:10]}",
        candidate_id=candidate.email,
        cities=payload.cities,
        max_budget_eur=payload.max_budget_eur,
        housing_type=payload.housing_type,
        move_in=payload.move_in,
    )
    profiles[profile.id] = profile
    return profile


@app.get("/api/v1/search-profiles/{profile_id}", response_model=SearchProfile)
def get_search_profile(
    profile_id: str, candidate: Candidate = Depends(current_candidate)
) -> SearchProfile:
    profile = profiles.get(profile_id)
    if profile is None or profile.candidate_id != candidate.email:
        raise HTTPException(status_code=404, detail="Profil introuvable.")
    return profile


@app.post("/api/recherches", response_model=SearchProfile, status_code=201)
def create_recherche(
    payload: SearchRequest, candidate: Candidate = Depends(current_candidate)
) -> SearchProfile:
    """Persist one candidate's natural-language search and structured criteria."""

    profile = SearchProfile(
        id=f"profile-{uuid4().hex[:10]}",
        candidate_id=candidate.email,
        cities=payload.cities,
        max_budget_eur=payload.max_budget_eur,
        housing_type=payload.housing_type,
        move_in=payload.move_in,
    )
    with closing(_connect()) as connection:
        connection.execute(
            """
            INSERT INTO search_profiles(
                id, email, texte, cities_json, max_budget_eur,
                housing_type, move_in, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                profile.id,
                candidate.email,
                _clean_text(payload.texte, 1000),
                json.dumps(payload.cities, ensure_ascii=False),
                payload.max_budget_eur,
                payload.housing_type,
                payload.move_in.isoformat() if payload.move_in else None,
                profile.status,
            ),
        )
        connection.commit()
    profiles[profile.id] = profile
    return profile


@app.get("/api/recherches", response_model=list[SearchProfile])
def get_recherches(candidate: Candidate = Depends(current_candidate)) -> list[SearchProfile]:
    """List only the authenticated candidate's structured searches."""

    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT id, cities_json, max_budget_eur, housing_type, move_in, status
            FROM search_profiles
            WHERE email = ?
            ORDER BY created_at DESC
            """,
            (candidate.email,),
        ).fetchall()
    return [
        SearchProfile(
            id=row["id"],
            candidate_id=candidate.email,
            cities=json.loads(row["cities_json"]),
            max_budget_eur=row["max_budget_eur"],
            housing_type=row["housing_type"],
            move_in=date.fromisoformat(row["move_in"]) if row["move_in"] else None,
            status=row["status"],
        )
        for row in rows
    ]


@app.get("/api/v1/applications", response_model=list[Application])
def get_applications(candidate: Candidate = Depends(current_candidate)) -> list[Application]:
    values = list(applications.values())
    return [item for item in values if item.candidate_id == candidate.email]
