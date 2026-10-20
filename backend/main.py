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
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as URLRequest, urlopen
from uuid import uuid4

from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from .listing_pipeline import SELOGER_SOURCE, demo_listings


PRODUCT = "piaule-fiction"
SESSION_COOKIE = "pf_s"
GOOGLE_STATE_COOKIE = "pf_google_state"
SESSION_DAYS = 30
GOOGLE_STATE_SECONDS = 600
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")
GOOGLE_CLIENT_ID = os.getenv("PIAULE_GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("PIAULE_GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_REDIRECT_URI = os.getenv(
    "PIAULE_GOOGLE_REDIRECT_URI",
    "http://127.0.0.1:8000/api/auth/google/callback",
).strip()
FRONTEND_REDIRECT_URI = os.getenv(
    "PIAULE_FRONTEND_REDIRECT_URI",
    "http://127.0.0.1:5173/espace.html",
).strip()

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


class PropertyCreate(BaseModel):
    nom: str = Field(min_length=2, max_length=120)
    type: Literal["immeuble", "maison", "appartement", "autre"] = "immeuble"
    adresse_ligne1: str = Field(min_length=3, max_length=160)
    adresse_ligne2: str = Field(default="", max_length=160)
    code_postal: str = Field(default="", max_length=20)
    ville: str = Field(min_length=2, max_length=100)
    pays: str = Field(default="France", max_length=80)
    description: str = Field(default="", max_length=2000)


class Property(PropertyCreate):
    id: str
    workspace_id: str
    lots_count: int = 0
    created_at: str
    updated_at: str


class LotCreate(BaseModel):
    identifiant: str = Field(min_length=1, max_length=80)
    type: Literal["appartement", "maison", "studio", "chambre", "local", "autre"] = "appartement"
    etage: str = Field(default="", max_length=30)
    surface_m2: float | None = Field(default=None, ge=0, le=10000)
    pieces: int | None = Field(default=None, ge=0, le=100)
    chambres: int | None = Field(default=None, ge=0, le=100)
    loyer_mensuel_eur: int | None = Field(default=None, ge=0, le=1_000_000)
    charges_mensuelles_eur: int = Field(default=0, ge=0, le=1_000_000)
    depot_garantie_eur: int | None = Field(default=None, ge=0, le=1_000_000)
    statut: Literal["brouillon", "disponible", "occupe", "archive"] = "brouillon"


class Lot(LotCreate):
    id: str
    workspace_id: str
    bien_id: str
    created_at: str
    updated_at: str


class PasswordChangeRequest(BaseModel):
    current_mdp: str = Field(min_length=1, max_length=128)
    nouveau_mdp: str = Field(min_length=8, max_length=128)


class PasswordResetRequest(BaseModel):
    email: str
    prenom: str = ""


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=160)
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
                google_sub TEXT,
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
            CREATE TABLE IF NOT EXISTS properties (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                nom TEXT NOT NULL,
                property_type TEXT NOT NULL,
                adresse_ligne1 TEXT NOT NULL,
                adresse_ligne2 TEXT NOT NULL DEFAULT '',
                code_postal TEXT NOT NULL DEFAULT '',
                ville TEXT NOT NULL,
                pays TEXT NOT NULL DEFAULT 'France',
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS properties_workspace_idx ON properties(workspace_id);
            CREATE TABLE IF NOT EXISTS lots (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                property_id TEXT NOT NULL,
                identifiant TEXT NOT NULL,
                lot_type TEXT NOT NULL,
                etage TEXT NOT NULL DEFAULT '',
                surface_m2 REAL,
                pieces INTEGER,
                chambres INTEGER,
                loyer_mensuel_eur INTEGER,
                charges_mensuelles_eur INTEGER NOT NULL DEFAULT 0,
                depot_garantie_eur INTEGER,
                statut TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(property_id, identifiant),
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(property_id) REFERENCES properties(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS lots_workspace_idx ON lots(workspace_id);
            CREATE INDEX IF NOT EXISTS lots_property_idx ON lots(property_id);
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                expires_at REAL NOT NULL,
                FOREIGN KEY(email) REFERENCES candidates(email) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions(expires_at);
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                token_hash TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                expires_at REAL NOT NULL,
                used_at REAL,
                FOREIGN KEY(email) REFERENCES candidates(email) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS password_reset_email_idx ON password_reset_tokens(email);
            CREATE TABLE IF NOT EXISTS google_oauth_states (
                state_hash TEXT PRIMARY KEY,
                expires_at REAL NOT NULL
            );
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
        if "google_sub" not in candidate_columns:
            connection.execute("ALTER TABLE candidates ADD COLUMN google_sub TEXT")
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS candidates_google_sub_idx ON candidates(google_sub) WHERE google_sub IS NOT NULL AND google_sub <> ''"
        )

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


def _google_error(message: str, code: int = 503) -> JSONResponse:
    return JSONResponse(status_code=code, content={"ok": False, "erreur": message})


def _create_workspace(connection: sqlite3.Connection, email: str, prenom: str) -> str:
    workspace_id = f"ws-{uuid4().hex[:16]}"
    connection.execute(
        "INSERT INTO workspaces(id, name, owner_email, created_at) VALUES (?, ?, ?, datetime('now'))",
        (workspace_id, f"Espace de {prenom}", email),
    )
    return workspace_id


def _google_is_configured() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI)


def _google_token_exchange(code: str) -> dict[str, object]:
    body = urlencode(
        {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    request = URLRequest(
        "https://oauth2.googleapis.com/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="Google n'a pas fourni de jeton exploitable.") from exc
    if not payload.get("id_token"):
        raise HTTPException(status_code=502, detail="La réponse Google ne contient pas d'identité.")
    return payload


def _verify_google_identity(id_token_value: str) -> tuple[str, str, str]:
    try:
        from google.auth.transport.requests import Request as GoogleRequest
        from google.oauth2 import id_token as google_id_token
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Le module Google OAuth n'est pas installé.") from exc
    try:
        claims = google_id_token.verify_oauth2_token(
            id_token_value, GoogleRequest(), GOOGLE_CLIENT_ID
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="L'identité Google n'est pas valide.") from exc

    subject = str(claims.get("sub", "")).strip()
    email = _normalise_email(str(claims.get("email", "")))
    verified = claims.get("email_verified") is True
    prenom = _clean_text(str(claims.get("given_name") or claims.get("name") or ""), 40)
    if not subject or not EMAIL_RE.fullmatch(email) or not verified or not prenom:
        raise HTTPException(status_code=401, detail="Le compte Google ne fournit pas une identité vérifiée.")
    return subject, email, prenom


def _find_or_create_google_owner(subject: str, email: str, prenom: str) -> tuple[str, str, str]:
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT email, prenom, workspace_id, google_sub FROM candidates WHERE google_sub = ?",
            (subject,),
        ).fetchone()
        if row is None:
            row = connection.execute(
                "SELECT email, prenom, workspace_id, google_sub FROM candidates WHERE email = ?",
                (email,),
            ).fetchone()
        if row is None:
            salt = secrets.token_bytes(16)
            workspace_id = _create_workspace(connection, email, prenom)
            connection.execute(
                """
                INSERT INTO candidates(email, prenom, salt, password_hash, workspace_id, google_sub, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (email, prenom, salt, _password_hash(secrets.token_urlsafe(32), salt), workspace_id, subject),
            )
            # The member row references candidates, so create it after the account.
            connection.execute(
                "INSERT OR IGNORE INTO workspace_members(workspace_id, email, role, joined_at) VALUES (?, ?, 'owner', datetime('now'))",
                (workspace_id, email),
            )
            connection.commit()
            return prenom, email, workspace_id

        if row["google_sub"] and row["google_sub"] != subject:
            raise HTTPException(status_code=409, detail="Cette adresse est déjà liée à un autre compte Google.")
        workspace_id = row["workspace_id"]
        if not workspace_id:
            workspace_id = _create_workspace(connection, email, row["prenom"])
        connection.execute(
            "UPDATE candidates SET google_sub = ?, workspace_id = ? WHERE email = ?",
            (subject, workspace_id, email),
        )
        connection.execute(
            "INSERT OR IGNORE INTO workspace_members(workspace_id, email, role, joined_at) VALUES (?, ?, 'owner', datetime('now'))",
            (workspace_id, email),
        )
        connection.commit()
        return row["prenom"], email, workspace_id


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


def _property_from_row(row: sqlite3.Row) -> Property:
    return Property(
        id=row["id"],
        workspace_id=row["workspace_id"],
        nom=row["nom"],
        type=row["property_type"],
        adresse_ligne1=row["adresse_ligne1"],
        adresse_ligne2=row["adresse_ligne2"],
        code_postal=row["code_postal"],
        ville=row["ville"],
        pays=row["pays"],
        description=row["description"],
        lots_count=row["lots_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _lot_from_row(row: sqlite3.Row) -> Lot:
    return Lot(
        id=row["id"],
        workspace_id=row["workspace_id"],
        bien_id=row["property_id"],
        identifiant=row["identifiant"],
        type=row["lot_type"],
        etage=row["etage"],
        surface_m2=row["surface_m2"],
        pieces=row["pieces"],
        chambres=row["chambres"],
        loyer_mensuel_eur=row["loyer_mensuel_eur"],
        charges_mensuelles_eur=row["charges_mensuelles_eur"],
        depot_garantie_eur=row["depot_garantie_eur"],
        statut=row["statut"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _property_query() -> str:
    return """
        SELECT p.*, COUNT(l.id) AS lots_count
        FROM properties p
        LEFT JOIN lots l ON l.property_id = p.id
    """


def _owned_property_row(
    connection: sqlite3.Connection, owner: Candidate, property_id: str
) -> sqlite3.Row:
    row = connection.execute(
        _property_query()
        + " WHERE p.id = ? AND p.workspace_id = ? GROUP BY p.id",
        (property_id, owner.workspace_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Bien introuvable dans ce workspace.")
    return row


def _owned_lot_row(
    connection: sqlite3.Connection, owner: Candidate, property_id: str, lot_id: str
) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM lots WHERE id = ? AND property_id = ? AND workspace_id = ?",
        (lot_id, property_id, owner.workspace_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Lot introuvable dans ce workspace.")
    return row


def _clean_property_payload(payload: PropertyCreate) -> PropertyCreate:
    cleaned = PropertyCreate(
        nom=_clean_text(payload.nom, 120),
        type=payload.type,
        adresse_ligne1=_clean_text(payload.adresse_ligne1, 160),
        adresse_ligne2=_clean_text(payload.adresse_ligne2, 160),
        code_postal=_clean_text(payload.code_postal, 20),
        ville=_clean_text(payload.ville, 100),
        pays=_clean_text(payload.pays, 80) or "France",
        description=_clean_text(payload.description, 2000),
    )
    if len(cleaned.nom) < 2 or len(cleaned.adresse_ligne1) < 3 or len(cleaned.ville) < 2:
        raise HTTPException(status_code=400, detail="Le nom, l'adresse et la ville sont obligatoires.")
    return cleaned


def _clean_lot_payload(payload: LotCreate) -> LotCreate:
    cleaned = LotCreate(
        identifiant=_clean_text(payload.identifiant, 80),
        type=payload.type,
        etage=_clean_text(payload.etage, 30),
        surface_m2=payload.surface_m2,
        pieces=payload.pieces,
        chambres=payload.chambres,
        loyer_mensuel_eur=payload.loyer_mensuel_eur,
        charges_mensuelles_eur=payload.charges_mensuelles_eur,
        depot_garantie_eur=payload.depot_garantie_eur,
        statut=payload.statut,
    )
    if not cleaned.identifiant:
        raise HTTPException(status_code=400, detail="L'identifiant du lot est obligatoire.")
    return cleaned


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


@app.get("/api/auth/google/start", response_model=None)
def google_start(request: Request) -> RedirectResponse | JSONResponse:
    """Start Google OpenID Connect with identity-only scopes."""

    if not _google_is_configured():
        return _google_error("La connexion Google n'est pas encore configurée.")

    state = secrets.token_urlsafe(32)
    state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()
    with closing(_connect()) as connection:
        connection.execute("DELETE FROM google_oauth_states WHERE expires_at < ?", (time.time(),))
        connection.execute(
            "INSERT INTO google_oauth_states(state_hash, expires_at) VALUES (?, ?)",
            (state_hash, time.time() + GOOGLE_STATE_SECONDS),
        )
        connection.commit()

    query = urlencode(
        {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    response = RedirectResponse(
        f"https://accounts.google.com/o/oauth2/v2/auth?{query}", status_code=302
    )
    response.set_cookie(
        GOOGLE_STATE_COOKIE,
        state,
        max_age=GOOGLE_STATE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=_secure_cookie(request),
        path="/",
    )
    return response


@app.get("/api/auth/google/callback", response_model=None)
def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse | JSONResponse:
    """Consume Google's one-time code and create the normal Piaule session."""

    if error:
        return _google_error("La connexion Google a été annulée.", 400)
    if not code or not state:
        return _google_error("La réponse Google est incomplète.", 400)
    state_cookie = request.cookies.get(GOOGLE_STATE_COOKIE)
    if not state_cookie or not hmac.compare_digest(state, state_cookie):
        return _google_error("La vérification de sécurité Google a échoué.", 400)

    state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT state_hash FROM google_oauth_states WHERE state_hash = ? AND expires_at > ?",
            (state_hash, time.time()),
        ).fetchone()
        connection.execute("DELETE FROM google_oauth_states WHERE state_hash = ?", (state_hash,))
        connection.commit()
    if row is None:
        return _google_error("La session Google a expiré. Recommence la connexion.", 400)

    token_payload = _google_token_exchange(code)
    subject, email, prenom = _verify_google_identity(str(token_payload["id_token"]))
    owner_prenom, owner_email, workspace_id = _find_or_create_google_owner(subject, email, prenom)

    response = RedirectResponse(FRONTEND_REDIRECT_URI, status_code=303)
    _set_session(response, request, owner_email)
    response.delete_cookie(
        GOOGLE_STATE_COOKIE,
        httponly=True,
        samesite="lax",
        secure=_secure_cookie(request),
        path="/",
    )
    return response


@app.post("/api/mot-de-passe-oublie")
def forgot_password(payload: PasswordResetRequest) -> dict[str, object]:
    """Prepare a single-use reset token without revealing whether an email exists."""

    email = _normalise_email(payload.email)
    prenom = _clean_text(payload.prenom, 40).casefold()
    reset_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(reset_token.encode("utf-8")).hexdigest()
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT prenom FROM candidates WHERE email = ?", (email,)
        ).fetchone()
        if row is not None and prenom and row["prenom"].casefold() == prenom:
            connection.execute("DELETE FROM password_reset_tokens WHERE email = ?", (email,))
            connection.execute(
                "INSERT INTO password_reset_tokens(token_hash, email, expires_at) VALUES (?, ?, ?)",
                (token_hash, email, time.time() + 900),
            )
        connection.commit()

    result: dict[str, object] = {
        "ok": True,
        "message": "Si les informations correspondent, un lien de réinitialisation sera envoyé.",
    }
    if os.getenv("PIAULE_EXPOSE_DEV_RESET_TOKEN", "false").lower() == "true":
        result["dev_reset_token"] = reset_token
    return result


@app.post("/api/mot-de-passe-reinitialiser")
def reset_password(payload: PasswordResetConfirm, request: Request) -> JSONResponse:
    """Use a reset token once, then revoke all sessions for that account."""

    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    salt = secrets.token_bytes(16)
    with closing(_connect()) as connection:
        row = connection.execute(
            """
            SELECT email FROM password_reset_tokens
            WHERE token_hash = ? AND expires_at > ? AND used_at IS NULL
            """,
            (token_hash, time.time()),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=400, detail="Ce lien de réinitialisation est invalide ou expiré.")
        connection.execute(
            "UPDATE candidates SET salt = ?, password_hash = ? WHERE email = ?",
            (salt, _password_hash(payload.nouveau_mdp, salt), row["email"]),
        )
        connection.execute(
            "UPDATE password_reset_tokens SET used_at = ? WHERE token_hash = ?",
            (time.time(), token_hash),
        )
        connection.execute("DELETE FROM sessions WHERE email = ?", (row["email"],))
        connection.commit()
    return JSONResponse(status_code=200, content={"ok": True})


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


@app.get("/api/biens", response_model=list[Property])
def list_properties(owner: Candidate = Depends(current_candidate)) -> list[Property]:
    """List only the properties belonging to the authenticated owner's workspace."""

    with closing(_connect()) as connection:
        rows = connection.execute(
            _property_query()
            + " WHERE p.workspace_id = ? GROUP BY p.id ORDER BY p.created_at DESC, p.id",
            (owner.workspace_id,),
        ).fetchall()
    return [_property_from_row(row) for row in rows]


@app.post("/api/biens", response_model=Property, status_code=201)
def create_property(
    payload: PropertyCreate, owner: Candidate = Depends(current_candidate)
) -> Property:
    """Create a property in the current owner's workspace."""

    cleaned = _clean_property_payload(payload)
    property_id = f"bien-{uuid4().hex[:16]}"
    with closing(_connect()) as connection:
        connection.execute(
            """
            INSERT INTO properties(
                id, workspace_id, nom, property_type, adresse_ligne1,
                adresse_ligne2, code_postal, ville, pays, description,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                property_id,
                owner.workspace_id,
                cleaned.nom,
                cleaned.type,
                cleaned.adresse_ligne1,
                cleaned.adresse_ligne2,
                cleaned.code_postal,
                cleaned.ville,
                cleaned.pays,
                cleaned.description,
            ),
        )
        connection.commit()
        row = _owned_property_row(connection, owner, property_id)
    return _property_from_row(row)


@app.get("/api/biens/{property_id}", response_model=Property)
def get_property(
    property_id: str, owner: Candidate = Depends(current_candidate)
) -> Property:
    with closing(_connect()) as connection:
        row = _owned_property_row(connection, owner, property_id)
    return _property_from_row(row)


@app.put("/api/biens/{property_id}", response_model=Property)
def update_property(
    property_id: str,
    payload: PropertyCreate,
    owner: Candidate = Depends(current_candidate),
) -> Property:
    """Update property metadata without changing its workspace ownership."""

    cleaned = _clean_property_payload(payload)
    with closing(_connect()) as connection:
        _owned_property_row(connection, owner, property_id)
        connection.execute(
            """
            UPDATE properties SET
                nom = ?, property_type = ?, adresse_ligne1 = ?, adresse_ligne2 = ?,
                code_postal = ?, ville = ?, pays = ?, description = ?, updated_at = datetime('now')
            WHERE id = ? AND workspace_id = ?
            """,
            (
                cleaned.nom,
                cleaned.type,
                cleaned.adresse_ligne1,
                cleaned.adresse_ligne2,
                cleaned.code_postal,
                cleaned.ville,
                cleaned.pays,
                cleaned.description,
                property_id,
                owner.workspace_id,
            ),
        )
        connection.commit()
        row = _owned_property_row(connection, owner, property_id)
    return _property_from_row(row)


@app.get("/api/biens/{property_id}/lots", response_model=list[Lot])
def list_lots(
    property_id: str, owner: Candidate = Depends(current_candidate)
) -> list[Lot]:
    with closing(_connect()) as connection:
        _owned_property_row(connection, owner, property_id)
        rows = connection.execute(
            """
            SELECT * FROM lots
            WHERE property_id = ? AND workspace_id = ?
            ORDER BY created_at DESC, id
            """,
            (property_id, owner.workspace_id),
        ).fetchall()
    return [_lot_from_row(row) for row in rows]


@app.post("/api/biens/{property_id}/lots", response_model=Lot, status_code=201)
def create_lot(
    property_id: str,
    payload: LotCreate,
    owner: Candidate = Depends(current_candidate),
) -> Lot:
    """Create a rentable lot attached to an owned property."""

    cleaned = _clean_lot_payload(payload)
    lot_id = f"lot-{uuid4().hex[:16]}"
    with closing(_connect()) as connection:
        _owned_property_row(connection, owner, property_id)
        try:
            connection.execute(
                """
                INSERT INTO lots(
                    id, workspace_id, property_id, identifiant, lot_type, etage,
                    surface_m2, pieces, chambres, loyer_mensuel_eur,
                    charges_mensuelles_eur, depot_garantie_eur, statut,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (
                    lot_id,
                    owner.workspace_id,
                    property_id,
                    cleaned.identifiant,
                    cleaned.type,
                    cleaned.etage,
                    cleaned.surface_m2,
                    cleaned.pieces,
                    cleaned.chambres,
                    cleaned.loyer_mensuel_eur,
                    cleaned.charges_mensuelles_eur,
                    cleaned.depot_garantie_eur,
                    cleaned.statut,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Un lot porte déjà cet identifiant dans ce bien.") from exc
        connection.commit()
        row = _owned_lot_row(connection, owner, property_id, lot_id)
    return _lot_from_row(row)


@app.get("/api/biens/{property_id}/lots/{lot_id}", response_model=Lot)
def get_lot(
    property_id: str, lot_id: str, owner: Candidate = Depends(current_candidate)
) -> Lot:
    with closing(_connect()) as connection:
        row = _owned_lot_row(connection, owner, property_id, lot_id)
    return _lot_from_row(row)


@app.put("/api/biens/{property_id}/lots/{lot_id}", response_model=Lot)
def update_lot(
    property_id: str,
    lot_id: str,
    payload: LotCreate,
    owner: Candidate = Depends(current_candidate),
) -> Lot:
    cleaned = _clean_lot_payload(payload)
    with closing(_connect()) as connection:
        _owned_lot_row(connection, owner, property_id, lot_id)
        try:
            connection.execute(
                """
                UPDATE lots SET
                    identifiant = ?, lot_type = ?, etage = ?, surface_m2 = ?,
                    pieces = ?, chambres = ?, loyer_mensuel_eur = ?,
                    charges_mensuelles_eur = ?, depot_garantie_eur = ?,
                    statut = ?, updated_at = datetime('now')
                WHERE id = ? AND property_id = ? AND workspace_id = ?
                """,
                (
                    cleaned.identifiant,
                    cleaned.type,
                    cleaned.etage,
                    cleaned.surface_m2,
                    cleaned.pieces,
                    cleaned.chambres,
                    cleaned.loyer_mensuel_eur,
                    cleaned.charges_mensuelles_eur,
                    cleaned.depot_garantie_eur,
                    cleaned.statut,
                    lot_id,
                    property_id,
                    owner.workspace_id,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Un lot porte déjà cet identifiant dans ce bien.") from exc
        connection.commit()
        row = _owned_lot_row(connection, owner, property_id, lot_id)
    return _lot_from_row(row)


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
