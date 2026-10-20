"""Piaule Fiction owner workspace API.

The current production-shaped slice preserves account/session primitives and
synthetic source contracts while the domain moves to owner workspaces,
properties, applications, agent actions and approvals. The API is the source
of truth; the browser may keep a display cache but never defines ownership.
"""

from __future__ import annotations

import hashlib
import hmac
import imaplib
import json
import os
import re
import secrets
import sqlite3
import smtplib
import time
import base64
import unicodedata
from contextlib import closing
from datetime import date, datetime, timezone
from email import policy
from email.header import decode_header, make_header
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.utils import getaddresses, parseaddr
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as URLRequest, urlopen
from uuid import uuid4

from fastapi import Body, Cookie, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
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
DOSSIER_FACILE_ENABLED = os.getenv("PIAULE_DOSSIER_FACILE_ENABLED", "false").lower() == "true"
DOSSIER_FACILE_CLIENT_ID = os.getenv("PIAULE_DOSSIER_FACILE_CLIENT_ID", "").strip()
DOSSIER_FACILE_CLIENT_SECRET = os.getenv("PIAULE_DOSSIER_FACILE_CLIENT_SECRET", "").strip()
DOSSIER_FACILE_AUTH_URL = os.getenv("PIAULE_DOSSIER_FACILE_AUTH_URL", "").strip()
DOSSIER_FACILE_TOKEN_URL = os.getenv("PIAULE_DOSSIER_FACILE_TOKEN_URL", "").strip()
DOSSIER_FACILE_PROFILE_URL = os.getenv("PIAULE_DOSSIER_FACILE_PROFILE_URL", "").strip()
DOSSIER_FACILE_REDIRECT_URI = os.getenv("PIAULE_DOSSIER_FACILE_REDIRECT_URI", "").strip()
DOSSIER_FACILE_WEBHOOK_TOKEN = os.getenv("PIAULE_DOSSIER_FACILE_WEBHOOK_TOKEN", "").strip()
DOSSIER_FACILE_STATE_SECONDS = 600
VERIFICATION_INTERNAL_TOKEN = os.getenv("PIAULE_VERIFICATION_INTERNAL_TOKEN", "").strip()
AGENT_INTERNAL_TOKEN = os.getenv("PIAULE_AGENT_INTERNAL_TOKEN", "").strip()
CANDIDATE_PORTAL_BASE_URL = os.getenv(
    "PIAULE_CANDIDATE_PORTAL_BASE_URL",
    "http://127.0.0.1:5173/candidature.html",
).strip()
CANDIDATE_LINK_SECONDS = 30 * 24 * 60 * 60

STATE_DIRECTORY = Path(os.getenv("PIAULE_STATE_DIRECTORY", ".local-state"))
DATABASE_PATH = Path(
    os.getenv("PIAULE_DATABASE_PATH", str(STATE_DIRECTORY / "piaule-fiction.sqlite3"))
)
UPLOAD_DIRECTORY = Path(os.getenv("PIAULE_UPLOAD_DIRECTORY", str(STATE_DIRECTORY / "uploads")))
MAX_DOCUMENT_BYTES = 100 * 1024 * 1024
ALLOWED_DOCUMENT_TYPES = {
    "pdf": {"application/pdf"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "png": {"image/png"},
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


AgentRunStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
ActionStatus = Literal[
    "proposee",
    "a_valider",
    "autorisee",
    "executee",
    "confirmee",
    "refusee",
    "expiree",
    "bloquee",
]
ActionRisk = Literal[
    "lecture",
    "brouillon",
    "transmission",
    "engagement_financier",
    "decision",
    "irreversible",
]
ActionDecision = Literal["autorisee", "refusee"]

# This is the first hard boundary for agent autonomy. The model may suggest
# only an action that belongs to its role; the owner approval gate remains a
# separate boundary for sensitive actions.
AGENT_SCOPE_POLICIES: dict[str, set[str]] = {
    "orchestrateur": {"distribuer_mission", "preparer_plan"},
    "agent-bien": {"analyser_bien", "preparer_annonce"},
    "agent-candidatures": {"analyser_candidature", "rattacher_candidature", "dedoublonner_candidature"},
    "agent-completude": {
        "analyser_piece",
        "recalculer_completude",
        "preparer_message_candidat",
        "preparer_relance_completude",
    },
    "agent-dossier": {"analyser_piece", "recalculer_completude", "preparer_verification"},
    "agent-confiance": {"analyser_piece", "preparer_verification", "signaler_anomalie"},
    "agent-comparaison": {"comparer_candidatures", "preparer_recommandation"},
    "agent-visites": {"proposer_visite", "preparer_rappel_visite"},
    "agent-communication": {"preparer_message_candidat", "preparer_rappel_visite"},
    "agent-conformite": {"controler_conformite", "signaler_anomalie"},
    "agent-suivi": {"preparer_tache", "preparer_relance_echeance"},
}

# Catalogue visible par le propriétaire. Les lignes sont des rôles provisionnés
# dans chaque workspace ; elles ne donnent aucun accès entre workspaces.
OWNER_AGENT_CATALOG: dict[str, dict[str, object]] = {
    "orchestrateur": {
        "nom": "Orchestrateur",
        "description": "Point de contact principal du propriétaire.",
        "mission": "Comprendre la demande, distribuer le travail et faire remonter les exceptions.",
        "principal": True,
    },
    "agent-bien": {
        "nom": "Agent Bien",
        "description": "Structure les biens, lots et informations manquantes.",
        "mission": "Préparer une fiche bien exploitable et relever les champs à compléter.",
        "principal": False,
    },
    "agent-candidatures": {
        "nom": "Agent Candidatures",
        "description": "Rattache, organise et dédoublonne les dossiers reçus.",
        "mission": "Associer chaque candidature au bon bien et conserver sa provenance.",
        "principal": False,
    },
    "agent-completude": {
        "nom": "Agent Complétude",
        "description": "Suit les pièces reçues, manquantes et à corriger.",
        "mission": "Calculer l'état du dossier et préparer une demande ciblée au candidat.",
        "principal": False,
    },
    "agent-confiance": {
        "nom": "Agent Confiance",
        "description": "Analyse les documents et sépare les contrôles des preuves officielles.",
        "mission": "Relever les anomalies, incohérences et contrôles à approfondir.",
        "principal": False,
    },
    "agent-comparaison": {
        "nom": "Agent Comparaison",
        "description": "Compare les dossiers avec les critères définis pour le bien.",
        "mission": "Préparer une synthèse explicable avec faits, preuves et inconnues.",
        "principal": False,
    },
    "agent-visites": {
        "nom": "Agent Visites",
        "description": "Prépare les créneaux et le suivi des rendez-vous.",
        "mission": "Proposer des créneaux compatibles sans confirmer à la place du propriétaire.",
        "principal": False,
    },
    "agent-communication": {
        "nom": "Agent Communication",
        "description": "Prépare les messages liés aux candidatures et aux visites.",
        "mission": "Rédiger des messages précis qui restent soumis aux permissions configurées.",
        "principal": False,
    },
    "agent-conformite": {
        "nom": "Agent Conformité",
        "description": "Contrôle les règles et bloque les demandes hors périmètre.",
        "mission": "Signaler les risques réglementaires, les pièces disproportionnées et les exceptions.",
        "principal": False,
    },
    "agent-suivi": {
        "nom": "Agent Suivi",
        "description": "Surveille les prochaines échéances et les tâches ouvertes.",
        "mission": "Préparer les rappels et faire remonter les éléments qui nécessitent une décision.",
        "principal": False,
    },
}


class AgentRunCreate(BaseModel):
    type_agent: str = Field(min_length=2, max_length=120)
    mission: str = Field(min_length=2, max_length=2000)
    cible_type: str = Field(default="", max_length=80)
    cible_id: str = Field(default="", max_length=160)
    entree: dict[str, object] = Field(default_factory=dict)


class AgentRun(BaseModel):
    id: str
    workspace_id: str
    type_agent: str
    mission: str
    cible_type: str
    cible_id: str
    statut: AgentRunStatus
    entree: dict[str, object]
    sortie: dict[str, object]
    preuves: list[dict[str, object]]
    erreur: str
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str
    updated_at: str


class AgentRunStatusUpdate(BaseModel):
    statut: AgentRunStatus
    sortie: dict[str, object] = Field(default_factory=dict)
    preuves: list[dict[str, object]] = Field(default_factory=list)
    erreur: str = Field(default="", max_length=4000)


AgentStatus = Literal["active", "paused"]
AgentMessageDirection = Literal["proprietaire", "agent"]
AgentMessageStatus = Literal["a_traiter", "en_cours", "repondu", "archive"]


class OwnerAgent(BaseModel):
    id: str
    workspace_id: str
    role: str
    nom: str
    description: str
    mission: str
    statut: AgentStatus
    principal: bool
    version_politique: str
    created_at: str
    updated_at: str


class OwnerAgentMessageCreate(BaseModel):
    contenu: str = Field(min_length=2, max_length=4000)
    contexte_type: str = Field(default="", max_length=80)
    contexte_id: str = Field(default="", max_length=160)


class OwnerAgentMessage(BaseModel):
    id: str
    workspace_id: str
    agent_id: str
    agent_role: str
    direction: AgentMessageDirection
    contenu: str
    statut: AgentMessageStatus
    run_id: str | None = None
    created_at: str
    updated_at: str


class ActionCreate(BaseModel):
    type_action: str = Field(min_length=2, max_length=120)
    libelle: str = Field(min_length=2, max_length=240)
    description: str = Field(default="", max_length=4000)
    niveau_risque: ActionRisk = "transmission"
    destinataire: str = Field(default="", max_length=500)
    cible_type: str = Field(default="", max_length=80)
    cible_id: str = Field(default="", max_length=160)
    bien_id: str | None = Field(default=None, max_length=160)
    candidature_id: str | None = Field(default=None, max_length=160)
    agent_run_id: str | None = Field(default=None, max_length=160)
    payload: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=8, max_length=180)
    expire_le: str | None = Field(default=None, max_length=80)


class Action(BaseModel):
    id: str
    workspace_id: str
    agent_run_id: str | None = None
    type_action: str
    libelle: str
    description: str
    niveau_risque: ActionRisk
    necessite_validation: bool
    destinataire: str
    cible_type: str
    cible_id: str
    bien_id: str | None = None
    candidature_id: str | None = None
    payload: dict[str, object]
    empreinte_payload: str
    idempotency_key: str
    statut: ActionStatus
    expire_le: str | None = None
    autorisee_le: str | None = None
    executee_le: str | None = None
    reference_execution: str = ""
    dernier_motif: str = ""
    created_at: str
    updated_at: str


class ActionDecisionRequest(BaseModel):
    motif: str = Field(default="", max_length=2000)


class ActionExecutionUpdate(BaseModel):
    reference_execution: str = Field(default="", max_length=240)
    resultat: dict[str, object] = Field(default_factory=dict)


class InternalAgentRunCreate(AgentRunCreate):
    workspace_id: str = Field(min_length=3, max_length=160)


class InternalAgentActionCreate(ActionCreate):
    workspace_id: str = Field(min_length=3, max_length=160)


class AuditEvent(BaseModel):
    id: str
    workspace_id: str
    acteur_type: str
    acteur_id: str
    evenement: str
    entite_type: str
    entite_id: str
    bien_id: str | None = None
    candidature_id: str | None = None
    metadata: dict[str, object]
    created_at: str


VerificationPolicy = Literal["standard", "renforcee", "officielle"]
VerificationSource = Literal[
    "employeur",
    "dossier_facile",
    "france_identite",
    "dgfip",
    "revue_humaine",
]
VerificationRequestStatus = Literal[
    "en_attente_consentement",
    "en_attente_source",
    "confirmee",
    "non_confirmee",
    "expiree",
    "annulee",
]


class PropertyCreate(BaseModel):
    nom: str = Field(min_length=2, max_length=120)
    type: Literal["immeuble", "maison", "appartement", "autre"] = "immeuble"
    structure: Literal["immeuble", "bien_individuel"] = "bien_individuel"
    adresse_ligne1: str = Field(min_length=3, max_length=160)
    adresse_ligne2: str = Field(default="", max_length=160)
    code_postal: str = Field(default="", max_length=20)
    ville: str = Field(min_length=2, max_length=100)
    pays: str = Field(default="France", max_length=80)
    description: str = Field(default="", max_length=2000)
    description_publique: str = Field(default="", max_length=2000)
    statut: Literal["preparation", "vacant", "partiellement_occupe", "occupe", "archive"] = "preparation"
    date_disponibilite: date | None = None
    mode_detention: Literal["nom_propre", "indivision", "sci", "lmnp", "autre"] = "nom_propre"
    adresse_exacte_visible: bool = False
    equipements: list[str] = Field(default_factory=list)
    photos: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    syndic_nom: str = Field(default="", max_length=120)
    syndic_email: str = Field(default="", max_length=254)
    syndic_telephone: str = Field(default="", max_length=30)
    tantiemes_total: float | None = Field(default=None, ge=0, le=1_000_000)
    politique_verification: VerificationPolicy = "standard"


class Property(PropertyCreate):
    id: str
    workspace_id: str
    lots_count: int = 0
    created_at: str
    updated_at: str


class VerificationPolicyUpdate(BaseModel):
    politique: VerificationPolicy


class PropertyVerificationPolicy(BaseModel):
    bien_id: str
    politique: VerificationPolicy
    sources_disponibles: list[str]
    regles: list[str]
    mis_a_jour_le: str


class LotCreate(BaseModel):
    identifiant: str = Field(min_length=1, max_length=80)
    type: Literal["appartement", "maison", "studio", "chambre", "local", "autre"] = "appartement"
    type_location: Literal["non_precise", "vide", "meuble", "etudiant", "mobilite", "colocation", "parking", "local"] = "non_precise"
    etage: str = Field(default="", max_length=30)
    surface_m2: float | None = Field(default=None, ge=0, le=10000)
    pieces: int | None = Field(default=None, ge=0, le=100)
    chambres: int | None = Field(default=None, ge=0, le=100)
    loyer_mensuel_eur: int | None = Field(default=None, ge=0, le=1_000_000)
    charges_mensuelles_eur: int = Field(default=0, ge=0, le=1_000_000)
    type_charges: Literal["aucune", "provision", "forfait"] = "aucune"
    depot_garantie_eur: int | None = Field(default=None, ge=0, le=1_000_000)
    date_disponibilite: date | None = None
    revision_irl_active: bool = False
    indice_irl_reference: str = Field(default="", max_length=30)
    date_revision: date | None = None
    dpe_classe: Literal["inconnu", "A", "B", "C", "D", "E", "F", "G"] = "inconnu"
    ges_classe: Literal["inconnu", "A", "B", "C", "D", "E", "F", "G"] = "inconnu"
    dpe_date: date | None = None
    chauffage: str = Field(default="", max_length=100)
    eau_chaude: str = Field(default="", max_length=100)
    ascenseur: bool = False
    accessibilite: str = Field(default="", max_length=300)
    equipements: list[str] = Field(default_factory=list)
    dependances: list[str] = Field(default_factory=list)
    photos: list[str] = Field(default_factory=list)
    tantiemes_generaux: float | None = Field(default=None, ge=0, le=1_000_000)
    statut: Literal["brouillon", "disponible", "occupe", "archive"] = "brouillon"


class Lot(LotCreate):
    id: str
    workspace_id: str
    bien_id: str
    created_at: str
    updated_at: str


class PropertyRecordCreate(BaseModel):
    type: Literal["diagnostic", "assurance", "contrat_fournisseur", "document_copropriete", "autre"]
    titre: str = Field(min_length=2, max_length=160)
    lot_id: str | None = None
    fournisseur: str = Field(default="", max_length=160)
    reference: str = Field(default="", max_length=120)
    date_etablissement: date | None = None
    date_expiration: date | None = None
    statut: Literal["a_verifier", "valide", "expire"] = "a_verifier"
    notes: str = Field(default="", max_length=2000)


class PropertyRecord(PropertyRecordCreate):
    id: str
    workspace_id: str
    bien_id: str
    created_at: str
    updated_at: str


ApplicationStatus = Literal[
    "recue",
    "a_completer",
    "en_verification",
    "prete",
    "visite_proposee",
    "visite_confirmee",
    "retenue",
    "refusee",
    "retiree",
]

APPLICATION_STATUS_VALUES = {
    "recue",
    "a_completer",
    "en_verification",
    "prete",
    "visite_proposee",
    "visite_confirmee",
    "retenue",
    "refusee",
    "retiree",
}
APPLICATION_READY_STATUSES = {
    "prete",
    "visite_proposee",
    "visite_confirmee",
    "retenue",
}
APPLICATION_STATUS_TRANSITIONS = {
    "recue": {"a_completer", "en_verification", "prete", "refusee", "retiree"},
    "a_completer": {"recue", "en_verification", "prete", "refusee", "retiree"},
    "en_verification": {"recue", "a_completer", "prete", "refusee", "retiree"},
    "prete": {"a_completer", "en_verification", "visite_proposee", "refusee", "retiree"},
    "visite_proposee": {"prete", "visite_confirmee", "refusee", "retiree"},
    "visite_confirmee": {"visite_proposee", "retenue", "refusee", "retiree"},
    "retenue": {"refusee", "retiree"},
    "refusee": {"recue", "retiree"},
    "retiree": {"recue"},
}


class OwnerApplicationCreate(BaseModel):
    lot_id: str | None = None
    candidat_prenom: str = Field(min_length=1, max_length=80)
    candidat_nom: str = Field(min_length=1, max_length=120)
    candidat_email: str = Field(default="", max_length=254)
    candidat_telephone: str = Field(default="", max_length=30)
    source: Literal["formulaire", "email", "dossier_facile", "import", "partenaire", "autre"] = "formulaire"
    reference_source: str = Field(default="", max_length=160)
    statut: ApplicationStatus = "recue"
    notes_privees: str = Field(default="", max_length=3000)


class OwnerApplicationUpdate(BaseModel):
    lot_id: str | None = None
    candidat_prenom: str | None = Field(default=None, min_length=1, max_length=80)
    candidat_nom: str | None = Field(default=None, min_length=1, max_length=120)
    candidat_email: str | None = Field(default=None, max_length=254)
    candidat_telephone: str | None = Field(default=None, max_length=30)
    source: Literal["formulaire", "email", "dossier_facile", "import", "partenaire", "autre"] | None = None
    reference_source: str | None = Field(default=None, max_length=160)
    statut: ApplicationStatus | None = None
    notes_privees: str | None = Field(default=None, max_length=3000)


class ApplicationStatusUpdate(BaseModel):
    statut: ApplicationStatus
    motif: str = Field(default="", max_length=1000)


class OwnerApplication(BaseModel):
    id: str
    workspace_id: str
    bien_id: str
    bien_nom: str
    lot_id: str | None = None
    lot_identifiant: str | None = None
    candidat_prenom: str
    candidat_nom: str
    candidat_email: str
    candidat_telephone: str
    source: str
    reference_source: str
    statut: ApplicationStatus
    statut_motif: str = ""
    statut_source: str = "proprietaire"
    doublon_possible: bool = False
    notes_privees: str
    recue_le: str
    updated_at: str


class ApplicationStatusEvent(BaseModel):
    id: str
    candidature_id: str
    ancien_statut: str
    nouveau_statut: ApplicationStatus
    source: str
    motif: str
    created_at: str


VisitSlotStatus = Literal["libre", "reserve", "bloque"]
VisitMode = Literal["sur_place", "visio"]
VisitStatus = Literal["proposee", "confirmee", "refusee", "annulee", "terminee"]


class VisitSlotCreate(BaseModel):
    lot_id: str | None = None
    debut: str = Field(min_length=10, max_length=80)
    fin: str = Field(min_length=10, max_length=80)
    fuseau: str = Field(default="Europe/Paris", min_length=1, max_length=80)
    mode: VisitMode = "sur_place"
    note: str = Field(default="", max_length=500)


class VisitSlot(BaseModel):
    id: str
    workspace_id: str
    bien_id: str
    lot_id: str | None = None
    debut: str
    fin: str
    fuseau: str
    mode: VisitMode
    note: str
    statut: VisitSlotStatus
    created_at: str


class VisitCreate(BaseModel):
    slot_id: str
    note: str = Field(default="", max_length=1000)


class Visit(BaseModel):
    id: str
    workspace_id: str
    bien_id: str
    bien_nom: str
    lot_id: str | None = None
    lot_identifiant: str | None = None
    candidature_id: str
    candidat_prenom: str
    candidat_nom: str
    slot_id: str
    debut: str
    fin: str
    fuseau: str
    mode: VisitMode
    statut: VisitStatus
    source: Literal["proprietaire", "agent", "candidat"]
    note: str
    motif: str
    created_at: str
    updated_at: str


class CandidateVisitResponse(BaseModel):
    accepte: bool
    motif: str = Field(default="", max_length=500)


class VisitCancelRequest(BaseModel):
    motif: str = Field(default="", max_length=500)


class CandidateVisit(BaseModel):
    id: str
    bien_nom: str
    lot_identifiant: str | None = None
    debut: str
    fin: str
    fuseau: str
    mode: VisitMode
    statut: VisitStatus
    note: str
    motif: str
    created_at: str
    updated_at: str


class ApplicationChannelCreate(BaseModel):
    lot_id: str | None = None
    canal: Literal["leboncoin", "seloger", "pap", "site_agence", "site_proprietaire", "autre"]
    libelle: str = Field(default="", max_length=160)


class ApplicationChannel(ApplicationChannelCreate):
    id: str
    workspace_id: str
    bien_id: str
    adresse_reception: str
    actif: bool = True
    created_at: str


class InboundApplicationEmail(BaseModel):
    adresse_reception: str
    message_id: str = Field(min_length=1, max_length=300)
    expediteur_email: str = Field(default="", max_length=254)
    objet: str = Field(default="", max_length=500)
    contenu_texte: str = Field(default="", max_length=100_000)
    pieces_jointes: list[str] = Field(default_factory=list)
    recu_le: str | None = None


class InboundApplicationMessage(BaseModel):
    id: str
    workspace_id: str
    canal_id: str
    bien_id: str
    lot_id: str | None = None
    adresse_reception: str
    message_id: str
    expediteur_email: str
    objet: str
    contenu_texte: str
    pieces_jointes: list[str]
    statut: Literal["recue", "en_analyse", "associee", "a_verifier", "rejetee"]
    candidature_id: str | None = None
    recu_le: str


ApplicationDocumentType = Literal[
    "identite",
    "domicile",
    "situation_professionnelle",
    "ressources",
    "imposition",
    "garant",
    "autre",
]
ApplicationDocumentStatus = Literal[
    "recu",
    "en_verification",
    "valide",
    "a_corriger",
    "expire",
    "refuse",
]
ApplicationDocumentVerificationLevel = Literal[
    "non_verifie",
    "controles_techniques",
    "source_partenaire",
    "revue_humaine",
    "source_officielle",
]
ApplicationDocumentProvenance = Literal[
    "email",
    "dossier_facile",
    "portail_candidat",
    "import",
    "autre",
]


class ApplicationDocument(BaseModel):
    id: str
    workspace_id: str
    candidature_id: str
    bien_id: str
    type: ApplicationDocumentType
    nom: str
    filename: str
    content_type: str
    size_bytes: int
    empreinte_sha256: str
    provenance: ApplicationDocumentProvenance
    statut: ApplicationDocumentStatus
    niveau_verification: ApplicationDocumentVerificationLevel = "non_verifie"
    anomalies: list[str] = Field(default_factory=list)
    doublon_de: str | None = None
    derniere_verification: str | None = None
    date_expiration: str | None = None
    note_verification: str
    created_at: str
    updated_at: str


class ApplicationDocumentVerificationUpdate(BaseModel):
    statut: ApplicationDocumentStatus
    note_verification: str = Field(default="", max_length=2000)
    date_expiration: str | None = None


class ApplicationDocumentCheck(BaseModel):
    id: str
    document_id: str
    resultat: Literal["ok_technique", "attention", "bloque", "non_verifiable"]
    controles: dict[str, str]
    anomalies: list[str]
    version_moteur: str
    created_at: str


class ApplicationDocumentAnalysisResult(BaseModel):
    document: ApplicationDocument
    dernier_controle: ApplicationDocumentCheck


class ApplicationVerificationRequestCreate(BaseModel):
    source: VerificationSource
    motif: str = Field(default="", max_length=500)


class ApplicationVerificationRequest(BaseModel):
    id: str
    candidature_id: str
    document_id: str
    source: VerificationSource
    statut: VerificationRequestStatus
    motif: str
    consentement_requis: bool
    consentement_donne_le: str | None = None
    preuve: dict[str, object]
    resultat: str
    expire_le: str | None = None
    cree_le: str
    mis_a_jour_le: str


class CompletenessItem(BaseModel):
    type: ApplicationDocumentType
    statut: Literal[
        "manquante",
        "recu",
        "en_verification",
        "valide",
        "a_corriger",
        "expire",
        "refuse",
        "verifiee_par_dossier_facile",
    ]
    piece_id: str | None = None
    source: str = ""
    details: str = ""


class ApplicationCompleteness(BaseModel):
    candidature_id: str
    statut: Literal["a_completer", "en_verification", "complet"]
    score: int = Field(ge=0, le=100)
    pieces_requises: list[CompletenessItem]
    dossier_facile_statut: str = ""
    mis_a_jour_le: str


class CandidateAccessLink(BaseModel):
    id: str
    candidature_id: str
    url: str
    expire_le: int
    actif: bool = True


class CandidatePortalView(BaseModel):
    candidature_id: str
    candidat_prenom: str
    bien_nom: str
    statut_candidature: ApplicationStatus
    completude: ApplicationCompleteness


class CandidateMessageCreate(BaseModel):
    contenu: str = Field(min_length=1, max_length=5000)
    sujet: str = Field(default="", max_length=160)


class OwnerCandidateMessageCreate(BaseModel):
    contenu: str = Field(min_length=1, max_length=5000)
    sujet: str = Field(default="", max_length=160)


class CandidateMessage(BaseModel):
    id: str
    candidature_id: str
    direction: Literal["entrant", "sortant"]
    sujet: str
    contenu: str
    source: Literal["email", "portail_candidat", "agent", "proprietaire"]
    statut: Literal["recu", "a_envoyer", "en_cours", "envoye", "erreur"]
    created_at: str


class CandidateCompletenessFollowUp(BaseModel):
    id: str
    candidature_id: str
    pieces_demandees: list[ApplicationDocumentType]
    message_id: str | None = None
    lien_depot: str | None = None
    statut: Literal["a_envoyer", "deja_preparee", "aucune_piece_manquante", "sans_email"]
    human_approval_required: bool = False
    refus_decision_proprietaire: bool = True
    created_at: str


class EmailOutboxProcessResult(BaseModel):
    traite: int
    envoyes: int
    erreurs: int
    configuration: str


class EmailInboxSyncResult(BaseModel):
    lus: int
    importes: int
    associes: int
    pieces_stockees: int
    ignores: int
    erreurs: int
    configuration: str


class DossierFacileConnection(BaseModel):
    id: str
    workspace_id: str
    candidature_id: str
    statut: Literal["initiee", "connectee", "a_completer", "verifiee", "refusee", "erreur"]
    statut_dossier: str
    evenement: str
    tenant_id: str
    resume: dict[str, object]
    created_at: str
    updated_at: str


class DossierFacileConnectStart(BaseModel):
    id: str
    candidature_id: str
    statut: Literal["initiee"]
    autorisation_url: str
    expire_le: int


class DossierFacileWebhook(BaseModel):
    id: int | str | None = None
    onTenantId: int | str | None = None
    partnerCallBackType: str | None = None
    applicationType: str | None = None
    dossierUrl: str | None = None
    dossierPdfDocumentStatus: str | None = None
    dossierPdfUrl: str | None = None
    status: str | None = None


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


def _ensure_column(
    connection: sqlite3.Connection, table: str, column: str, definition: str
) -> None:
    """Add a newly introduced schema column to an existing local database."""

    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


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
                structure_type TEXT NOT NULL DEFAULT 'bien_individuel',
                adresse_ligne1 TEXT NOT NULL,
                adresse_ligne2 TEXT NOT NULL DEFAULT '',
                code_postal TEXT NOT NULL DEFAULT '',
                ville TEXT NOT NULL,
                pays TEXT NOT NULL DEFAULT 'France',
                description TEXT NOT NULL DEFAULT '',
                description_publique TEXT NOT NULL DEFAULT '',
                statut TEXT NOT NULL DEFAULT 'preparation',
                date_disponibilite TEXT,
                mode_detention TEXT NOT NULL DEFAULT 'nom_propre',
                adresse_exacte_visible INTEGER NOT NULL DEFAULT 0,
                equipements_json TEXT NOT NULL DEFAULT '[]',
                photos_json TEXT NOT NULL DEFAULT '[]',
                tags_json TEXT NOT NULL DEFAULT '[]',
                syndic_nom TEXT NOT NULL DEFAULT '',
                syndic_email TEXT NOT NULL DEFAULT '',
                syndic_telephone TEXT NOT NULL DEFAULT '',
                tantiemes_total REAL,
                verification_policy TEXT NOT NULL DEFAULT 'standard',
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
                type_location TEXT NOT NULL DEFAULT 'non_precise',
                etage TEXT NOT NULL DEFAULT '',
                surface_m2 REAL,
                pieces INTEGER,
                chambres INTEGER,
                loyer_mensuel_eur INTEGER,
                charges_mensuelles_eur INTEGER NOT NULL DEFAULT 0,
                type_charges TEXT NOT NULL DEFAULT 'aucune',
                depot_garantie_eur INTEGER,
                date_disponibilite TEXT,
                revision_irl_active INTEGER NOT NULL DEFAULT 0,
                indice_irl_reference TEXT NOT NULL DEFAULT '',
                date_revision TEXT,
                dpe_classe TEXT NOT NULL DEFAULT 'inconnu',
                ges_classe TEXT NOT NULL DEFAULT 'inconnu',
                dpe_date TEXT,
                chauffage TEXT NOT NULL DEFAULT '',
                eau_chaude TEXT NOT NULL DEFAULT '',
                ascenseur INTEGER NOT NULL DEFAULT 0,
                accessibilite TEXT NOT NULL DEFAULT '',
                equipements_json TEXT NOT NULL DEFAULT '[]',
                dependances_json TEXT NOT NULL DEFAULT '[]',
                photos_json TEXT NOT NULL DEFAULT '[]',
                tantiemes_generaux REAL,
                statut TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(property_id, identifiant),
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(property_id) REFERENCES properties(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS lots_workspace_idx ON lots(workspace_id);
            CREATE INDEX IF NOT EXISTS lots_property_idx ON lots(property_id);
            CREATE TABLE IF NOT EXISTS property_records (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                property_id TEXT NOT NULL,
                lot_id TEXT,
                record_type TEXT NOT NULL,
                titre TEXT NOT NULL,
                fournisseur TEXT NOT NULL DEFAULT '',
                reference TEXT NOT NULL DEFAULT '',
                date_etablissement TEXT,
                date_expiration TEXT,
                statut TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(property_id) REFERENCES properties(id) ON DELETE CASCADE,
                FOREIGN KEY(lot_id) REFERENCES lots(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS property_records_workspace_idx ON property_records(workspace_id);
            CREATE INDEX IF NOT EXISTS property_records_property_idx ON property_records(property_id);
            CREATE INDEX IF NOT EXISTS property_records_expiry_idx ON property_records(date_expiration);
            CREATE TABLE IF NOT EXISTS owner_applications (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                property_id TEXT NOT NULL,
                lot_id TEXT,
                candidat_prenom TEXT NOT NULL,
                candidat_nom TEXT NOT NULL,
                candidat_email TEXT NOT NULL DEFAULT '',
                candidat_telephone TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL,
                reference_source TEXT NOT NULL DEFAULT '',
                statut TEXT NOT NULL,
                statut_motif TEXT NOT NULL DEFAULT '',
                statut_source TEXT NOT NULL DEFAULT 'proprietaire',
                duplicate_key TEXT NOT NULL DEFAULT '',
                doublon_possible INTEGER NOT NULL DEFAULT 0,
                notes_privees TEXT NOT NULL DEFAULT '',
                recue_le TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(property_id) REFERENCES properties(id) ON DELETE CASCADE,
                FOREIGN KEY(lot_id) REFERENCES lots(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS owner_applications_workspace_idx ON owner_applications(workspace_id);
            CREATE INDEX IF NOT EXISTS owner_applications_property_idx ON owner_applications(property_id);
            CREATE INDEX IF NOT EXISTS owner_applications_duplicate_idx ON owner_applications(duplicate_key);
            CREATE TABLE IF NOT EXISTS application_status_history (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                application_id TEXT NOT NULL,
                property_id TEXT NOT NULL,
                previous_status TEXT NOT NULL DEFAULT '',
                new_status TEXT NOT NULL,
                source TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(application_id) REFERENCES owner_applications(id) ON DELETE CASCADE,
                FOREIGN KEY(property_id) REFERENCES properties(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS application_status_history_application_idx ON application_status_history(application_id, created_at);
            CREATE INDEX IF NOT EXISTS application_status_history_workspace_idx ON application_status_history(workspace_id, created_at);
            CREATE TABLE IF NOT EXISTS application_channels (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                property_id TEXT NOT NULL,
                lot_id TEXT,
                canal TEXT NOT NULL,
                libelle TEXT NOT NULL DEFAULT '',
                adresse_reception TEXT NOT NULL UNIQUE,
                actif INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(property_id) REFERENCES properties(id) ON DELETE CASCADE,
                FOREIGN KEY(lot_id) REFERENCES lots(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS application_channels_workspace_idx ON application_channels(workspace_id);
            CREATE INDEX IF NOT EXISTS application_channels_property_idx ON application_channels(property_id);
            CREATE TABLE IF NOT EXISTS inbound_application_messages (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                property_id TEXT NOT NULL,
                lot_id TEXT,
                adresse_reception TEXT NOT NULL,
                message_id TEXT NOT NULL,
                expediteur_email TEXT NOT NULL DEFAULT '',
                objet TEXT NOT NULL DEFAULT '',
                contenu_texte TEXT NOT NULL DEFAULT '',
                pieces_jointes_json TEXT NOT NULL DEFAULT '[]',
                statut TEXT NOT NULL,
                application_id TEXT,
                recu_le TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(workspace_id, message_id),
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(channel_id) REFERENCES application_channels(id) ON DELETE CASCADE,
                FOREIGN KEY(property_id) REFERENCES properties(id) ON DELETE CASCADE,
                FOREIGN KEY(lot_id) REFERENCES lots(id) ON DELETE SET NULL,
                FOREIGN KEY(application_id) REFERENCES owner_applications(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS inbound_application_workspace_idx ON inbound_application_messages(workspace_id);
            CREATE INDEX IF NOT EXISTS inbound_application_channel_idx ON inbound_application_messages(channel_id);
            CREATE TABLE IF NOT EXISTS dossier_facile_connections (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                application_id TEXT NOT NULL,
                state_hash TEXT NOT NULL UNIQUE,
                statut TEXT NOT NULL,
                statut_dossier TEXT NOT NULL DEFAULT '',
                evenement TEXT NOT NULL DEFAULT '',
                tenant_id TEXT NOT NULL DEFAULT '',
                resume_json TEXT NOT NULL DEFAULT '{}',
                expires_at REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(application_id) REFERENCES owner_applications(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS dossier_facile_workspace_idx ON dossier_facile_connections(workspace_id);
            CREATE INDEX IF NOT EXISTS dossier_facile_application_idx ON dossier_facile_connections(application_id);
            CREATE INDEX IF NOT EXISTS dossier_facile_tenant_idx ON dossier_facile_connections(tenant_id);
            CREATE TABLE IF NOT EXISTS application_documents (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                application_id TEXT NOT NULL,
                property_id TEXT NOT NULL,
                document_type TEXT NOT NULL,
                nom TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                provenance TEXT NOT NULL,
                statut TEXT NOT NULL,
                verification_level TEXT NOT NULL DEFAULT 'non_verifie',
                anomalies_json TEXT NOT NULL DEFAULT '[]',
                duplicate_of TEXT,
                checked_at TEXT,
                verification_engine_version TEXT NOT NULL DEFAULT '',
                date_expiration TEXT,
                note_verification TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(application_id) REFERENCES owner_applications(id) ON DELETE CASCADE,
                FOREIGN KEY(property_id) REFERENCES properties(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS application_documents_workspace_idx ON application_documents(workspace_id);
            CREATE INDEX IF NOT EXISTS application_documents_application_idx ON application_documents(application_id);
            CREATE INDEX IF NOT EXISTS application_documents_type_idx ON application_documents(application_id, document_type);
            CREATE INDEX IF NOT EXISTS application_documents_hash_idx ON application_documents(workspace_id, sha256);
            CREATE TABLE IF NOT EXISTS application_document_checks (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                application_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                result TEXT NOT NULL,
                checks_json TEXT NOT NULL DEFAULT '{}',
                anomalies_json TEXT NOT NULL DEFAULT '[]',
                engine_version TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(application_id) REFERENCES owner_applications(id) ON DELETE CASCADE,
                FOREIGN KEY(document_id) REFERENCES application_documents(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS application_document_checks_document_idx ON application_document_checks(document_id, created_at);
            CREATE TABLE IF NOT EXISTS application_verification_requests (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                application_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                motif TEXT NOT NULL DEFAULT '',
                consent_given_at TEXT,
                evidence_json TEXT NOT NULL DEFAULT '{}',
                result_summary TEXT NOT NULL DEFAULT '',
                external_reference_hash TEXT NOT NULL DEFAULT '',
                expires_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(application_id) REFERENCES owner_applications(id) ON DELETE CASCADE,
                FOREIGN KEY(document_id) REFERENCES application_documents(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS application_verification_requests_application_idx
                ON application_verification_requests(application_id, created_at);
            CREATE INDEX IF NOT EXISTS application_verification_requests_document_idx
                ON application_verification_requests(document_id, created_at);
            CREATE TABLE IF NOT EXISTS candidate_access_links (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                application_id TEXT NOT NULL,
                property_id TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at REAL NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(application_id) REFERENCES owner_applications(id) ON DELETE CASCADE,
                FOREIGN KEY(property_id) REFERENCES properties(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS candidate_access_application_idx ON candidate_access_links(application_id);
            CREATE INDEX IF NOT EXISTS candidate_access_expiry_idx ON candidate_access_links(expires_at);
            CREATE TABLE IF NOT EXISTS candidate_messages (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                application_id TEXT NOT NULL,
                property_id TEXT NOT NULL,
                direction TEXT NOT NULL,
                sujet TEXT NOT NULL DEFAULT '',
                contenu TEXT NOT NULL,
                source TEXT NOT NULL,
                statut TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(application_id) REFERENCES owner_applications(id) ON DELETE CASCADE,
                FOREIGN KEY(property_id) REFERENCES properties(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS candidate_messages_application_idx ON candidate_messages(application_id, created_at);
            CREATE TABLE IF NOT EXISTS visit_slots (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                property_id TEXT NOT NULL,
                lot_id TEXT,
                starts_at TEXT NOT NULL,
                ends_at TEXT NOT NULL,
                timezone TEXT NOT NULL DEFAULT 'Europe/Paris',
                mode TEXT NOT NULL DEFAULT 'sur_place',
                note TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'libre',
                created_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(property_id) REFERENCES properties(id) ON DELETE CASCADE,
                FOREIGN KEY(lot_id) REFERENCES lots(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS visit_slots_workspace_idx ON visit_slots(workspace_id, starts_at);
            CREATE INDEX IF NOT EXISTS visit_slots_property_idx ON visit_slots(property_id, starts_at);
            CREATE TABLE IF NOT EXISTS visits (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                property_id TEXT NOT NULL,
                lot_id TEXT,
                application_id TEXT NOT NULL,
                slot_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'proposee',
                source TEXT NOT NULL DEFAULT 'agent',
                note TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(property_id) REFERENCES properties(id) ON DELETE CASCADE,
                FOREIGN KEY(lot_id) REFERENCES lots(id) ON DELETE SET NULL,
                FOREIGN KEY(application_id) REFERENCES owner_applications(id) ON DELETE CASCADE,
                FOREIGN KEY(slot_id) REFERENCES visit_slots(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS visits_workspace_idx ON visits(workspace_id, created_at);
            CREATE INDEX IF NOT EXISTS visits_application_idx ON visits(application_id, created_at);
            CREATE INDEX IF NOT EXISTS visits_slot_idx ON visits(slot_id, status);
            CREATE TABLE IF NOT EXISTS agent_runs (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                mission TEXT NOT NULL,
                target_type TEXT NOT NULL DEFAULT '',
                target_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'queued',
                input_json TEXT NOT NULL DEFAULT '{}',
                output_json TEXT NOT NULL DEFAULT '{}',
                evidence_json TEXT NOT NULL DEFAULT '[]',
                error TEXT NOT NULL DEFAULT '',
                started_at TEXT,
                finished_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS agent_runs_workspace_idx ON agent_runs(workspace_id, created_at);
            CREATE TABLE IF NOT EXISTS workspace_agents (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                role_key TEXT NOT NULL,
                display_name TEXT NOT NULL,
                description TEXT NOT NULL,
                mission TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                is_primary INTEGER NOT NULL DEFAULT 0,
                policy_version TEXT NOT NULL DEFAULT 'v1',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(workspace_id, role_key),
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS workspace_agents_workspace_idx
                ON workspace_agents(workspace_id, is_primary DESC, created_at);
            CREATE TABLE IF NOT EXISTS agent_messages (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                agent_run_id TEXT,
                direction TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'a_traiter',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(agent_id) REFERENCES workspace_agents(id) ON DELETE CASCADE,
                FOREIGN KEY(agent_run_id) REFERENCES agent_runs(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS agent_messages_workspace_idx
                ON agent_messages(workspace_id, created_at);
            CREATE INDEX IF NOT EXISTS agent_messages_agent_idx
                ON agent_messages(agent_id, created_at);
            CREATE TABLE IF NOT EXISTS actions (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                agent_run_id TEXT,
                action_type TEXT NOT NULL,
                label TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                risk_level TEXT NOT NULL,
                requires_approval INTEGER NOT NULL DEFAULT 1,
                recipient TEXT NOT NULL DEFAULT '',
                target_type TEXT NOT NULL DEFAULT '',
                target_id TEXT NOT NULL DEFAULT '',
                property_id TEXT,
                application_id TEXT,
                payload_json TEXT NOT NULL DEFAULT '{}',
                payload_hash TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'a_valider',
                expires_at TEXT,
                approved_at TEXT,
                executed_at TEXT,
                execution_reference TEXT NOT NULL DEFAULT '',
                last_reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(workspace_id, idempotency_key),
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(agent_run_id) REFERENCES agent_runs(id) ON DELETE SET NULL,
                FOREIGN KEY(property_id) REFERENCES properties(id) ON DELETE SET NULL,
                FOREIGN KEY(application_id) REFERENCES owner_applications(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS actions_workspace_idx ON actions(workspace_id, created_at);
            CREATE INDEX IF NOT EXISTS actions_status_idx ON actions(workspace_id, status, created_at);
            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                action_id TEXT NOT NULL,
                approver_email TEXT NOT NULL,
                decision TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(action_id) REFERENCES actions(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS approvals_action_idx ON approvals(action_id, created_at);
            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                actor_type TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                event_name TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                property_id TEXT,
                application_id TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS audit_workspace_idx ON audit_events(workspace_id, created_at);
            CREATE INDEX IF NOT EXISTS audit_entity_idx ON audit_events(workspace_id, entity_type, entity_id, created_at);
            CREATE TABLE IF NOT EXISTS candidate_completeness_followups (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                application_id TEXT NOT NULL,
                property_id TEXT NOT NULL,
                missing_signature TEXT NOT NULL,
                missing_types_json TEXT NOT NULL,
                message_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(workspace_id, application_id, missing_signature),
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(application_id) REFERENCES owner_applications(id) ON DELETE CASCADE,
                FOREIGN KEY(property_id) REFERENCES properties(id) ON DELETE CASCADE,
                FOREIGN KEY(message_id) REFERENCES candidate_messages(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS candidate_followups_application_idx ON candidate_completeness_followups(application_id, created_at);
            CREATE TABLE IF NOT EXISTS inbound_application_attachments (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                inbound_message_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                application_document_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                FOREIGN KEY(inbound_message_id) REFERENCES inbound_application_messages(id) ON DELETE CASCADE,
                FOREIGN KEY(application_document_id) REFERENCES application_documents(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS inbound_attachments_message_idx ON inbound_application_attachments(inbound_message_id);
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

        for column, definition in (
            ("structure_type", "TEXT NOT NULL DEFAULT 'bien_individuel'"),
            ("description_publique", "TEXT NOT NULL DEFAULT ''"),
            ("statut", "TEXT NOT NULL DEFAULT 'preparation'"),
            ("date_disponibilite", "TEXT"),
            ("mode_detention", "TEXT NOT NULL DEFAULT 'nom_propre'"),
            ("adresse_exacte_visible", "INTEGER NOT NULL DEFAULT 0"),
            ("equipements_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("photos_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("tags_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("syndic_nom", "TEXT NOT NULL DEFAULT ''"),
            ("syndic_email", "TEXT NOT NULL DEFAULT ''"),
            ("syndic_telephone", "TEXT NOT NULL DEFAULT ''"),
            ("tantiemes_total", "REAL"),
            ("verification_policy", "TEXT NOT NULL DEFAULT 'standard'"),
        ):
            _ensure_column(connection, "properties", column, definition)
        for column, definition in (
            ("type_location", "TEXT NOT NULL DEFAULT 'non_precise'"),
            ("type_charges", "TEXT NOT NULL DEFAULT 'aucune'"),
            ("date_disponibilite", "TEXT"),
            ("revision_irl_active", "INTEGER NOT NULL DEFAULT 0"),
            ("indice_irl_reference", "TEXT NOT NULL DEFAULT ''"),
            ("date_revision", "TEXT"),
            ("dpe_classe", "TEXT NOT NULL DEFAULT 'inconnu'"),
            ("ges_classe", "TEXT NOT NULL DEFAULT 'inconnu'"),
            ("dpe_date", "TEXT"),
            ("chauffage", "TEXT NOT NULL DEFAULT ''"),
            ("eau_chaude", "TEXT NOT NULL DEFAULT ''"),
            ("ascenseur", "INTEGER NOT NULL DEFAULT 0"),
            ("accessibilite", "TEXT NOT NULL DEFAULT ''"),
            ("equipements_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("dependances_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("photos_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("tantiemes_generaux", "REAL"),
        ):
            _ensure_column(connection, "lots", column, definition)
        for column, definition in (
            ("verification_level", "TEXT NOT NULL DEFAULT 'non_verifie'"),
            ("anomalies_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("duplicate_of", "TEXT"),
            ("checked_at", "TEXT"),
            ("verification_engine_version", "TEXT NOT NULL DEFAULT ''"),
        ):
            _ensure_column(connection, "application_documents", column, definition)
        for column, definition in (
            ("statut_motif", "TEXT NOT NULL DEFAULT ''"),
            ("statut_source", "TEXT NOT NULL DEFAULT 'proprietaire'"),
        ):
            _ensure_column(connection, "owner_applications", column, definition)
        for column, definition in (
            ("attempts", "INTEGER NOT NULL DEFAULT 0"),
            ("sent_at", "TEXT"),
            ("last_error", "TEXT NOT NULL DEFAULT ''"),
        ):
            _ensure_column(connection, "candidate_messages", column, definition)

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
        for workspace in connection.execute("SELECT id FROM workspaces").fetchall():
            _provision_workspace_agents(connection, workspace[0])
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


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_object(value: object, *, label: str, maximum: int = 50_000) -> str:
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"{label} doit être un objet JSON valide.") from exc
    if len(encoded.encode("utf-8")) > maximum:
        raise HTTPException(status_code=422, detail=f"{label} est trop volumineux.")
    return encoded


def _agent_internal_auth(request: Request) -> None:
    """Authenticate the private agent worker without exposing a user session."""

    if not AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=503, detail="Le canal interne des agents n'est pas configuré.")
    received_token = request.headers.get("x-piaule-agent-token", "")
    if not hmac.compare_digest(received_token, AGENT_INTERNAL_TOKEN):
        raise HTTPException(status_code=401, detail="Jeton interne des agents invalide.")


def _agent_run_from_row(row: sqlite3.Row) -> AgentRun:
    return AgentRun(
        id=row["id"],
        workspace_id=row["workspace_id"],
        type_agent=row["agent_type"],
        mission=row["mission"],
        cible_type=row["target_type"],
        cible_id=row["target_id"],
        statut=row["status"],
        entree=json.loads(row["input_json"] or "{}"),
        sortie=json.loads(row["output_json"] or "{}"),
        preuves=json.loads(row["evidence_json"] or "[]"),
        erreur=row["error"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _action_from_row(row: sqlite3.Row) -> Action:
    return Action(
        id=row["id"],
        workspace_id=row["workspace_id"],
        agent_run_id=row["agent_run_id"],
        type_action=row["action_type"],
        libelle=row["label"],
        description=row["description"],
        niveau_risque=row["risk_level"],
        necessite_validation=bool(row["requires_approval"]),
        destinataire=row["recipient"],
        cible_type=row["target_type"],
        cible_id=row["target_id"],
        bien_id=row["property_id"],
        candidature_id=row["application_id"],
        payload=json.loads(row["payload_json"] or "{}"),
        empreinte_payload=row["payload_hash"],
        idempotency_key=row["idempotency_key"],
        statut=row["status"],
        expire_le=row["expires_at"],
        autorisee_le=row["approved_at"],
        executee_le=row["executed_at"],
        reference_execution=row["execution_reference"],
        dernier_motif=row["last_reason"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _audit_event_from_row(row: sqlite3.Row) -> AuditEvent:
    return AuditEvent(
        id=row["id"],
        workspace_id=row["workspace_id"],
        acteur_type=row["actor_type"],
        acteur_id=row["actor_id"],
        evenement=row["event_name"],
        entite_type=row["entity_type"],
        entite_id=row["entity_id"],
        bien_id=row["property_id"],
        candidature_id=row["application_id"],
        metadata=json.loads(row["metadata_json"] or "{}"),
        created_at=row["created_at"],
    )


def _record_audit_event(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    actor_type: str,
    actor_id: str,
    event_name: str,
    entity_type: str,
    entity_id: str,
    property_id: str | None = None,
    application_id: str | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO audit_events(
            id, workspace_id, actor_type, actor_id, event_name, entity_type,
            entity_id, property_id, application_id, metadata_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"audit-{uuid4().hex[:16]}",
            workspace_id,
            _clean_text(actor_type, 40),
            _clean_text(actor_id, 254),
            _clean_text(event_name, 120),
            _clean_text(entity_type, 80),
            _clean_text(entity_id, 160),
            property_id,
            application_id,
            _json_object(metadata or {}, label="Les métadonnées d'audit", maximum=20_000),
            _iso_now(),
        ),
    )


def _validate_action_scope(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    property_id: str | None,
    application_id: str | None,
) -> None:
    if property_id:
        property_row = connection.execute(
            "SELECT id FROM properties WHERE id = ? AND workspace_id = ?",
            (property_id, workspace_id),
        ).fetchone()
        if property_row is None:
            raise HTTPException(status_code=404, detail="Le bien de l'action est introuvable dans ce workspace.")
    if application_id:
        application_row = connection.execute(
            "SELECT property_id FROM owner_applications WHERE id = ? AND workspace_id = ?",
            (application_id, workspace_id),
        ).fetchone()
        if application_row is None:
            raise HTTPException(status_code=404, detail="La candidature de l'action est introuvable dans ce workspace.")
        if property_id and application_row["property_id"] != property_id:
            raise HTTPException(status_code=422, detail="Le bien et la candidature de l'action ne correspondent pas.")


def _action_expired(row: sqlite3.Row) -> bool:
    expires_at = row["expires_at"]
    if not expires_at:
        return False
    try:
        return datetime.fromisoformat(expires_at.replace("Z", "+00:00")) <= datetime.now(timezone.utc)
    except ValueError:
        return True


def _enforce_agent_scope(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    payload: ActionCreate,
    actor_id: str,
) -> None:
    """Reject an action that is outside the role of the agent that proposed it."""

    if not payload.agent_run_id:
        # Calls without a run are reserved for the trusted orchestration
        # worker. A named agent must always be attached to a mission.
        return
    run = connection.execute(
        "SELECT id, agent_type, status FROM agent_runs WHERE id = ? AND workspace_id = ?",
        (payload.agent_run_id, workspace_id),
    ).fetchone()
    if run is None:
        raise HTTPException(status_code=404, detail="La mission d'agent est introuvable dans ce workspace.")
    if run["status"] in {"completed", "failed", "cancelled"}:
        raise HTTPException(status_code=409, detail="Une mission terminée ne peut plus produire d'action.")
    allowed_actions = AGENT_SCOPE_POLICIES.get(run["agent_type"], set())
    if payload.type_action in allowed_actions:
        return
    _record_audit_event(
        connection,
        workspace_id=workspace_id,
        actor_type="system",
        actor_id="agent-guard",
        event_name="agent_action_bloquee",
        entity_type="agent_run",
        entity_id=run["id"],
        property_id=payload.bien_id,
        application_id=payload.candidature_id,
        metadata={
            "agent_type": run["agent_type"],
            "action_demandee": payload.type_action,
            "actions_autorisees": sorted(allowed_actions),
            "acteur": actor_id,
            "motif": "Action hors périmètre de l'agent.",
        },
    )
    connection.commit()
    raise HTTPException(
        status_code=403,
        detail=f"L'action '{payload.type_action}' est hors du périmètre de {run['agent_type']}.",
    )


def _create_agent_action(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    payload: ActionCreate,
    actor_type: str,
    actor_id: str,
) -> tuple[sqlite3.Row, bool]:
    _enforce_agent_scope(
        connection,
        workspace_id=workspace_id,
        payload=payload,
        actor_id=actor_id,
    )
    _validate_action_scope(
        connection,
        workspace_id=workspace_id,
        property_id=payload.bien_id,
        application_id=payload.candidature_id,
    )
    if payload.agent_run_id:
        run = connection.execute(
            "SELECT id FROM agent_runs WHERE id = ? AND workspace_id = ?",
            (payload.agent_run_id, workspace_id),
        ).fetchone()
        if run is None:
            raise HTTPException(status_code=404, detail="La mission d'agent est introuvable dans ce workspace.")
    payload_json = _json_object(payload.payload, label="Le contenu de l'action")
    payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    existing = connection.execute(
        "SELECT * FROM actions WHERE workspace_id = ? AND idempotency_key = ?",
        (workspace_id, _clean_text(payload.idempotency_key, 180)),
    ).fetchone()
    if existing is not None:
        if existing["payload_hash"] != payload_hash or existing["action_type"] != payload.type_action:
            raise HTTPException(status_code=409, detail="Cette clé d'idempotence désigne déjà une autre action.")
        return existing, False

    requires_approval = payload.niveau_risque not in {"lecture", "brouillon"}
    action_status = "a_valider" if requires_approval else "proposee"
    now = _iso_now()
    action_id = f"action-{uuid4().hex[:16]}"
    connection.execute(
        """
        INSERT INTO actions(
            id, workspace_id, agent_run_id, action_type, label, description,
            risk_level, requires_approval, recipient, target_type, target_id,
            property_id, application_id, payload_json, payload_hash,
            idempotency_key, status, expires_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            action_id,
            workspace_id,
            payload.agent_run_id,
            _clean_text(payload.type_action, 120),
            _clean_text(payload.libelle, 240),
            _clean_text(payload.description, 4000),
            payload.niveau_risque,
            int(requires_approval),
            _clean_text(payload.destinataire, 500),
            _clean_text(payload.cible_type, 80),
            _clean_text(payload.cible_id, 160),
            payload.bien_id,
            payload.candidature_id,
            payload_json,
            payload_hash,
            _clean_text(payload.idempotency_key, 180),
            action_status,
            payload.expire_le,
            now,
            now,
        ),
    )
    _record_audit_event(
        connection,
        workspace_id=workspace_id,
        actor_type=actor_type,
        actor_id=actor_id,
        event_name="action_proposee",
        entity_type="action",
        entity_id=action_id,
        property_id=payload.bien_id,
        application_id=payload.candidature_id,
        metadata={
            "type_action": payload.type_action,
            "niveau_risque": payload.niveau_risque,
            "necessite_validation": requires_approval,
            "empreinte_payload": payload_hash,
        },
    )
    return connection.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone(), True


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


def _provision_workspace_agents(connection: sqlite3.Connection, workspace_id: str) -> None:
    """Create the standard owner team once, without sharing instances across owners."""

    now = _iso_now()
    for role_key, definition in OWNER_AGENT_CATALOG.items():
        connection.execute(
            """
            INSERT OR IGNORE INTO workspace_agents(
                id, workspace_id, role_key, display_name, description, mission,
                status, is_primary, policy_version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, 'v1', ?, ?)
            """,
            (
                f"agent-{uuid4().hex[:16]}",
                workspace_id,
                role_key,
                str(definition["nom"]),
                str(definition["description"]),
                str(definition["mission"]),
                1 if definition["principal"] else 0,
                now,
                now,
            ),
        )


def _owner_agent_from_row(row: sqlite3.Row) -> OwnerAgent:
    return OwnerAgent(
        id=row["id"],
        workspace_id=row["workspace_id"],
        role=row["role_key"],
        nom=row["display_name"],
        description=row["description"],
        mission=row["mission"],
        statut=row["status"],
        principal=bool(row["is_primary"]),
        version_politique=row["policy_version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _owner_agent_message_from_row(row: sqlite3.Row) -> OwnerAgentMessage:
    return OwnerAgentMessage(
        id=row["id"],
        workspace_id=row["workspace_id"],
        agent_id=row["agent_id"],
        agent_role=row["role_key"],
        direction=row["direction"],
        contenu=row["content"],
        statut=row["status"],
        run_id=row["agent_run_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


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
            _provision_workspace_agents(connection, workspace_id)
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
        _provision_workspace_agents(connection, workspace_id)
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
        structure=row["structure_type"],
        adresse_ligne1=row["adresse_ligne1"],
        adresse_ligne2=row["adresse_ligne2"],
        code_postal=row["code_postal"],
        ville=row["ville"],
        pays=row["pays"],
        description=row["description"],
        description_publique=row["description_publique"],
        statut=row["statut"],
        date_disponibilite=date.fromisoformat(row["date_disponibilite"]) if row["date_disponibilite"] else None,
        mode_detention=row["mode_detention"],
        adresse_exacte_visible=bool(row["adresse_exacte_visible"]),
        equipements=json.loads(row["equipements_json"] or "[]"),
        photos=json.loads(row["photos_json"] or "[]"),
        tags=json.loads(row["tags_json"] or "[]"),
        syndic_nom=row["syndic_nom"],
        syndic_email=row["syndic_email"],
        syndic_telephone=row["syndic_telephone"],
        tantiemes_total=row["tantiemes_total"],
        politique_verification=row["verification_policy"],
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
        type_location=row["type_location"],
        etage=row["etage"],
        surface_m2=row["surface_m2"],
        pieces=row["pieces"],
        chambres=row["chambres"],
        loyer_mensuel_eur=row["loyer_mensuel_eur"],
        charges_mensuelles_eur=row["charges_mensuelles_eur"],
        type_charges=row["type_charges"],
        depot_garantie_eur=row["depot_garantie_eur"],
        date_disponibilite=date.fromisoformat(row["date_disponibilite"]) if row["date_disponibilite"] else None,
        revision_irl_active=bool(row["revision_irl_active"]),
        indice_irl_reference=row["indice_irl_reference"],
        date_revision=date.fromisoformat(row["date_revision"]) if row["date_revision"] else None,
        dpe_classe=row["dpe_classe"],
        ges_classe=row["ges_classe"],
        dpe_date=date.fromisoformat(row["dpe_date"]) if row["dpe_date"] else None,
        chauffage=row["chauffage"],
        eau_chaude=row["eau_chaude"],
        ascenseur=bool(row["ascenseur"]),
        accessibilite=row["accessibilite"],
        equipements=json.loads(row["equipements_json"] or "[]"),
        dependances=json.loads(row["dependances_json"] or "[]"),
        photos=json.loads(row["photos_json"] or "[]"),
        tantiemes_generaux=row["tantiemes_generaux"],
        statut=row["statut"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _property_record_from_row(row: sqlite3.Row) -> PropertyRecord:
    return PropertyRecord(
        id=row["id"],
        workspace_id=row["workspace_id"],
        bien_id=row["property_id"],
        lot_id=row["lot_id"],
        type=row["record_type"],
        titre=row["titre"],
        fournisseur=row["fournisseur"],
        reference=row["reference"],
        date_etablissement=date.fromisoformat(row["date_etablissement"]) if row["date_etablissement"] else None,
        date_expiration=date.fromisoformat(row["date_expiration"]) if row["date_expiration"] else None,
        statut=row["statut"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _application_from_row(row: sqlite3.Row) -> OwnerApplication:
    return OwnerApplication(
        id=row["id"],
        workspace_id=row["workspace_id"],
        bien_id=row["property_id"],
        bien_nom=row["bien_nom"],
        lot_id=row["lot_id"],
        lot_identifiant=row["lot_identifiant"],
        candidat_prenom=row["candidat_prenom"],
        candidat_nom=row["candidat_nom"],
        candidat_email=row["candidat_email"],
        candidat_telephone=row["candidat_telephone"],
        source=row["source"],
        reference_source=row["reference_source"],
        statut=row["statut"],
        statut_motif=row["statut_motif"],
        statut_source=row["statut_source"],
        doublon_possible=bool(row["doublon_possible"]),
        notes_privees=row["notes_privees"],
        recue_le=row["recue_le"],
        updated_at=row["updated_at"],
    )


def _parse_visit_datetime(value: str, field_name: str) -> str:
    """Normalize an ISO datetime and require an explicit timezone."""

    candidate = _clean_text(value, 80).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} doit être une date ISO 8601 valide avec fuseau horaire.",
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} doit contenir un fuseau horaire explicite.",
        )
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _visit_slot_from_row(row: sqlite3.Row) -> VisitSlot:
    return VisitSlot(
        id=row["id"],
        workspace_id=row["workspace_id"],
        bien_id=row["property_id"],
        lot_id=row["lot_id"],
        debut=row["starts_at"],
        fin=row["ends_at"],
        fuseau=row["timezone"],
        mode=row["mode"],
        note=row["note"],
        statut=row["status"],
        created_at=row["created_at"],
    )


def _visit_from_row(row: sqlite3.Row) -> Visit:
    return Visit(
        id=row["id"],
        workspace_id=row["workspace_id"],
        bien_id=row["property_id"],
        bien_nom=row["bien_nom"],
        lot_id=row["lot_id"],
        lot_identifiant=row["lot_identifiant"],
        candidature_id=row["application_id"],
        candidat_prenom=row["candidat_prenom"],
        candidat_nom=row["candidat_nom"],
        slot_id=row["slot_id"],
        debut=row["starts_at"],
        fin=row["ends_at"],
        fuseau=row["timezone"],
        mode=row["mode"],
        statut=row["status"],
        source=row["source"],
        note=row["note"],
        motif=row["reason"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _candidate_visit_from_row(row: sqlite3.Row) -> CandidateVisit:
    return CandidateVisit(
        id=row["id"],
        bien_nom=row["bien_nom"],
        lot_identifiant=row["lot_identifiant"],
        debut=row["starts_at"],
        fin=row["ends_at"],
        fuseau=row["timezone"],
        mode=row["mode"],
        statut=row["status"],
        note=row["note"],
        motif=row["reason"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _visit_query() -> str:
    return """
        SELECT v.*, p.nom AS bien_nom, l.identifiant AS lot_identifiant,
               a.candidat_prenom, a.candidat_nom,
               s.starts_at, s.ends_at, s.timezone, s.mode
        FROM visits v
        JOIN properties p ON p.id = v.property_id
        LEFT JOIN lots l ON l.id = v.lot_id
        JOIN owner_applications a ON a.id = v.application_id
        JOIN visit_slots s ON s.id = v.slot_id
    """


def _owned_visit_row(
    connection: sqlite3.Connection, owner: Candidate, property_id: str, visit_id: str
) -> sqlite3.Row:
    row = connection.execute(
        _visit_query()
        + " WHERE v.id = ? AND v.property_id = ? AND v.workspace_id = ?",
        (visit_id, property_id, owner.workspace_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Visite introuvable dans ce bien.")
    return row


def _active_visit_statuses() -> tuple[str, ...]:
    return ("proposee", "confirmee")


def _application_query() -> str:
    return """
        SELECT a.*, p.nom AS bien_nom, l.identifiant AS lot_identifiant
        FROM owner_applications a
        JOIN properties p ON p.id = a.property_id
        LEFT JOIN lots l ON l.id = a.lot_id
    """


def _owned_application_row(
    connection: sqlite3.Connection, owner: Candidate, application_id: str
) -> sqlite3.Row:
    row = connection.execute(
        _application_query() + " WHERE a.id = ? AND a.workspace_id = ?",
        (application_id, owner.workspace_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Candidature introuvable dans ce workspace.")
    return row


def _record_application_status_event(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    application_id: str,
    property_id: str,
    previous_status: str,
    new_status: str,
    source: str,
    reason: str = "",
) -> None:
    connection.execute(
        """
        INSERT INTO application_status_history(
            id, workspace_id, application_id, property_id, previous_status,
            new_status, source, reason, metadata_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}', datetime('now'))
        """,
        (
            f"application-status-{uuid4().hex[:16]}",
            workspace_id,
            application_id,
            property_id,
            previous_status,
            new_status,
            source,
            _clean_text(reason, 1000),
        ),
    )


def _set_application_status(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    application_id: str,
    new_status: str,
    source: str,
    reason: str = "",
) -> sqlite3.Row:
    if new_status not in APPLICATION_STATUS_VALUES:
        raise HTTPException(status_code=422, detail="Statut de candidature inconnu.")
    current = connection.execute(
        """
        SELECT id, workspace_id, property_id, statut
        FROM owner_applications
        WHERE id = ? AND workspace_id = ?
        """,
        (application_id, workspace_id),
    ).fetchone()
    if current is None:
        raise HTTPException(status_code=404, detail="Candidature introuvable.")
    previous_status = current["statut"]
    if previous_status == new_status:
        if reason:
            connection.execute(
                """
                UPDATE owner_applications
                SET statut_motif = ?, statut_source = ?, updated_at = datetime('now')
                WHERE id = ? AND workspace_id = ?
                """,
                (_clean_text(reason, 1000), source, application_id, workspace_id),
            )
        return connection.execute(
            "SELECT * FROM owner_applications WHERE id = ? AND workspace_id = ?",
            (application_id, workspace_id),
        ).fetchone()
    allowed = APPLICATION_STATUS_TRANSITIONS.get(previous_status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Transition impossible : {previous_status} vers {new_status}.",
        )
    if new_status in APPLICATION_READY_STATUSES:
        completeness = _application_completeness(connection, workspace_id, application_id)
        if completeness.statut != "complet":
            raise HTTPException(
                status_code=409,
                detail="Cette candidature doit être complète avant de passer à cette étape.",
            )
    clean_reason = _clean_text(reason, 1000)
    connection.execute(
        """
        UPDATE owner_applications
        SET statut = ?, statut_motif = ?, statut_source = ?, updated_at = datetime('now')
        WHERE id = ? AND workspace_id = ?
        """,
        (new_status, clean_reason, source, application_id, workspace_id),
    )
    _record_application_status_event(
        connection,
        workspace_id=workspace_id,
        application_id=application_id,
        property_id=current["property_id"],
        previous_status=previous_status,
        new_status=new_status,
        source=source,
        reason=clean_reason,
    )
    return connection.execute(
        "SELECT * FROM owner_applications WHERE id = ? AND workspace_id = ?",
        (application_id, workspace_id),
    ).fetchone()


def _application_status_event_from_row(row: sqlite3.Row) -> ApplicationStatusEvent:
    return ApplicationStatusEvent(
        id=row["id"],
        candidature_id=row["application_id"],
        ancien_statut=row["previous_status"],
        nouveau_statut=row["new_status"],
        source=row["source"],
        motif=row["reason"],
        created_at=row["created_at"],
    )


def _clean_application_create(payload: OwnerApplicationCreate) -> OwnerApplicationCreate:
    email = _normalise_email(payload.candidat_email) if payload.candidat_email else ""
    if email and not EMAIL_RE.fullmatch(email):
        raise HTTPException(status_code=400, detail="L'adresse e-mail du candidat est invalide.")
    return OwnerApplicationCreate(
        lot_id=_clean_text(payload.lot_id, 80) if payload.lot_id else None,
        candidat_prenom=_clean_text(payload.candidat_prenom, 80),
        candidat_nom=_clean_text(payload.candidat_nom, 120),
        candidat_email=email,
        candidat_telephone=_clean_text(payload.candidat_telephone, 30),
        source=payload.source,
        reference_source=_clean_text(payload.reference_source, 160),
        statut=payload.statut,
        notes_privees=_clean_text(payload.notes_privees, 3000),
    )


def _clean_application_update(payload: OwnerApplicationUpdate) -> OwnerApplicationUpdate:
    email = _normalise_email(payload.candidat_email) if payload.candidat_email else payload.candidat_email
    if email and not EMAIL_RE.fullmatch(email):
        raise HTTPException(status_code=400, detail="L'adresse e-mail du candidat est invalide.")
    return OwnerApplicationUpdate(
        lot_id=_clean_text(payload.lot_id, 80) if payload.lot_id else payload.lot_id,
        candidat_prenom=_clean_text(payload.candidat_prenom, 80) if payload.candidat_prenom else payload.candidat_prenom,
        candidat_nom=_clean_text(payload.candidat_nom, 120) if payload.candidat_nom else payload.candidat_nom,
        candidat_email=email,
        candidat_telephone=_clean_text(payload.candidat_telephone, 30) if payload.candidat_telephone else payload.candidat_telephone,
        source=payload.source,
        reference_source=_clean_text(payload.reference_source, 160) if payload.reference_source else payload.reference_source,
        statut=payload.statut,
        notes_privees=_clean_text(payload.notes_privees, 3000) if payload.notes_privees else payload.notes_privees,
    )


def _application_duplicate_key(property_id: str, lot_id: str | None, email: str) -> str:
    if not email:
        return ""
    return "|".join((property_id, lot_id or "", email))


def _application_channel_from_row(row: sqlite3.Row) -> ApplicationChannel:
    return ApplicationChannel(
        id=row["id"],
        workspace_id=row["workspace_id"],
        bien_id=row["property_id"],
        lot_id=row["lot_id"],
        canal=row["canal"],
        libelle=row["libelle"],
        adresse_reception=row["adresse_reception"],
        actif=bool(row["actif"]),
        created_at=row["created_at"],
    )


def _inbound_message_from_row(row: sqlite3.Row) -> InboundApplicationMessage:
    return InboundApplicationMessage(
        id=row["id"],
        workspace_id=row["workspace_id"],
        canal_id=row["channel_id"],
        bien_id=row["property_id"],
        lot_id=row["lot_id"],
        adresse_reception=row["adresse_reception"],
        message_id=row["message_id"],
        expediteur_email=row["expediteur_email"],
        objet=row["objet"],
        contenu_texte=row["contenu_texte"],
        pieces_jointes=json.loads(row["pieces_jointes_json"] or "[]"),
        statut=row["statut"],
        candidature_id=row["application_id"],
        recu_le=row["recu_le"],
    )


def _dossier_facile_connection_from_row(row: sqlite3.Row) -> DossierFacileConnection:
    return DossierFacileConnection(
        id=row["id"],
        workspace_id=row["workspace_id"],
        candidature_id=row["application_id"],
        statut=row["statut"],
        statut_dossier=row["statut_dossier"],
        evenement=row["evenement"],
        tenant_id=row["tenant_id"],
        resume=json.loads(row["resume_json"] or "{}"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _dossier_facile_is_configured() -> bool:
    return DOSSIER_FACILE_ENABLED and all(
        (
            DOSSIER_FACILE_CLIENT_ID,
            DOSSIER_FACILE_CLIENT_SECRET,
            DOSSIER_FACILE_AUTH_URL,
            DOSSIER_FACILE_TOKEN_URL,
            DOSSIER_FACILE_PROFILE_URL,
            DOSSIER_FACILE_REDIRECT_URI,
        )
    )


def _dossier_facile_http_json(
    request: URLRequest, *, error_message: str, timeout: int = 15
) -> dict[str, object]:
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=error_message) from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail=error_message)
    return payload


def _dossier_facile_exchange_code(code: str) -> dict[str, object]:
    credentials = base64.b64encode(
        f"{DOSSIER_FACILE_CLIENT_ID}:{DOSSIER_FACILE_CLIENT_SECRET}".encode("utf-8")
    ).decode("ascii")
    body = urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": DOSSIER_FACILE_REDIRECT_URI,
            "client_id": DOSSIER_FACILE_CLIENT_ID,
        }
    ).encode("utf-8")
    request = URLRequest(
        DOSSIER_FACILE_TOKEN_URL,
        data=body,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    return _dossier_facile_http_json(
        request,
        error_message="DossierFacile n'a pas accepté la connexion du candidat.",
    )


def _dossier_facile_fetch_profile(access_token: str) -> dict[str, object]:
    request = URLRequest(
        DOSSIER_FACILE_PROFILE_URL,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        method="GET",
    )
    return _dossier_facile_http_json(
        request,
        error_message="Le profil DossierFacile n'a pas pu être récupéré.",
    )


def _dossier_facile_summary(payload: dict[str, object]) -> tuple[str, str, dict[str, object]]:
    apartment = payload.get("apartmentSharing")
    apartment_data = apartment if isinstance(apartment, dict) else {}
    raw_status = payload.get("status") or apartment_data.get("status") or ""
    dossier_status = str(raw_status).strip().upper()
    tenant_id = payload.get("tenantId") or payload.get("tenant_id") or payload.get("id") or ""
    documents = payload.get("documents")
    document_statuses: list[str] = []
    if isinstance(documents, list):
        for document in documents:
            if isinstance(document, dict) and document.get("status"):
                document_statuses.append(str(document["status"]).upper())
    if dossier_status in {"VALIDATED", "VERIFIED", "VERIFIED_ACCOUNT"}:
        connection_status = "verifiee"
    elif dossier_status in {"DECLINED", "DENIED", "DENIED_ACCOUNT"}:
        connection_status = "refusee"
    elif dossier_status in {"INCOMPLETE", "ARCHIVED_ACCOUNT"}:
        connection_status = "a_completer"
    else:
        connection_status = "connectee"
    summary: dict[str, object] = {
        "statut_dossier": dossier_status,
        "documents_total": len(document_statuses),
        "documents_statuts": document_statuses,
    }
    return connection_status, str(tenant_id), summary


def _dossier_facile_connection_for_owner(
    connection: sqlite3.Connection, owner: Candidate, application_id: str
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT * FROM dossier_facile_connections
        WHERE application_id = ? AND workspace_id = ?
        ORDER BY created_at DESC LIMIT 1
        """,
        (application_id, owner.workspace_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Aucune connexion DossierFacile pour cette candidature.")
    return row


def _application_document_from_row(row: sqlite3.Row) -> ApplicationDocument:
    return ApplicationDocument(
        id=row["id"],
        workspace_id=row["workspace_id"],
        candidature_id=row["application_id"],
        bien_id=row["property_id"],
        type=row["document_type"],
        nom=row["nom"],
        filename=row["original_filename"],
        content_type=row["content_type"],
        size_bytes=row["size_bytes"],
        empreinte_sha256=row["sha256"],
        provenance=row["provenance"],
        statut=row["statut"],
        niveau_verification=row["verification_level"],
        anomalies=json.loads(row["anomalies_json"] or "[]"),
        doublon_de=row["duplicate_of"],
        derniere_verification=row["checked_at"],
        date_expiration=row["date_expiration"],
        note_verification=row["note_verification"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _application_document_check_from_row(row: sqlite3.Row) -> ApplicationDocumentCheck:
    return ApplicationDocumentCheck(
        id=row["id"],
        document_id=row["document_id"],
        resultat=row["result"],
        controles=json.loads(row["checks_json"] or "{}"),
        anomalies=json.loads(row["anomalies_json"] or "[]"),
        version_moteur=row["engine_version"],
        created_at=row["created_at"],
    )


def _application_verification_request_from_row(row: sqlite3.Row) -> ApplicationVerificationRequest:
    return ApplicationVerificationRequest(
        id=row["id"],
        candidature_id=row["application_id"],
        document_id=row["document_id"],
        source=row["source"],
        statut=row["status"],
        motif=row["motif"],
        consentement_requis=row["source"] != "revue_humaine",
        consentement_donne_le=row["consent_given_at"],
        preuve=json.loads(row["evidence_json"] or "{}"),
        resultat=row["result_summary"],
        expire_le=row["expires_at"],
        cree_le=row["created_at"],
        mis_a_jour_le=row["updated_at"],
    )


def _candidate_message_from_row(row: sqlite3.Row) -> CandidateMessage:
    return CandidateMessage(
        id=row["id"],
        candidature_id=row["application_id"],
        direction=row["direction"],
        sujet=row["sujet"],
        contenu=row["contenu"],
        source=row["source"],
        statut=row["statut"],
        created_at=row["created_at"],
    )


def _candidate_followup_from_row(
    row: sqlite3.Row, *, status: str | None = None, link: str | None = None
) -> CandidateCompletenessFollowUp:
    return CandidateCompletenessFollowUp(
        id=row["id"],
        candidature_id=row["application_id"],
        pieces_demandees=json.loads(row["missing_types_json"] or "[]"),
        message_id=row["message_id"] or None,
        lien_depot=link,
        statut=status or "deja_preparee",
        created_at=row["created_at"],
    )


def _candidate_access_url(token: str) -> str:
    if not CANDIDATE_PORTAL_BASE_URL:
        raise HTTPException(status_code=503, detail="Le portail candidat n'est pas configuré.")
    separator = "&" if "?" in CANDIDATE_PORTAL_BASE_URL else "?"
    return f"{CANDIDATE_PORTAL_BASE_URL}{separator}{urlencode({'access': token})}"


def _issue_candidate_access_link(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    application_id: str,
    property_id: str,
) -> tuple[str, str, int]:
    """Issue one revocable candidate link and return id, raw token and expiry."""

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = time.time() + CANDIDATE_LINK_SECONDS
    link_id = f"candidate-link-{uuid4().hex[:16]}"
    connection.execute(
        "UPDATE candidate_access_links SET active = 0 WHERE application_id = ? AND workspace_id = ? AND active = 1",
        (application_id, workspace_id),
    )
    connection.execute(
        """
        INSERT INTO candidate_access_links(
            id, workspace_id, application_id, property_id, token_hash,
            expires_at, active, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 1, datetime('now'))
        """,
        (link_id, workspace_id, application_id, property_id, token_hash, expires_at),
    )
    return link_id, token, int(expires_at)


def _active_candidate_access_row(token: str) -> sqlite3.Row:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with closing(_connect()) as connection:
        row = connection.execute(
            """
            SELECT l.*, a.candidat_prenom, a.candidat_email, a.statut AS candidature_statut,
                   p.nom AS bien_nom
            FROM candidate_access_links l
            JOIN owner_applications a ON a.id = l.application_id
            JOIN properties p ON p.id = l.property_id
            WHERE l.token_hash = ? AND l.active = 1 AND l.expires_at > ?
            """,
            (token_hash, time.time()),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Ce lien candidat est invalide ou expiré.")
    return row


def _owned_application_document_row(
    connection: sqlite3.Connection,
    owner: Candidate,
    property_id: str,
    application_id: str,
    document_id: str,
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT * FROM application_documents
        WHERE id = ? AND workspace_id = ? AND property_id = ? AND application_id = ?
        """,
        (document_id, owner.workspace_id, property_id, application_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Pièce de candidature introuvable.")
    return row


REQUIRED_APPLICATION_DOCUMENT_TYPES: tuple[ApplicationDocumentType, ...] = (
    "identite",
    "domicile",
    "situation_professionnelle",
    "ressources",
    "imposition",
)

DOCUMENT_TYPE_LABELS: dict[ApplicationDocumentType, str] = {
    "identite": "pièce d'identité",
    "domicile": "justificatif de domicile",
    "situation_professionnelle": "justificatif de situation professionnelle",
    "ressources": "justificatif de ressources",
    "imposition": "avis d'imposition",
    "garant": "pièce du garant",
    "autre": "document complémentaire",
}
DOCUMENT_VERIFICATION_ENGINE_VERSION = "technical-v1"
DOCUMENT_TYPE_FILENAME_HINTS: dict[str, tuple[str, ...]] = {
    "identite": ("identite", "passeport", "cni", "permis", "sejour", "resident"),
    "domicile": ("domicile", "quittance", "hebergement", "heberge", "propriete", "taxe_fonciere"),
    "situation_professionnelle": ("contrat", "travail", "employeur", "attestation", "scolarite", "etudiant", "kbis"),
    "ressources": ("salaire", "paie", "bulletin", "revenus", "pension", "bourse", "caf"),
    "imposition": ("impot", "imposition", "fiscal", "avis"),
    "garant": ("garant", "caution"),
}


def _normalise_document_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")


def _document_type_filename_hints(filename: str) -> set[str]:
    normalized = _normalise_document_name(filename)
    return {
        document_type
        for document_type, hints in DOCUMENT_TYPE_FILENAME_HINTS.items()
        if any(hint in normalized for hint in hints)
    }


def _document_preflight(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
) -> tuple[sqlite3.Row, sqlite3.Row]:
    """Run safe local checks without claiming authenticity or identity verification."""

    checks: dict[str, str] = {}
    anomalies: list[str] = []
    path = UPLOAD_DIRECTORY / row["stored_filename"]
    expected_extension = Path(row["original_filename"]).suffix.lower().lstrip(".")
    actual_size = path.stat().st_size if path.exists() else -1
    checks["fichier_present"] = "oui" if path.exists() else "non"
    checks["taille"] = "coherente" if actual_size == row["size_bytes"] else "incoherente"
    if actual_size < 0:
        anomalies.append("fichier_absent_du_stockage")
    elif actual_size != row["size_bytes"]:
        anomalies.append("taille_stockee_incoherente")

    allowed_content_types = ALLOWED_DOCUMENT_TYPES.get(expected_extension, set())
    checks["extension"] = "supportee" if expected_extension in ALLOWED_DOCUMENT_TYPES else "inconnue"
    checks["mime"] = "coherent" if row["content_type"] in allowed_content_types else "incoherent"
    if expected_extension not in ALLOWED_DOCUMENT_TYPES:
        anomalies.append("extension_non_supportee")
    elif row["content_type"] not in allowed_content_types:
        anomalies.append("type_mime_incoherent")

    signature = b""
    if path.exists():
        with path.open("rb") as document_file:
            signature = document_file.read(16)
    signature_ok = (
        (expected_extension == "pdf" and signature.startswith(b"%PDF-"))
        or (expected_extension in {"jpg", "jpeg"} and signature.startswith(b"\xff\xd8\xff"))
        or (expected_extension == "png" and signature.startswith(b"\x89PNG\r\n\x1a\n"))
    )
    checks["signature_fichier"] = "coherente" if signature_ok else "incoherente"
    if not signature_ok:
        anomalies.append("signature_fichier_incoherente")

    hints = _document_type_filename_hints(row["original_filename"])
    declared_type = row["document_type"]
    checks["type_declare"] = declared_type
    checks["type_attendu"] = "requis" if declared_type in REQUIRED_APPLICATION_DOCUMENT_TYPES else "optionnel"
    if hints and declared_type not in hints:
        checks["type_nom_fichier"] = "probablement_incoherent"
        anomalies.append("type_probable_incompatible_avec_le_nom")
    else:
        checks["type_nom_fichier"] = "compatible_ou_non_concluant"

    expiration_status = "absente"
    if row["date_expiration"]:
        try:
            expiration_status = "expiree" if row["date_expiration"] < date.today().isoformat() else "valide"
        except TypeError:
            expiration_status = "invalide"
            anomalies.append("date_expiration_invalide")
    checks["expiration"] = expiration_status
    if expiration_status == "expiree":
        anomalies.append("document_expire")

    duplicate = connection.execute(
        """
        SELECT id FROM application_documents
        WHERE workspace_id = ? AND application_id = ? AND sha256 = ? AND id <> ?
        ORDER BY created_at, id LIMIT 1
        """,
        (row["workspace_id"], row["application_id"], row["sha256"], row["id"]),
    ).fetchone()
    checks["doublon"] = "oui" if duplicate else "non"
    if duplicate:
        anomalies.append("doublon_dans_le_dossier")

    # A local check cannot prove that a file was issued by an administration.
    checks["authenticite"] = "non_verifiable_localement"
    checks["coherence_identite_revenus"] = "non_verifiee_sans_extraction"
    checks["niveau_de_confiance"] = "controle_technique_uniquement"

    hard_anomalies = {
        "fichier_absent_du_stockage",
        "taille_stockee_incoherente",
        "extension_non_supportee",
        "type_mime_incoherent",
        "signature_fichier_incoherente",
        "date_expiration_invalide",
    }
    attention_anomalies = {"document_expire", "doublon_dans_le_dossier", "type_probable_incompatible_avec_le_nom"}
    if any(item in hard_anomalies for item in anomalies):
        result = "bloque"
        new_status = "a_corriger"
    elif any(item in attention_anomalies for item in anomalies):
        result = "attention"
        new_status = "expire" if "document_expire" in anomalies else "a_corriger"
    else:
        result = "ok_technique"
        new_status = "en_verification"

    previous_level = row["verification_level"]
    if not anomalies and previous_level in {"revue_humaine", "source_partenaire", "source_officielle"}:
        new_status = row["statut"]
        verification_level = previous_level
    else:
        verification_level = "controles_techniques"
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    connection.execute(
        """
        UPDATE application_documents
        SET statut = ?, verification_level = ?, anomalies_json = ?, duplicate_of = ?,
            checked_at = ?, verification_engine_version = ?, updated_at = datetime('now')
        WHERE id = ? AND workspace_id = ?
        """,
        (
            new_status,
            verification_level,
            json.dumps(anomalies, ensure_ascii=False),
            duplicate["id"] if duplicate else None,
            now,
            DOCUMENT_VERIFICATION_ENGINE_VERSION,
            row["id"],
            row["workspace_id"],
        ),
    )
    check_id = f"document-check-{uuid4().hex[:16]}"
    connection.execute(
        """
        INSERT INTO application_document_checks(
            id, workspace_id, application_id, document_id, result,
            checks_json, anomalies_json, engine_version, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            check_id,
            row["workspace_id"],
            row["application_id"],
            row["id"],
            result,
            json.dumps(checks, ensure_ascii=False),
            json.dumps(anomalies, ensure_ascii=False),
            DOCUMENT_VERIFICATION_ENGINE_VERSION,
        ),
    )
    updated_row = connection.execute(
        "SELECT * FROM application_documents WHERE id = ? AND workspace_id = ?",
        (row["id"], row["workspace_id"]),
    ).fetchone()
    check_row = connection.execute(
        "SELECT * FROM application_document_checks WHERE id = ?",
        (check_id,),
    ).fetchone()
    return updated_row, check_row


def _completeness_followup_types(
    completeness: ApplicationCompleteness,
) -> list[ApplicationDocumentType]:
    """Return only categories the agent may safely request from a candidate."""

    requestable = {"manquante", "a_corriger", "expire", "refuse"}
    return [item.type for item in completeness.pieces_requises if item.statut in requestable]


def _application_completeness(
    connection: sqlite3.Connection, workspace_id: str, application_id: str
) -> ApplicationCompleteness:
    rows = connection.execute(
        """
        SELECT * FROM application_documents
        WHERE workspace_id = ? AND application_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (workspace_id, application_id),
    ).fetchall()
    latest_by_type: dict[str, sqlite3.Row] = {}
    for row in rows:
        latest_by_type.setdefault(row["document_type"], row)

    dossier_facile = connection.execute(
        """
        SELECT statut, statut_dossier FROM dossier_facile_connections
        WHERE workspace_id = ? AND application_id = ?
        ORDER BY updated_at DESC LIMIT 1
        """,
        (workspace_id, application_id),
    ).fetchone()
    dossier_facile_status = dossier_facile["statut"] if dossier_facile else ""
    if dossier_facile_status == "verifiee":
        items = [
            CompletenessItem(
                type=document_type,
                statut="verifiee_par_dossier_facile",
                source="dossier_facile",
                details="Catégorie couverte par un dossier DossierFacile vérifié.",
            )
            for document_type in REQUIRED_APPLICATION_DOCUMENT_TYPES
        ]
        return ApplicationCompleteness(
            candidature_id=application_id,
            statut="complet",
            score=100,
            pieces_requises=items,
            dossier_facile_statut=dossier_facile["statut_dossier"] or dossier_facile_status,
            mis_a_jour_le=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

    valid_count = 0
    pending = False
    items: list[CompletenessItem] = []
    today = date.today().isoformat()
    for document_type in REQUIRED_APPLICATION_DOCUMENT_TYPES:
        row = latest_by_type.get(document_type)
        if row is None:
            items.append(
                CompletenessItem(type=document_type, statut="manquante", details="Aucune pièce reçue.")
            )
            continue
        piece_status = row["statut"]
        details = row["note_verification"] or ""
        if piece_status == "valide" and row["date_expiration"] and row["date_expiration"] < today:
            piece_status = "expire"
            details = details or "La date d'expiration est dépassée."
        if piece_status == "valide":
            valid_count += 1
        if piece_status in {"recu", "en_verification"}:
            pending = True
        items.append(
            CompletenessItem(
                type=document_type,
                statut=piece_status,
                piece_id=row["id"],
                source=row["provenance"],
                details=details,
            )
        )
    if valid_count == len(REQUIRED_APPLICATION_DOCUMENT_TYPES):
        completeness_status = "complet"
    elif pending:
        completeness_status = "en_verification"
    else:
        completeness_status = "a_completer"
    return ApplicationCompleteness(
        candidature_id=application_id,
        statut=completeness_status,
        score=round(valid_count * 100 / len(REQUIRED_APPLICATION_DOCUMENT_TYPES)),
        pieces_requises=items,
        dossier_facile_statut=(dossier_facile["statut_dossier"] if dossier_facile else ""),
        mis_a_jour_le=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )


def _refresh_application_status(
    connection: sqlite3.Connection, workspace_id: str, application_id: str
) -> ApplicationCompleteness:
    completeness = _application_completeness(connection, workspace_id, application_id)
    new_status = {
        "complet": "prete",
        "en_verification": "en_verification",
        "a_completer": "a_completer",
    }[completeness.statut]
    current = connection.execute(
        "SELECT statut FROM owner_applications WHERE id = ? AND workspace_id = ?",
        (application_id, workspace_id),
    ).fetchone()
    if current is not None and current["statut"] in {"recue", "a_completer", "en_verification", "prete"}:
        _set_application_status(
            connection,
            workspace_id=workspace_id,
            application_id=application_id,
            new_status=new_status,
            source="systeme",
            reason=f"Complétude recalculée : {completeness.statut}.",
        )
    return completeness


def _owned_application_channel_row(
    connection: sqlite3.Connection, owner: Candidate, channel_id: str
) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM application_channels WHERE id = ? AND workspace_id = ?",
        (channel_id, owner.workspace_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Canal de candidature introuvable dans ce workspace.")
    return row


def _clean_application_channel(payload: ApplicationChannelCreate) -> ApplicationChannelCreate:
    return ApplicationChannelCreate(
        lot_id=_clean_text(payload.lot_id, 80) if payload.lot_id else None,
        canal=payload.canal,
        libelle=_clean_text(payload.libelle, 160),
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


def _clean_string_list(values: list[str], maximum_items: int = 30, maximum_length: int = 120) -> list[str]:
    cleaned: list[str] = []
    for value in values[:maximum_items]:
        item = _clean_text(value, maximum_length)
        if item and item not in cleaned:
            cleaned.append(item)
    return cleaned


def _clean_property_payload(payload: PropertyCreate) -> PropertyCreate:
    cleaned = PropertyCreate(
        nom=_clean_text(payload.nom, 120),
        type=payload.type,
        structure=payload.structure,
        adresse_ligne1=_clean_text(payload.adresse_ligne1, 160),
        adresse_ligne2=_clean_text(payload.adresse_ligne2, 160),
        code_postal=_clean_text(payload.code_postal, 20),
        ville=_clean_text(payload.ville, 100),
        pays=_clean_text(payload.pays, 80) or "France",
        description=_clean_text(payload.description, 2000),
        description_publique=_clean_text(payload.description_publique, 2000),
        statut=payload.statut,
        date_disponibilite=payload.date_disponibilite,
        mode_detention=payload.mode_detention,
        adresse_exacte_visible=payload.adresse_exacte_visible,
        equipements=_clean_string_list(payload.equipements),
        photos=_clean_string_list(payload.photos, maximum_length=500),
        tags=_clean_string_list(payload.tags, maximum_length=50),
        syndic_nom=_clean_text(payload.syndic_nom, 120),
        syndic_email=_normalise_email(payload.syndic_email) if payload.syndic_email else "",
        syndic_telephone=_clean_text(payload.syndic_telephone, 30),
        tantiemes_total=payload.tantiemes_total,
        politique_verification=payload.politique_verification,
    )
    if len(cleaned.nom) < 2 or len(cleaned.adresse_ligne1) < 3 or len(cleaned.ville) < 2:
        raise HTTPException(status_code=400, detail="Le nom, l'adresse et la ville sont obligatoires.")
    return cleaned


def _clean_lot_payload(payload: LotCreate) -> LotCreate:
    cleaned = LotCreate(
        identifiant=_clean_text(payload.identifiant, 80),
        type=payload.type,
        type_location=payload.type_location,
        etage=_clean_text(payload.etage, 30),
        surface_m2=payload.surface_m2,
        pieces=payload.pieces,
        chambres=payload.chambres,
        loyer_mensuel_eur=payload.loyer_mensuel_eur,
        charges_mensuelles_eur=payload.charges_mensuelles_eur,
        type_charges=payload.type_charges,
        depot_garantie_eur=payload.depot_garantie_eur,
        date_disponibilite=payload.date_disponibilite,
        revision_irl_active=payload.revision_irl_active,
        indice_irl_reference=_clean_text(payload.indice_irl_reference, 30),
        date_revision=payload.date_revision,
        dpe_classe=payload.dpe_classe,
        ges_classe=payload.ges_classe,
        dpe_date=payload.dpe_date,
        chauffage=_clean_text(payload.chauffage, 100),
        eau_chaude=_clean_text(payload.eau_chaude, 100),
        ascenseur=payload.ascenseur,
        accessibilite=_clean_text(payload.accessibilite, 300),
        equipements=_clean_string_list(payload.equipements),
        dependances=_clean_string_list(payload.dependances),
        photos=_clean_string_list(payload.photos, maximum_length=500),
        tantiemes_generaux=payload.tantiemes_generaux,
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


def _email_enabled() -> bool:
    return os.getenv("PIAULE_EMAIL_ENABLED", "false").strip().lower() == "true"


def _email_internal_token(request: Request) -> None:
    expected_token = os.getenv("PIAULE_EMAIL_INTERNAL_TOKEN", "").strip()
    received_token = request.headers.get("x-piaule-email-token", "")
    if not expected_token:
        raise HTTPException(status_code=503, detail="Le worker e-mail n'est pas configuré.")
    if not hmac.compare_digest(received_token, expected_token):
        raise HTTPException(status_code=401, detail="Jeton du worker e-mail invalide.")


def _smtp_settings() -> dict[str, object] | None:
    if not _email_enabled():
        return None
    host = os.getenv("PIAULE_SMTP_HOST", "").strip()
    username = os.getenv("PIAULE_SMTP_USERNAME", "").strip()
    password = os.getenv("PIAULE_SMTP_PASSWORD", "")
    sender = _normalise_email(os.getenv("PIAULE_SMTP_FROM", "") or username)
    if not host or not username or not password or not EMAIL_RE.fullmatch(sender):
        return None
    try:
        port = int(os.getenv("PIAULE_SMTP_PORT", "587"))
    except ValueError:
        return None
    use_ssl = os.getenv("PIAULE_SMTP_USE_SSL", "false").strip().lower() == "true"
    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "sender": sender,
        "use_ssl": use_ssl,
    }


def _imap_settings() -> dict[str, object] | None:
    if not _email_enabled():
        return None
    host = os.getenv("PIAULE_IMAP_HOST", "imap.hostinger.com").strip()
    username = os.getenv("PIAULE_IMAP_USERNAME", "").strip()
    password = os.getenv("PIAULE_IMAP_PASSWORD", "")
    if not host or not username or not password:
        return None
    try:
        port = int(os.getenv("PIAULE_IMAP_PORT", "993"))
    except ValueError:
        return None
    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "folder": os.getenv("PIAULE_IMAP_FOLDER", "INBOX").strip() or "INBOX",
    }


def _send_smtp_message(recipient: str, subject: str, body: str) -> None:
    settings = _smtp_settings()
    if settings is None:
        raise RuntimeError("La configuration SMTP est incomplète ou désactivée.")
    message = EmailMessage()
    message["From"] = str(settings["sender"])
    message["To"] = recipient
    message["Subject"] = subject or "Piaule Fiction"
    message.set_content(body)
    if bool(settings["use_ssl"]):
        with smtplib.SMTP_SSL(str(settings["host"]), int(settings["port"]), timeout=20) as client:
            client.login(str(settings["username"]), str(settings["password"]))
            client.send_message(message)
        return
    with smtplib.SMTP(str(settings["host"]), int(settings["port"]), timeout=20) as client:
        client.ehlo()
        client.starttls()
        client.ehlo()
        client.login(str(settings["username"]), str(settings["password"]))
        client.send_message(message)


def _decode_email_header(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except (TypeError, ValueError):
        return value


def _html_to_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", without_tags).strip()


def _extract_email_parts(message: Message) -> tuple[str, list[tuple[str, str, bytes]]]:
    text_parts: list[str] = []
    attachments: list[tuple[str, str, bytes]] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        payload = part.get_payload(decode=True) or b""
        filename = _decode_email_header(part.get_filename())
        disposition = part.get_content_disposition()
        content_type = part.get_content_type().lower()
        if filename or disposition == "attachment":
            attachments.append((filename or "piece-jointe", content_type, payload))
        elif content_type == "text/plain":
            charset = part.get_content_charset() or "utf-8"
            text_parts.append(payload.decode(charset, errors="replace"))
        elif content_type == "text/html" and not text_parts:
            charset = part.get_content_charset() or "utf-8"
            text_parts.append(_html_to_text(payload.decode(charset, errors="replace")))
    return "\n\n".join(text_parts).strip(), attachments


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
            _provision_workspace_agents(connection, workspace_id)
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


@app.get("/api/agents", response_model=list[OwnerAgent])
def list_owner_agents(owner: Candidate = Depends(current_candidate)) -> list[OwnerAgent]:
    """Return the standard, workspace-isolated team visible to the owner."""

    with closing(_connect()) as connection:
        _provision_workspace_agents(connection, owner.workspace_id)
        connection.commit()
        rows = connection.execute(
            """
            SELECT * FROM workspace_agents
            WHERE workspace_id = ?
            ORDER BY is_primary DESC, created_at ASC, role_key ASC
            """,
            (owner.workspace_id,),
        ).fetchall()
    return [_owner_agent_from_row(row) for row in rows]


@app.get("/api/agents/orchestrateur/messages", response_model=list[OwnerAgentMessage])
def list_orchestrator_messages(
    limit: int = 50,
    owner: Candidate = Depends(current_candidate),
) -> list[OwnerAgentMessage]:
    """List the owner's conversation with the workspace orchestrator."""

    safe_limit = max(1, min(limit, 100))
    with closing(_connect()) as connection:
        _provision_workspace_agents(connection, owner.workspace_id)
        rows = connection.execute(
            """
            SELECT m.*, a.role_key
            FROM agent_messages m
            JOIN workspace_agents a ON a.id = m.agent_id
            WHERE m.workspace_id = ? AND a.role_key = 'orchestrateur'
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT ?
            """,
            (owner.workspace_id, safe_limit),
        ).fetchall()
    return [_owner_agent_message_from_row(row) for row in reversed(rows)]


@app.post("/api/agents/orchestrateur/messages", response_model=OwnerAgentMessage, status_code=201)
def send_orchestrator_message(
    payload: OwnerAgentMessageCreate,
    owner: Candidate = Depends(current_candidate),
) -> OwnerAgentMessage:
    """Record a mission for the orchestrator; a worker will process it later."""

    content = _clean_text(payload.contenu, 4000)
    if len(content) < 2:
        raise HTTPException(status_code=422, detail="La demande au Orchestrateur est trop courte.")
    now = _iso_now()
    message_id = f"agent-message-{uuid4().hex[:16]}"
    run_id = f"agent-run-{uuid4().hex[:16]}"
    with closing(_connect()) as connection:
        _provision_workspace_agents(connection, owner.workspace_id)
        agent = connection.execute(
            "SELECT * FROM workspace_agents WHERE workspace_id = ? AND role_key = 'orchestrateur'",
            (owner.workspace_id,),
        ).fetchone()
        if agent is None:
            raise HTTPException(status_code=503, detail="L'équipe d'agents n'est pas disponible.")
        context = {
            "message_id": message_id,
            "contexte_type": _clean_text(payload.contexte_type, 80),
            "contexte_id": _clean_text(payload.contexte_id, 160),
        }
        connection.execute(
            """
            INSERT INTO agent_runs(
                id, workspace_id, agent_type, mission, target_type, target_id,
                status, input_json, output_json, evidence_json, error,
                created_at, updated_at
            ) VALUES (?, ?, 'orchestrateur', ?, 'workspace', ?, 'queued', ?, '{}', '[]', '', ?, ?)
            """,
            (
                run_id,
                owner.workspace_id,
                "Traiter la demande du propriétaire et préparer le prochain plan d'action.",
                owner.workspace_id,
                _json_object({"contenu": content, **context}, label="L'entrée de la mission"),
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO agent_messages(
                id, workspace_id, agent_id, agent_run_id, direction, content,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'proprietaire', ?, 'a_traiter', ?, ?)
            """,
            (message_id, owner.workspace_id, agent["id"], run_id, content, now, now),
        )
        _record_audit_event(
            connection,
            workspace_id=owner.workspace_id,
            actor_type="proprietaire",
            actor_id=owner.email,
            event_name="demande_orchestrateur_recue",
            entity_type="agent_message",
            entity_id=message_id,
            metadata={"run_id": run_id, **context},
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT m.*, a.role_key
            FROM agent_messages m
            JOIN workspace_agents a ON a.id = m.agent_id
            WHERE m.id = ? AND m.workspace_id = ?
            """,
            (message_id, owner.workspace_id),
        ).fetchone()
    return _owner_agent_message_from_row(row)


@app.get("/api/agents/{agent_id}", response_model=OwnerAgent)
def get_owner_agent(agent_id: str, owner: Candidate = Depends(current_candidate)) -> OwnerAgent:
    with closing(_connect()) as connection:
        _provision_workspace_agents(connection, owner.workspace_id)
        row = connection.execute(
            "SELECT * FROM workspace_agents WHERE id = ? AND workspace_id = ?",
            (agent_id, owner.workspace_id),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Agent introuvable dans ce workspace.")
    return _owner_agent_from_row(row)


@app.get("/api/agent-runs", response_model=list[AgentRun])
def list_agent_runs(
    statut: AgentRunStatus | None = None,
    limit: int = 50,
    owner: Candidate = Depends(current_candidate),
) -> list[AgentRun]:
    """List the agent missions belonging to the current owner's workspace."""

    safe_limit = max(1, min(limit, 100))
    with closing(_connect()) as connection:
        query = "SELECT * FROM agent_runs WHERE workspace_id = ?"
        values: list[object] = [owner.workspace_id]
        if statut:
            query += " AND status = ?"
            values.append(statut)
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        values.append(safe_limit)
        rows = connection.execute(query, values).fetchall()
    return [_agent_run_from_row(row) for row in rows]


@app.get("/api/agent-runs/{run_id}", response_model=AgentRun)
def get_agent_run(run_id: str, owner: Candidate = Depends(current_candidate)) -> AgentRun:
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT * FROM agent_runs WHERE id = ? AND workspace_id = ?",
            (run_id, owner.workspace_id),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Mission d'agent introuvable dans ce workspace.")
    return _agent_run_from_row(row)


@app.get("/api/actions", response_model=list[Action])
def list_actions(
    statut: ActionStatus | None = None,
    niveau_risque: ActionRisk | None = None,
    limit: int = 50,
    owner: Candidate = Depends(current_candidate),
) -> list[Action]:
    """Return the validation queue without executing any action."""

    safe_limit = max(1, min(limit, 100))
    with closing(_connect()) as connection:
        query = "SELECT * FROM actions WHERE workspace_id = ?"
        values: list[object] = [owner.workspace_id]
        if statut:
            query += " AND status = ?"
            values.append(statut)
        if niveau_risque:
            query += " AND risk_level = ?"
            values.append(niveau_risque)
        query += " ORDER BY CASE status WHEN 'a_valider' THEN 0 WHEN 'autorisee' THEN 1 ELSE 2 END, created_at DESC, id DESC LIMIT ?"
        values.append(safe_limit)
        rows = connection.execute(query, values).fetchall()
    return [_action_from_row(row) for row in rows]


@app.get("/api/actions/{action_id}", response_model=Action)
def get_action(action_id: str, owner: Candidate = Depends(current_candidate)) -> Action:
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT * FROM actions WHERE id = ? AND workspace_id = ?",
            (action_id, owner.workspace_id),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Action introuvable dans ce workspace.")
    return _action_from_row(row)


def _owner_decide_action(
    action_id: str,
    *,
    decision: ActionDecision,
    payload: ActionDecisionRequest,
    owner: Candidate,
) -> Action:
    reason = _clean_text(payload.motif, 2000)
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT * FROM actions WHERE id = ? AND workspace_id = ?",
            (action_id, owner.workspace_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Action introuvable dans ce workspace.")
        if row["status"] == "executee":
            raise HTTPException(status_code=409, detail="Une action déjà exécutée ne peut plus être modifiée.")
        if _action_expired(row):
            if row["status"] not in {"expiree", "refusee"}:
                connection.execute(
                    "UPDATE actions SET status = 'expiree', last_reason = ?, updated_at = ? WHERE id = ?",
                    ("La durée de validité de l'action est dépassée.", _iso_now(), action_id),
                )
                _record_audit_event(
                    connection,
                    workspace_id=owner.workspace_id,
                    actor_type="system",
                    actor_id="action-center",
                    event_name="action_expiree",
                    entity_type="action",
                    entity_id=action_id,
                    property_id=row["property_id"],
                    application_id=row["application_id"],
                )
                connection.commit()
            raise HTTPException(status_code=409, detail="Cette action a expiré et doit être préparée à nouveau.")
        if decision == "autorisee":
            if not row["requires_approval"]:
                raise HTTPException(status_code=409, detail="Cette action ne nécessite pas de validation.")
            if row["status"] == "autorisee":
                return _action_from_row(row)
            if row["status"] != "a_valider":
                raise HTTPException(status_code=409, detail="Cette action n'est plus dans la file de validation.")
            next_status = "autorisee"
            event_name = "action_autorisee"
        else:
            if row["status"] == "refusee":
                return _action_from_row(row)
            if row["status"] not in {"proposee", "a_valider"}:
                raise HTTPException(status_code=409, detail="Cette action ne peut plus être refusée.")
            next_status = "refusee"
            event_name = "action_refusee"
        now = _iso_now()
        connection.execute(
            """
            UPDATE actions
            SET status = ?, approved_at = CASE WHEN ? = 'autorisee' THEN ? ELSE approved_at END,
                last_reason = ?, updated_at = ?
            WHERE id = ? AND workspace_id = ?
            """,
            (next_status, next_status, now, reason, now, action_id, owner.workspace_id),
        )
        connection.execute(
            """
            INSERT INTO approvals(id, workspace_id, action_id, approver_email, decision, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (f"approval-{uuid4().hex[:16]}", owner.workspace_id, action_id, owner.email, decision, reason, now),
        )
        _record_audit_event(
            connection,
            workspace_id=owner.workspace_id,
            actor_type="proprietaire",
            actor_id=owner.email,
            event_name=event_name,
            entity_type="action",
            entity_id=action_id,
            property_id=row["property_id"],
            application_id=row["application_id"],
            metadata={"motif": reason, "decision": decision},
        )
        connection.commit()
        updated = connection.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    return _action_from_row(updated)


@app.post("/api/actions/{action_id}/approve", response_model=Action)
def approve_action(
    action_id: str,
    payload: ActionDecisionRequest,
    owner: Candidate = Depends(current_candidate),
) -> Action:
    """Authorize a sensitive agent proposal without executing it."""

    return _owner_decide_action(action_id, decision="autorisee", payload=payload, owner=owner)


@app.post("/api/actions/{action_id}/reject", response_model=Action)
def reject_action(
    action_id: str,
    payload: ActionDecisionRequest,
    owner: Candidate = Depends(current_candidate),
) -> Action:
    return _owner_decide_action(action_id, decision="refusee", payload=payload, owner=owner)


@app.get("/api/audit", response_model=list[AuditEvent])
def list_audit_events(
    entite_type: str | None = None,
    entite_id: str | None = None,
    limit: int = 100,
    owner: Candidate = Depends(current_candidate),
) -> list[AuditEvent]:
    safe_limit = max(1, min(limit, 200))
    with closing(_connect()) as connection:
        query = "SELECT * FROM audit_events WHERE workspace_id = ?"
        values: list[object] = [owner.workspace_id]
        if entite_type:
            query += " AND entity_type = ?"
            values.append(_clean_text(entite_type, 80))
        if entite_id:
            query += " AND entity_id = ?"
            values.append(_clean_text(entite_id, 160))
        query += " ORDER BY rowid DESC LIMIT ?"
        values.append(safe_limit)
        rows = connection.execute(query, values).fetchall()
    return [_audit_event_from_row(row) for row in rows]


@app.post("/api/internal/agent-runs", response_model=AgentRun, status_code=201)
def create_agent_run(payload: InternalAgentRunCreate, request: Request) -> AgentRun:
    """Create a mission from a trusted worker; no model call happens here."""

    _agent_internal_auth(request)
    run_id = f"agent-run-{uuid4().hex[:16]}"
    now = _iso_now()
    input_json = _json_object(payload.entree, label="L'entrée de la mission")
    with closing(_connect()) as connection:
        workspace = connection.execute("SELECT id FROM workspaces WHERE id = ?", (payload.workspace_id,)).fetchone()
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace introuvable.")
        connection.execute(
            """
            INSERT INTO agent_runs(
                id, workspace_id, agent_type, mission, target_type, target_id,
                status, input_json, output_json, evidence_json, error,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, '{}', '[]', '', ?, ?)
            """,
            (
                run_id,
                payload.workspace_id,
                _clean_text(payload.type_agent, 120),
                _clean_text(payload.mission, 2000),
                _clean_text(payload.cible_type, 80),
                _clean_text(payload.cible_id, 160),
                input_json,
                now,
                now,
            ),
        )
        _record_audit_event(
            connection,
            workspace_id=payload.workspace_id,
            actor_type="agent",
            actor_id=_clean_text(payload.type_agent, 120),
            event_name="mission_agent_creee",
            entity_type="agent_run",
            entity_id=run_id,
            metadata={"mission": _clean_text(payload.mission, 2000)},
        )
        connection.commit()
        row = connection.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
    return _agent_run_from_row(row)


@app.put("/api/internal/agent-runs/{run_id}", response_model=AgentRun)
def update_agent_run(
    run_id: str,
    payload: AgentRunStatusUpdate,
    request: Request,
) -> AgentRun:
    _agent_internal_auth(request)
    terminal_statuses = {"completed", "failed", "cancelled"}
    now = _iso_now()
    with closing(_connect()) as connection:
        row = connection.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Mission d'agent introuvable.")
        if row["status"] in terminal_statuses:
            return _agent_run_from_row(row)
        output_json = _json_object(payload.sortie, label="La sortie de la mission")
        evidence_json = _json_object(payload.preuves, label="Les preuves de la mission", maximum=50_000)
        started_at = row["started_at"] or (now if payload.statut == "running" else None)
        finished_at = now if payload.statut in terminal_statuses else row["finished_at"]
        connection.execute(
            """
            UPDATE agent_runs
            SET status = ?, output_json = ?, evidence_json = ?, error = ?,
                started_at = ?, finished_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.statut,
                output_json,
                evidence_json,
                _clean_text(payload.erreur, 4000),
                started_at,
                finished_at,
                now,
                run_id,
            ),
        )
        _record_audit_event(
            connection,
            workspace_id=row["workspace_id"],
            actor_type="agent",
            actor_id="agent-worker",
            event_name="mission_agent_mise_a_jour",
            entity_type="agent_run",
            entity_id=run_id,
            metadata={"statut": payload.statut, "erreur": _clean_text(payload.erreur, 4000)},
        )
        connection.commit()
        updated = connection.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
    return _agent_run_from_row(updated)


@app.post("/api/internal/actions", response_model=Action, status_code=201)
def create_internal_action(payload: InternalAgentActionCreate, request: Request, response: Response) -> Action:
    """Persist an agent proposal; external side effects are intentionally absent."""

    _agent_internal_auth(request)
    with closing(_connect()) as connection:
        row, created = _create_agent_action(
            connection,
            workspace_id=payload.workspace_id,
            payload=payload,
            actor_type="agent",
            actor_id=payload.agent_run_id or "agent-worker",
        )
        connection.commit()
    if not created:
        response.status_code = 200
    return _action_from_row(row)


@app.post("/api/internal/actions/{action_id}/execute", response_model=Action)
def execute_action(action_id: str, payload: ActionExecutionUpdate, request: Request) -> Action:
    """Record execution after approval; this endpoint is only a provider boundary marker."""

    _agent_internal_auth(request)
    now = _iso_now()
    with closing(_connect()) as connection:
        row = connection.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Action introuvable.")
        if row["status"] == "executee":
            return _action_from_row(row)
        if _action_expired(row):
            connection.execute(
                "UPDATE actions SET status = 'expiree', last_reason = ?, updated_at = ? WHERE id = ?",
                ("La durée de validité de l'action est dépassée.", now, action_id),
            )
            _record_audit_event(
                connection,
                workspace_id=row["workspace_id"],
                actor_type="system",
                actor_id="action-center",
                event_name="action_expiree",
                entity_type="action",
                entity_id=action_id,
                property_id=row["property_id"],
                application_id=row["application_id"],
            )
            connection.commit()
            raise HTTPException(status_code=409, detail="Cette action a expiré et doit être préparée à nouveau.")
        if row["requires_approval"] and row["status"] != "autorisee":
            raise HTTPException(status_code=409, detail="La validation du propriétaire est requise avant exécution.")
        result_json = _json_object(payload.resultat, label="Le résultat d'exécution", maximum=20_000)
        reference = _clean_text(payload.reference_execution, 240)
        connection.execute(
            """
            UPDATE actions
            SET status = 'executee', executed_at = ?, execution_reference = ?,
                last_reason = '', updated_at = ?
            WHERE id = ?
            """,
            (now, reference, now, action_id),
        )
        _record_audit_event(
            connection,
            workspace_id=row["workspace_id"],
            actor_type="agent",
            actor_id="agent-worker",
            event_name="action_executee",
            entity_type="action",
            entity_id=action_id,
            property_id=row["property_id"],
            application_id=row["application_id"],
            metadata={"reference_execution": reference, "resultat": json.loads(result_json)},
        )
        connection.commit()
        updated = connection.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    return _action_from_row(updated)


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
                id, workspace_id, nom, property_type, structure_type, adresse_ligne1,
                adresse_ligne2, code_postal, ville, pays, description, description_publique,
                statut, date_disponibilite, mode_detention, adresse_exacte_visible,
                equipements_json, photos_json, tags_json, syndic_nom, syndic_email,
                syndic_telephone, tantiemes_total, verification_policy,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                property_id,
                owner.workspace_id,
                cleaned.nom,
                cleaned.type,
                cleaned.structure,
                cleaned.adresse_ligne1,
                cleaned.adresse_ligne2,
                cleaned.code_postal,
                cleaned.ville,
                cleaned.pays,
                cleaned.description,
                cleaned.description_publique,
                cleaned.statut,
                cleaned.date_disponibilite.isoformat() if cleaned.date_disponibilite else None,
                cleaned.mode_detention,
                int(cleaned.adresse_exacte_visible),
                json.dumps(cleaned.equipements, ensure_ascii=False),
                json.dumps(cleaned.photos, ensure_ascii=False),
                json.dumps(cleaned.tags, ensure_ascii=False),
                cleaned.syndic_nom,
                cleaned.syndic_email,
                cleaned.syndic_telephone,
                cleaned.tantiemes_total,
                cleaned.politique_verification,
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
                nom = ?, property_type = ?, structure_type = ?, adresse_ligne1 = ?, adresse_ligne2 = ?,
                code_postal = ?, ville = ?, pays = ?, description = ?, description_publique = ?,
                statut = ?, date_disponibilite = ?, mode_detention = ?, adresse_exacte_visible = ?,
                equipements_json = ?, photos_json = ?, tags_json = ?, syndic_nom = ?, syndic_email = ?,
                syndic_telephone = ?, tantiemes_total = ?, verification_policy = ?, updated_at = datetime('now')
            WHERE id = ? AND workspace_id = ?
            """,
            (
                cleaned.nom,
                cleaned.type,
                cleaned.structure,
                cleaned.adresse_ligne1,
                cleaned.adresse_ligne2,
                cleaned.code_postal,
                cleaned.ville,
                cleaned.pays,
                cleaned.description,
                cleaned.description_publique,
                cleaned.statut,
                cleaned.date_disponibilite.isoformat() if cleaned.date_disponibilite else None,
                cleaned.mode_detention,
                int(cleaned.adresse_exacte_visible),
                json.dumps(cleaned.equipements, ensure_ascii=False),
                json.dumps(cleaned.photos, ensure_ascii=False),
                json.dumps(cleaned.tags, ensure_ascii=False),
                cleaned.syndic_nom,
                cleaned.syndic_email,
                cleaned.syndic_telephone,
                cleaned.tantiemes_total,
                cleaned.politique_verification,
                property_id,
                owner.workspace_id,
            ),
        )
        connection.commit()
        row = _owned_property_row(connection, owner, property_id)
    return _property_from_row(row)


VERIFICATION_POLICY_RULES: dict[str, list[str]] = {
    "standard": [
        "contrôles techniques et cohérence entre pièces",
        "aucune confirmation externe obligatoire",
    ],
    "renforcee": [
        "contrôles techniques et cohérence entre pièces",
        "attestation employeur ou confirmation ciblée si nécessaire",
        "validation humaine pour les exceptions",
    ],
    "officielle": [
        "preuve officielle demandée lorsque le document le permet",
        "DossierFacile, France Identité ou DGFiP selon le type de pièce",
        "validation humaine si aucune source officielle n'est disponible",
    ],
}
VERIFICATION_POLICY_SOURCES: dict[str, list[str]] = {
    "standard": ["controle_local", "revue_humaine"],
    "renforcee": ["controle_local", "employeur", "dossier_facile", "revue_humaine"],
    "officielle": [
        "controle_local",
        "employeur",
        "dossier_facile",
        "france_identite",
        "dgfip",
        "revue_humaine",
    ],
}


def _property_verification_policy_from_row(row: sqlite3.Row) -> PropertyVerificationPolicy:
    policy = row["verification_policy"] or "standard"
    return PropertyVerificationPolicy(
        bien_id=row["id"],
        politique=policy,
        sources_disponibles=VERIFICATION_POLICY_SOURCES[policy],
        regles=VERIFICATION_POLICY_RULES[policy],
        mis_a_jour_le=row["updated_at"],
    )


@app.get("/api/biens/{property_id}/politique-verification", response_model=PropertyVerificationPolicy)
def get_property_verification_policy(
    property_id: str, owner: Candidate = Depends(current_candidate)
) -> PropertyVerificationPolicy:
    with closing(_connect()) as connection:
        row = _owned_property_row(connection, owner, property_id)
    return _property_verification_policy_from_row(row)


@app.put("/api/biens/{property_id}/politique-verification", response_model=PropertyVerificationPolicy)
def update_property_verification_policy(
    property_id: str,
    payload: VerificationPolicyUpdate,
    owner: Candidate = Depends(current_candidate),
) -> PropertyVerificationPolicy:
    with closing(_connect()) as connection:
        _owned_property_row(connection, owner, property_id)
        connection.execute(
            "UPDATE properties SET verification_policy = ?, updated_at = datetime('now') WHERE id = ? AND workspace_id = ?",
            (payload.politique, property_id, owner.workspace_id),
        )
        connection.commit()
        row = _owned_property_row(connection, owner, property_id)
    return _property_verification_policy_from_row(row)


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
                    id, workspace_id, property_id, identifiant, lot_type, type_location, etage,
                    surface_m2, pieces, chambres, loyer_mensuel_eur, charges_mensuelles_eur,
                    type_charges, depot_garantie_eur, date_disponibilite, revision_irl_active,
                    indice_irl_reference, date_revision, dpe_classe, ges_classe, dpe_date,
                    chauffage, eau_chaude, ascenseur, accessibilite, equipements_json,
                    dependances_json, photos_json, tantiemes_generaux, statut,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (
                    lot_id,
                    owner.workspace_id,
                    property_id,
                    cleaned.identifiant,
                    cleaned.type,
                    cleaned.type_location,
                    cleaned.etage,
                    cleaned.surface_m2,
                    cleaned.pieces,
                    cleaned.chambres,
                    cleaned.loyer_mensuel_eur,
                    cleaned.charges_mensuelles_eur,
                    cleaned.type_charges,
                    cleaned.depot_garantie_eur,
                    cleaned.date_disponibilite.isoformat() if cleaned.date_disponibilite else None,
                    int(cleaned.revision_irl_active),
                    cleaned.indice_irl_reference,
                    cleaned.date_revision.isoformat() if cleaned.date_revision else None,
                    cleaned.dpe_classe,
                    cleaned.ges_classe,
                    cleaned.dpe_date.isoformat() if cleaned.dpe_date else None,
                    cleaned.chauffage,
                    cleaned.eau_chaude,
                    int(cleaned.ascenseur),
                    cleaned.accessibilite,
                    json.dumps(cleaned.equipements, ensure_ascii=False),
                    json.dumps(cleaned.dependances, ensure_ascii=False),
                    json.dumps(cleaned.photos, ensure_ascii=False),
                    cleaned.tantiemes_generaux,
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
                    identifiant = ?, lot_type = ?, type_location = ?, etage = ?, surface_m2 = ?,
                    pieces = ?, chambres = ?, loyer_mensuel_eur = ?, charges_mensuelles_eur = ?,
                    type_charges = ?, depot_garantie_eur = ?, date_disponibilite = ?,
                    revision_irl_active = ?, indice_irl_reference = ?, date_revision = ?,
                    dpe_classe = ?, ges_classe = ?, dpe_date = ?, chauffage = ?, eau_chaude = ?,
                    ascenseur = ?, accessibilite = ?, equipements_json = ?, dependances_json = ?,
                    photos_json = ?, tantiemes_generaux = ?, statut = ?, updated_at = datetime('now')
                WHERE id = ? AND property_id = ? AND workspace_id = ?
                """,
                (
                    cleaned.identifiant,
                    cleaned.type,
                    cleaned.type_location,
                    cleaned.etage,
                    cleaned.surface_m2,
                    cleaned.pieces,
                    cleaned.chambres,
                    cleaned.loyer_mensuel_eur,
                    cleaned.charges_mensuelles_eur,
                    cleaned.type_charges,
                    cleaned.depot_garantie_eur,
                    cleaned.date_disponibilite.isoformat() if cleaned.date_disponibilite else None,
                    int(cleaned.revision_irl_active),
                    cleaned.indice_irl_reference,
                    cleaned.date_revision.isoformat() if cleaned.date_revision else None,
                    cleaned.dpe_classe,
                    cleaned.ges_classe,
                    cleaned.dpe_date.isoformat() if cleaned.dpe_date else None,
                    cleaned.chauffage,
                    cleaned.eau_chaude,
                    int(cleaned.ascenseur),
                    cleaned.accessibilite,
                    json.dumps(cleaned.equipements, ensure_ascii=False),
                    json.dumps(cleaned.dependances, ensure_ascii=False),
                    json.dumps(cleaned.photos, ensure_ascii=False),
                    cleaned.tantiemes_generaux,
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


def _owned_property_record_row(
    connection: sqlite3.Connection, owner: Candidate, property_id: str, record_id: str
) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM property_records WHERE id = ? AND property_id = ? AND workspace_id = ?",
        (record_id, property_id, owner.workspace_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Suivi introuvable dans ce workspace.")
    return row


def _clean_property_record_payload(payload: PropertyRecordCreate) -> PropertyRecordCreate:
    if payload.date_etablissement and payload.date_expiration and payload.date_expiration < payload.date_etablissement:
        raise HTTPException(status_code=400, detail="La date d'expiration ne peut pas précéder la date d'établissement.")
    return PropertyRecordCreate(
        type=payload.type,
        titre=_clean_text(payload.titre, 160),
        lot_id=_clean_text(payload.lot_id, 80) if payload.lot_id else None,
        fournisseur=_clean_text(payload.fournisseur, 160),
        reference=_clean_text(payload.reference, 120),
        date_etablissement=payload.date_etablissement,
        date_expiration=payload.date_expiration,
        statut=payload.statut,
        notes=_clean_text(payload.notes, 2000),
    )


@app.get("/api/biens/{property_id}/suivis", response_model=list[PropertyRecord])
def list_property_records(
    property_id: str, owner: Candidate = Depends(current_candidate)
) -> list[PropertyRecord]:
    """List diagnostics, contracts and other expiry-tracked records for a property."""

    with closing(_connect()) as connection:
        _owned_property_row(connection, owner, property_id)
        rows = connection.execute(
            """
            SELECT * FROM property_records
            WHERE property_id = ? AND workspace_id = ?
            ORDER BY COALESCE(date_expiration, '9999-12-31'), created_at DESC
            """,
            (property_id, owner.workspace_id),
        ).fetchall()
    return [_property_record_from_row(row) for row in rows]


@app.post("/api/biens/{property_id}/suivis", response_model=PropertyRecord, status_code=201)
def create_property_record(
    property_id: str,
    payload: PropertyRecordCreate,
    owner: Candidate = Depends(current_candidate),
) -> PropertyRecord:
    """Create an expiry-tracked property record without uploading its file yet."""

    cleaned = _clean_property_record_payload(payload)
    record_id = f"suivi-{uuid4().hex[:16]}"
    with closing(_connect()) as connection:
        _owned_property_row(connection, owner, property_id)
        if cleaned.lot_id:
            _owned_lot_row(connection, owner, property_id, cleaned.lot_id)
        connection.execute(
            """
            INSERT INTO property_records(
                id, workspace_id, property_id, lot_id, record_type, titre,
                fournisseur, reference, date_etablissement, date_expiration,
                statut, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                record_id,
                owner.workspace_id,
                property_id,
                cleaned.lot_id,
                cleaned.type,
                cleaned.titre,
                cleaned.fournisseur,
                cleaned.reference,
                cleaned.date_etablissement.isoformat() if cleaned.date_etablissement else None,
                cleaned.date_expiration.isoformat() if cleaned.date_expiration else None,
                cleaned.statut,
                cleaned.notes,
            ),
        )
        connection.commit()
        row = _owned_property_record_row(connection, owner, property_id, record_id)
    return _property_record_from_row(row)


@app.put("/api/biens/{property_id}/suivis/{record_id}", response_model=PropertyRecord)
def update_property_record(
    property_id: str,
    record_id: str,
    payload: PropertyRecordCreate,
    owner: Candidate = Depends(current_candidate),
) -> PropertyRecord:
    cleaned = _clean_property_record_payload(payload)
    with closing(_connect()) as connection:
        _owned_property_row(connection, owner, property_id)
        _owned_property_record_row(connection, owner, property_id, record_id)
        if cleaned.lot_id:
            _owned_lot_row(connection, owner, property_id, cleaned.lot_id)
        connection.execute(
            """
            UPDATE property_records SET
                lot_id = ?, record_type = ?, titre = ?, fournisseur = ?, reference = ?,
                date_etablissement = ?, date_expiration = ?, statut = ?, notes = ?,
                updated_at = datetime('now')
            WHERE id = ? AND property_id = ? AND workspace_id = ?
            """,
            (
                cleaned.lot_id,
                cleaned.type,
                cleaned.titre,
                cleaned.fournisseur,
                cleaned.reference,
                cleaned.date_etablissement.isoformat() if cleaned.date_etablissement else None,
                cleaned.date_expiration.isoformat() if cleaned.date_expiration else None,
                cleaned.statut,
                cleaned.notes,
                record_id,
                property_id,
                owner.workspace_id,
            ),
        )
        connection.commit()
        row = _owned_property_record_row(connection, owner, property_id, record_id)
    return _property_record_from_row(row)


@app.get("/api/echeances", response_model=list[PropertyRecord])
def list_upcoming_deadlines(
    jours: int = 30, owner: Candidate = Depends(current_candidate)
) -> list[PropertyRecord]:
    """Return expired and soon-expiring property records for the current workspace."""

    if jours < 0 or jours > 3650:
        raise HTTPException(status_code=400, detail="La période doit être comprise entre 0 et 3650 jours.")
    today = date.today()
    limit = date.fromordinal(today.toordinal() + jours)
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT * FROM property_records
            WHERE workspace_id = ? AND date_expiration IS NOT NULL
              AND date_expiration <= ?
            ORDER BY date_expiration, created_at
            """,
            (owner.workspace_id, limit.isoformat()),
        ).fetchall()
    return [_property_record_from_row(row) for row in rows]


def _clean_visit_slot_payload(payload: VisitSlotCreate) -> tuple[VisitSlotCreate, str, str]:
    start = _parse_visit_datetime(payload.debut, "debut")
    end = _parse_visit_datetime(payload.fin, "fin")
    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
    if end_dt <= start_dt:
        raise HTTPException(status_code=422, detail="La fin doit être postérieure au début.")
    if (end_dt - start_dt).total_seconds() > 8 * 3600:
        raise HTTPException(status_code=422, detail="Un créneau ne peut pas dépasser huit heures.")
    cleaned = VisitSlotCreate(
        lot_id=_clean_text(payload.lot_id, 80) if payload.lot_id else None,
        debut=start,
        fin=end,
        fuseau=_clean_text(payload.fuseau, 80),
        mode=payload.mode,
        note=_clean_text(payload.note, 500),
    )
    return cleaned, start, end


@app.get("/api/biens/{property_id}/visite-creneaux", response_model=list[VisitSlot])
def list_visit_slots(
    property_id: str,
    statut: VisitSlotStatus | None = None,
    owner: Candidate = Depends(current_candidate),
) -> list[VisitSlot]:
    with closing(_connect()) as connection:
        _owned_property_row(connection, owner, property_id)
        query = "SELECT * FROM visit_slots WHERE property_id = ? AND workspace_id = ?"
        values: list[object] = [property_id, owner.workspace_id]
        if statut:
            query += " AND status = ?"
            values.append(statut)
        query += " ORDER BY starts_at, id"
        rows = connection.execute(query, values).fetchall()
    return [_visit_slot_from_row(row) for row in rows]


@app.post("/api/biens/{property_id}/visite-creneaux", response_model=VisitSlot, status_code=201)
def create_visit_slot(
    property_id: str,
    payload: VisitSlotCreate,
    owner: Candidate = Depends(current_candidate),
) -> VisitSlot:
    """Create one owner availability slot, without contacting a candidate."""

    cleaned, start, end = _clean_visit_slot_payload(payload)
    slot_id = f"visit-slot-{uuid4().hex[:16]}"
    with closing(_connect()) as connection:
        _owned_property_row(connection, owner, property_id)
        if cleaned.lot_id:
            _owned_lot_row(connection, owner, property_id, cleaned.lot_id)
        scope_clause = "(lot_id = ? OR lot_id IS NULL)" if cleaned.lot_id else "lot_id IS NULL"
        overlap = connection.execute(
            f"""
            SELECT id FROM visit_slots
            WHERE property_id = ? AND workspace_id = ? AND status <> 'bloque'
              AND {scope_clause} AND starts_at < ? AND ends_at > ?
            LIMIT 1
            """,
            (
                property_id,
                owner.workspace_id,
                *( [cleaned.lot_id] if cleaned.lot_id else [] ),
                end,
                start,
            ),
        ).fetchone()
        if overlap is not None:
            raise HTTPException(status_code=409, detail="Ce créneau chevauche déjà une disponibilité.")
        connection.execute(
            """
            INSERT INTO visit_slots(
                id, workspace_id, property_id, lot_id, starts_at, ends_at,
                timezone, mode, note, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'libre', datetime('now'))
            """,
            (
                slot_id,
                owner.workspace_id,
                property_id,
                cleaned.lot_id,
                start,
                end,
                cleaned.fuseau,
                cleaned.mode,
                cleaned.note,
            ),
        )
        connection.commit()
        row = connection.execute("SELECT * FROM visit_slots WHERE id = ?", (slot_id,)).fetchone()
    return _visit_slot_from_row(row)


@app.post(
    "/api/biens/{property_id}/candidatures/{application_id}/visites/proposer",
    response_model=Visit,
    status_code=201,
)
def propose_application_visit(
    property_id: str,
    application_id: str,
    payload: VisitCreate,
    owner: Candidate = Depends(current_candidate),
) -> Visit:
    """Reserve an available slot for a complete application.

    This creates a proposal only. Sending an e-mail or calendar invitation is a
    separate connector action and is deliberately not performed here.
    """

    note = _clean_text(payload.note, 1000)
    visit_id = f"visit-{uuid4().hex[:16]}"
    with closing(_connect()) as connection:
        application = _application_for_owner(connection, owner, property_id, application_id)
        completeness = _application_completeness(connection, owner.workspace_id, application_id)
        if completeness.statut != "complet":
            raise HTTPException(status_code=409, detail="La candidature doit être complète avant de proposer une visite.")
        slot = connection.execute(
            """
            SELECT * FROM visit_slots
            WHERE id = ? AND property_id = ? AND workspace_id = ? AND status = 'libre'
            """,
            (payload.slot_id, property_id, owner.workspace_id),
        ).fetchone()
        if slot is None:
            raise HTTPException(status_code=409, detail="Ce créneau n'est plus disponible.")
        if slot["lot_id"] and slot["lot_id"] != application["lot_id"]:
            raise HTTPException(status_code=409, detail="Ce créneau ne correspond pas au lot de la candidature.")
        existing = connection.execute(
            """
            SELECT id FROM visits
            WHERE workspace_id = ? AND slot_id = ? AND status IN ('proposee', 'confirmee')
            LIMIT 1
            """,
            (owner.workspace_id, payload.slot_id),
        ).fetchone()
        if existing is not None:
            raise HTTPException(status_code=409, detail="Ce créneau est déjà réservé.")
        connection.execute(
            """
            INSERT INTO visits(
                id, workspace_id, property_id, lot_id, application_id, slot_id,
                status, source, note, reason, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'proposee', 'agent', ?, '', datetime('now'), datetime('now'))
            """,
            (
                visit_id,
                owner.workspace_id,
                property_id,
                application["lot_id"],
                application_id,
                payload.slot_id,
                note,
            ),
        )
        connection.execute("UPDATE visit_slots SET status = 'reserve' WHERE id = ?", (payload.slot_id,))
        _set_application_status(
            connection,
            workspace_id=owner.workspace_id,
            application_id=application_id,
            new_status="visite_proposee",
            source="agent",
            reason="Créneau proposé après vérification de la complétude.",
        )
        connection.commit()
        row = _owned_visit_row(connection, owner, property_id, visit_id)
    return _visit_from_row(row)


@app.get("/api/biens/{property_id}/visites", response_model=list[Visit])
def list_property_visits(
    property_id: str,
    statut: VisitStatus | None = None,
    owner: Candidate = Depends(current_candidate),
) -> list[Visit]:
    with closing(_connect()) as connection:
        _owned_property_row(connection, owner, property_id)
        query = _visit_query() + " WHERE v.property_id = ? AND v.workspace_id = ?"
        values: list[object] = [property_id, owner.workspace_id]
        if statut:
            query += " AND v.status = ?"
            values.append(statut)
        query += " ORDER BY s.starts_at, v.created_at"
        rows = connection.execute(query, values).fetchall()
    return [_visit_from_row(row) for row in rows]


@app.post("/api/biens/{property_id}/visites/{visit_id}/annuler", response_model=Visit)
def cancel_property_visit(
    property_id: str,
    visit_id: str,
    payload: VisitCancelRequest,
    owner: Candidate = Depends(current_candidate),
) -> Visit:
    with closing(_connect()) as connection:
        row = _owned_visit_row(connection, owner, property_id, visit_id)
        if row["status"] in {"annulee", "refusee", "terminee"}:
            return _visit_from_row(row)
        reason = _clean_text(payload.motif, 500) or "Visite annulée par le propriétaire."
        connection.execute(
            "UPDATE visits SET status = 'annulee', reason = ?, updated_at = datetime('now') WHERE id = ?",
            (reason, visit_id),
        )
        connection.execute("UPDATE visit_slots SET status = 'libre' WHERE id = ?", (row["slot_id"],))
        application = connection.execute(
            "SELECT statut FROM owner_applications WHERE id = ? AND workspace_id = ?",
            (row["application_id"], owner.workspace_id),
        ).fetchone()
        if application and application["statut"] in {"visite_proposee", "visite_confirmee"}:
            _set_application_status(
                connection,
                workspace_id=owner.workspace_id,
                application_id=row["application_id"],
                new_status="prete",
                source="proprietaire",
                reason=reason,
            )
        connection.commit()
        updated = _owned_visit_row(connection, owner, property_id, visit_id)
    return _visit_from_row(updated)


@app.get("/api/candidatures", response_model=list[OwnerApplication])
def list_all_applications(owner: Candidate = Depends(current_candidate)) -> list[OwnerApplication]:
    """List the application pipeline across the current owner's portfolio."""

    with closing(_connect()) as connection:
        rows = connection.execute(
            _application_query()
            + " WHERE a.workspace_id = ? ORDER BY a.recue_le DESC, a.id",
            (owner.workspace_id,),
        ).fetchall()
    return [_application_from_row(row) for row in rows]


@app.get("/api/biens/{property_id}/canaux-candidatures", response_model=list[ApplicationChannel])
def list_application_channels(
    property_id: str, owner: Candidate = Depends(current_candidate)
) -> list[ApplicationChannel]:
    with closing(_connect()) as connection:
        _owned_property_row(connection, owner, property_id)
        rows = connection.execute(
            """
            SELECT * FROM application_channels
            WHERE property_id = ? AND workspace_id = ?
            ORDER BY created_at DESC, id
            """,
            (property_id, owner.workspace_id),
        ).fetchall()
    return [_application_channel_from_row(row) for row in rows]


@app.post("/api/biens/{property_id}/canaux-candidatures", response_model=ApplicationChannel, status_code=201)
def create_application_channel(
    property_id: str,
    payload: ApplicationChannelCreate,
    owner: Candidate = Depends(current_candidate),
) -> ApplicationChannel:
    """Create a unique reception address to place in an external listing."""

    cleaned = _clean_application_channel(payload)
    channel_id = f"canal-{uuid4().hex[:16]}"
    domain = os.getenv("PIAULE_APPLICATION_EMAIL_DOMAIN", "piaulefiction.fr").strip().lower()
    if not domain or "." not in domain or any(character.isspace() for character in domain):
        raise HTTPException(status_code=503, detail="Le domaine de réception des candidatures n'est pas configuré.")
    address = f"candidatures+{secrets.token_hex(10)}@{domain}"
    with closing(_connect()) as connection:
        _owned_property_row(connection, owner, property_id)
        if cleaned.lot_id:
            _owned_lot_row(connection, owner, property_id, cleaned.lot_id)
        connection.execute(
            """
            INSERT INTO application_channels(
                id, workspace_id, property_id, lot_id, canal, libelle,
                adresse_reception, actif, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, datetime('now'))
            """,
            (
                channel_id,
                owner.workspace_id,
                property_id,
                cleaned.lot_id,
                cleaned.canal,
                cleaned.libelle,
                address,
            ),
        )
        connection.commit()
        row = _owned_application_channel_row(connection, owner, channel_id)
    return _application_channel_from_row(row)


@app.get("/api/candidatures/inbox", response_model=list[InboundApplicationMessage])
def list_inbound_application_messages(
    owner: Candidate = Depends(current_candidate),
) -> list[InboundApplicationMessage]:
    """List raw messages waiting for agent extraction and association."""

    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT * FROM inbound_application_messages
            WHERE workspace_id = ?
            ORDER BY recu_le DESC, id
            """,
            (owner.workspace_id,),
        ).fetchall()
    return [_inbound_message_from_row(row) for row in rows]


def _store_inbound_attachment(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    inbound_message_id: str,
    filename: str,
    content_type: str,
    content: bytes,
) -> bool:
    extension = _document_extension(filename, content_type)
    if extension is None or len(content) > MAX_DOCUMENT_BYTES:
        return False
    attachment_id = f"inbound-attachment-{uuid4().hex}"
    stored_filename = f"{attachment_id}.{extension}"
    safe_filename = _clean_text(filename or f"piece.{extension}", 180)
    digest = hashlib.sha256(content).hexdigest()
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIRECTORY / stored_filename
    path.write_bytes(content)
    try:
        connection.execute(
            """
            INSERT INTO inbound_application_attachments(
                id, workspace_id, inbound_message_id, filename, content_type,
                size_bytes, sha256, stored_filename, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                attachment_id,
                workspace_id,
                inbound_message_id,
                safe_filename,
                content_type,
                len(content),
                digest,
                stored_filename,
            ),
        )
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return True


def _promote_inbound_attachments(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    inbound_message_id: str,
    application_id: str,
    property_id: str,
) -> int:
    rows = connection.execute(
        """
        SELECT * FROM inbound_application_attachments
        WHERE workspace_id = ? AND inbound_message_id = ?
          AND application_document_id IS NULL
        ORDER BY created_at, id
        """,
        (workspace_id, inbound_message_id),
    ).fetchall()
    promoted = 0
    for row in rows:
        document_id = f"application-doc-{uuid4().hex}"
        connection.execute(
            """
            INSERT INTO application_documents(
                id, workspace_id, application_id, property_id, document_type,
                nom, original_filename, stored_filename, content_type, size_bytes,
                sha256, provenance, statut, date_expiration, note_verification,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'autre', ?, ?, ?, ?, ?, ?, 'email', 'recu', NULL, '', datetime('now'), datetime('now'))
            """,
            (
                document_id,
                workspace_id,
                application_id,
                property_id,
                row["filename"],
                row["filename"],
                row["stored_filename"],
                row["content_type"],
                row["size_bytes"],
                row["sha256"],
            ),
        )
        connection.execute(
            "UPDATE inbound_application_attachments SET application_document_id = ? WHERE id = ?",
            (document_id, row["id"]),
        )
        inserted = connection.execute(
            "SELECT * FROM application_documents WHERE id = ?",
            (document_id,),
        ).fetchone()
        _document_preflight(connection, inserted)
        promoted += 1
    if promoted:
        _refresh_application_status(connection, workspace_id, application_id)
    return promoted


def _ingest_inbound_application(
    connection: sqlite3.Connection,
    *,
    reception_address: str,
    message_id: str,
    sender: str,
    subject: str,
    body: str,
    attachment_names: list[str],
    attachment_payloads: list[tuple[str, str, bytes]] | None = None,
    received_at: str | None = None,
) -> tuple[sqlite3.Row, bool, int]:
    reception_address = _normalise_email(reception_address)
    sender = _normalise_email(sender) if sender else ""
    if sender and not EMAIL_RE.fullmatch(sender):
        sender = ""
    cleaned_message_id = _clean_text(message_id, 300)
    attachments = _clean_string_list(attachment_names, maximum_items=50, maximum_length=240)
    with_payload_names = [item[0] for item in (attachment_payloads or [])]
    attachments = _clean_string_list(attachments + with_payload_names, maximum_items=50, maximum_length=240)
    channel = connection.execute(
        """
        SELECT * FROM application_channels
        WHERE lower(adresse_reception) = ? AND actif = 1
        """,
        (reception_address,),
    ).fetchone()
    if channel is None:
        raise HTTPException(status_code=404, detail="Adresse de réception inconnue ou désactivée.")
    matching_applications = connection.execute(
        """
        SELECT id FROM owner_applications
        WHERE workspace_id = ? AND property_id = ?
          AND lower(candidat_email) = ?
          AND (? IS NULL OR lot_id = ?)
        ORDER BY updated_at DESC
        """,
        (
            channel["workspace_id"],
            channel["property_id"],
            sender,
            channel["lot_id"],
            channel["lot_id"],
        ),
    ).fetchall() if sender else []
    matched_application_id = matching_applications[0]["id"] if len(matching_applications) == 1 else None
    existing = connection.execute(
        """
        SELECT * FROM inbound_application_messages
        WHERE workspace_id = ? AND message_id = ?
        """,
        (channel["workspace_id"], cleaned_message_id),
    ).fetchone()
    if existing is not None:
        return existing, bool(existing["application_id"]), 0

    inbound_id = f"message-{uuid4().hex[:16]}"
    connection.execute(
        """
        INSERT INTO inbound_application_messages(
            id, workspace_id, channel_id, property_id, lot_id, adresse_reception,
            message_id, expediteur_email, objet, contenu_texte, pieces_jointes_json,
            statut, application_id, recu_le, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, datetime('now')), datetime('now'))
        """,
        (
            inbound_id,
            channel["workspace_id"],
            channel["id"],
            channel["property_id"],
            channel["lot_id"],
            channel["adresse_reception"],
            cleaned_message_id,
            sender,
            _clean_text(subject, 500),
            _clean_text(body, 100_000),
            json.dumps(attachments, ensure_ascii=False),
            "associee" if matched_application_id else "recue",
            matched_application_id,
            _clean_text(received_at, 80) if received_at else None,
        ),
    )
    stored_count = 0
    for filename, content_type, content in attachment_payloads or []:
        if _store_inbound_attachment(
            connection,
            workspace_id=channel["workspace_id"],
            inbound_message_id=inbound_id,
            filename=filename,
            content_type=content_type,
            content=content,
        ):
            stored_count += 1
    if matched_application_id:
        connection.execute(
            """
            INSERT INTO candidate_messages(
                id, workspace_id, application_id, property_id, direction,
                sujet, contenu, source, statut, created_at
            ) VALUES (?, ?, ?, ?, 'entrant', ?, ?, 'email', 'recu', datetime('now'))
            """,
            (
                f"message-candidat-{uuid4().hex[:16]}",
                channel["workspace_id"],
                matched_application_id,
                channel["property_id"],
                _clean_text(subject, 160),
                _clean_text(body, 5_000),
            ),
        )
        _promote_inbound_attachments(
            connection,
            workspace_id=channel["workspace_id"],
            inbound_message_id=inbound_id,
            application_id=matched_application_id,
            property_id=channel["property_id"],
        )
    row = connection.execute(
        "SELECT * FROM inbound_application_messages WHERE id = ?",
        (inbound_id,),
    ).fetchone()
    return row, bool(matched_application_id), stored_count


@app.post("/api/internal/candidatures/inbound", response_model=InboundApplicationMessage)
def ingest_inbound_application_email(
    payload: InboundApplicationEmail, request: Request
) -> InboundApplicationMessage:
    """Receive a normalized email from an authorized mailbox provider."""

    expected_token = os.getenv("PIAULE_INBOUND_WEBHOOK_TOKEN", "").strip()
    received_token = request.headers.get("x-piaule-inbound-token", "")
    if not expected_token:
        raise HTTPException(status_code=503, detail="La réception des candidatures n'est pas configurée.")
    if not hmac.compare_digest(received_token, expected_token):
        raise HTTPException(status_code=401, detail="Jeton de réception invalide.")

    with closing(_connect()) as connection:
        row, _, _ = _ingest_inbound_application(
            connection,
            reception_address=payload.adresse_reception,
            message_id=payload.message_id,
            sender=payload.expediteur_email,
            subject=payload.objet,
            body=payload.contenu_texte,
            attachment_names=payload.pieces_jointes,
            received_at=payload.recu_le,
        )
        connection.commit()
    return _inbound_message_from_row(row)


class AssociateInboundApplication(BaseModel):
    candidature_id: str = Field(min_length=1, max_length=100)


@app.put("/api/candidatures/inbox/{message_id}/associer", response_model=InboundApplicationMessage)
def associate_inbound_application(
    message_id: str,
    payload: AssociateInboundApplication,
    owner: Candidate = Depends(current_candidate),
) -> InboundApplicationMessage:
    """Attach an analyzed inbound message to an owner application."""

    with closing(_connect()) as connection:
        message = connection.execute(
            "SELECT * FROM inbound_application_messages WHERE id = ? AND workspace_id = ?",
            (message_id, owner.workspace_id),
        ).fetchone()
        if message is None:
            raise HTTPException(status_code=404, detail="Message entrant introuvable.")
        application = connection.execute(
            "SELECT id FROM owner_applications WHERE id = ? AND workspace_id = ? AND property_id = ?",
            (payload.candidature_id, owner.workspace_id, message["property_id"]),
        ).fetchone()
        if application is None:
            raise HTTPException(status_code=404, detail="La candidature ne correspond pas au bien du message.")
        connection.execute(
            "UPDATE inbound_application_messages SET application_id = ?, statut = 'associee' WHERE id = ? AND workspace_id = ?",
            (payload.candidature_id, message_id, owner.workspace_id),
        )
        _promote_inbound_attachments(
            connection,
            workspace_id=owner.workspace_id,
            inbound_message_id=message_id,
            application_id=payload.candidature_id,
            property_id=message["property_id"],
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM inbound_application_messages WHERE id = ? AND workspace_id = ?",
            (message_id, owner.workspace_id),
        ).fetchone()
    return _inbound_message_from_row(row)


@app.post(
    "/api/internal/candidatures/outbox/traiter",
    response_model=EmailOutboxProcessResult,
)
def process_candidate_email_outbox(request: Request) -> EmailOutboxProcessResult:
    """Send queued candidate messages through the configured SMTP account."""

    _email_internal_token(request)
    if _smtp_settings() is None:
        raise HTTPException(status_code=503, detail="La configuration SMTP est incomplète ou désactivée.")
    try:
        limit = max(1, min(int(os.getenv("PIAULE_EMAIL_BATCH_SIZE", "20")), 100))
    except ValueError:
        limit = 20

    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT m.*, a.candidat_email
            FROM candidate_messages m
            JOIN owner_applications a ON a.id = m.application_id
            WHERE m.direction = 'sortant' AND m.statut = 'a_envoyer'
              AND a.candidat_email <> ''
            ORDER BY m.created_at, m.id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        for row in rows:
            connection.execute(
                """
                UPDATE candidate_messages
                SET statut = 'en_cours', attempts = attempts + 1, last_error = ''
                WHERE id = ? AND statut = 'a_envoyer'
                """,
                (row["id"],),
            )
        connection.commit()

    sent = errors = 0
    for row in rows:
        try:
            recipient = _normalise_email(row["candidat_email"])
            if not EMAIL_RE.fullmatch(recipient):
                raise RuntimeError("Adresse e-mail candidat invalide.")
            _send_smtp_message(recipient, row["sujet"], row["contenu"])
        except Exception as exc:
            errors += 1
            with closing(_connect()) as connection:
                connection.execute(
                    """
                    UPDATE candidate_messages
                    SET statut = 'erreur', last_error = ?
                    WHERE id = ? AND statut = 'en_cours'
                    """,
                    (_clean_text(str(exc), 500), row["id"]),
                )
                connection.commit()
        else:
            sent += 1
            with closing(_connect()) as connection:
                connection.execute(
                    """
                    UPDATE candidate_messages
                    SET statut = 'envoye', sent_at = datetime('now'), last_error = ''
                    WHERE id = ? AND statut = 'en_cours'
                    """,
                    (row["id"],),
                )
                connection.commit()
    return EmailOutboxProcessResult(
        traite=len(rows),
        envoyes=sent,
        erreurs=errors,
        configuration="smtp",
    )


def _known_reception_address(connection: sqlite3.Connection, recipients: list[str]) -> str | None:
    for recipient in recipients:
        normalized = _normalise_email(recipient)
        row = connection.execute(
            """
            SELECT adresse_reception FROM application_channels
            WHERE lower(adresse_reception) = ? AND actif = 1
            """,
            (normalized,),
        ).fetchone()
        if row is not None:
            return row["adresse_reception"]
    return None


@app.post(
    "/api/internal/candidatures/inbox/synchroniser",
    response_model=EmailInboxSyncResult,
)
def synchronize_candidate_email_inbox(request: Request) -> EmailInboxSyncResult:
    """Read unread Hostinger messages and import known application addresses."""

    _email_internal_token(request)
    settings = _imap_settings()
    if settings is None:
        raise HTTPException(status_code=503, detail="La configuration IMAP est incomplète ou désactivée.")
    try:
        limit = max(1, min(int(os.getenv("PIAULE_EMAIL_BATCH_SIZE", "20")), 100))
    except ValueError:
        limit = 20

    mailbox = imaplib.IMAP4_SSL(str(settings["host"]), int(settings["port"]))
    lus = imported = associated = stored = ignored = errors = 0
    try:
        status_code, _ = mailbox.login(str(settings["username"]), str(settings["password"]))
        if status_code != "OK":
            raise RuntimeError("La connexion IMAP Hostinger a été refusée.")
        status_code, _ = mailbox.select(str(settings["folder"]))
        if status_code != "OK":
            raise RuntimeError("La boîte IMAP demandée est inaccessible.")
        status_code, search_data = mailbox.uid("search", None, "UNSEEN")
        if status_code != "OK":
            raise RuntimeError("La recherche des messages non lus a échoué.")
        message_uids = (search_data[0] or b"").split()[:limit]
        for uid in message_uids:
            lus += 1
            try:
                status_code, fetched = mailbox.uid("fetch", uid, "(RFC822)")
                if status_code != "OK":
                    raise RuntimeError("La lecture du message IMAP a échoué.")
                raw_message = next(
                    item[1] for item in fetched if isinstance(item, tuple) and isinstance(item[1], bytes)
                )
                message = BytesParser(policy=policy.default).parsebytes(raw_message)
                recipients = [
                    address
                    for _, address in getaddresses(
                        message.get_all("to", [])
                        + message.get_all("delivered-to", [])
                        + message.get_all("x-original-to", [])
                    )
                    if address
                ]
                with closing(_connect()) as connection:
                    reception_address = _known_reception_address(connection, recipients)
                if reception_address is None:
                    ignored += 1
                    continue
                body, attachments = _extract_email_parts(message)
                message_id = f"imap:{settings['folder']}:{uid.decode(errors='replace')}"
                external_message_id = _decode_email_header(message.get("Message-ID"))
                if external_message_id:
                    message_id = f"{message_id}:{external_message_id}"
                with closing(_connect()) as connection:
                    row, was_associated, stored_count = _ingest_inbound_application(
                        connection,
                        reception_address=reception_address,
                        message_id=message_id,
                        sender=parseaddr(message.get("From", ""))[1],
                        subject=_decode_email_header(message.get("Subject")),
                        body=body,
                        attachment_names=[filename for filename, _, _ in attachments],
                        attachment_payloads=attachments,
                        received_at=_decode_email_header(message.get("Date")),
                    )
                    connection.commit()
                imported += 1
                associated += int(was_associated)
                stored += stored_count
                mailbox.uid("store", uid, "+FLAGS", "(\\Seen)")
            except Exception:
                errors += 1
    finally:
        try:
            mailbox.close()
        except Exception:
            pass
        try:
            mailbox.logout()
        except Exception:
            pass
    return EmailInboxSyncResult(
        lus=lus,
        importes=imported,
        associes=associated,
        pieces_stockees=stored,
        ignores=ignored,
        erreurs=errors,
        configuration="imap",
    )


@app.post(
    "/api/biens/{property_id}/candidatures/{application_id}/dossier-facile/connect",
    response_model=DossierFacileConnectStart,
)
def start_dossier_facile_connection(
    property_id: str,
    application_id: str,
    owner: Candidate = Depends(current_candidate),
) -> DossierFacileConnectStart:
    """Prepare a candidate-consent URL for DossierFacile Connect."""

    if not _dossier_facile_is_configured():
        raise HTTPException(
            status_code=503,
            detail="DossierFacile Connect n'est pas encore configuré avec des identifiants partenaires.",
        )
    state = secrets.token_urlsafe(32)
    state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()
    connection_id = f"dfc-{uuid4().hex[:16]}"
    expires_at = time.time() + DOSSIER_FACILE_STATE_SECONDS
    with closing(_connect()) as connection:
        _owned_property_row(connection, owner, property_id)
        application = connection.execute(
            """
            SELECT * FROM owner_applications
            WHERE id = ? AND property_id = ? AND workspace_id = ?
            """,
            (application_id, property_id, owner.workspace_id),
        ).fetchone()
        if application is None:
            raise HTTPException(status_code=404, detail="Candidature introuvable dans ce bien.")
        connection.execute(
            "DELETE FROM dossier_facile_connections WHERE application_id = ? AND workspace_id = ? AND statut = 'initiee'",
            (application_id, owner.workspace_id),
        )
        connection.execute(
            """
            INSERT INTO dossier_facile_connections(
                id, workspace_id, application_id, state_hash, statut, expires_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'initiee', ?, datetime('now'), datetime('now'))
            """,
            (connection_id, owner.workspace_id, application_id, state_hash, expires_at),
        )
        connection.commit()

    query: dict[str, str] = {
        "client_id": DOSSIER_FACILE_CLIENT_ID,
        "redirect_uri": DOSSIER_FACILE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid",
        "state": state,
    }
    if application["candidat_email"]:
        query["login_hint"] = application["candidat_email"]
    authorization_url = f"{DOSSIER_FACILE_AUTH_URL}?{urlencode(query)}"
    return DossierFacileConnectStart(
        id=connection_id,
        candidature_id=application_id,
        statut="initiee",
        autorisation_url=authorization_url,
        expire_le=int(expires_at),
    )


@app.get("/api/dossier-facile/callback", response_model=None)
def dossier_facile_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse | JSONResponse:
    """Consume the one-time DossierFacile Connect authorization code."""

    if error:
        return JSONResponse(status_code=400, content={"ok": False, "erreur": "Le candidat a annulé le partage DossierFacile."})
    if not code or not state:
        return JSONResponse(status_code=400, content={"ok": False, "erreur": "La réponse DossierFacile est incomplète."})
    state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()
    with closing(_connect()) as connection:
        row = connection.execute(
            """
            SELECT * FROM dossier_facile_connections
            WHERE state_hash = ? AND statut = 'initiee' AND expires_at > ?
            """,
            (state_hash, time.time()),
        ).fetchone()
        if row is None:
            return JSONResponse(status_code=400, content={"ok": False, "erreur": "La demande DossierFacile a expiré ou a déjà été utilisée."})
        connection.execute(
            "UPDATE dossier_facile_connections SET expires_at = 0, updated_at = datetime('now') WHERE id = ?",
            (row["id"],),
        )
        connection.commit()

    try:
        token_payload = _dossier_facile_exchange_code(code)
        access_token = str(token_payload.get("access_token") or "")
        if not access_token:
            raise HTTPException(status_code=502, detail="DossierFacile n'a pas renvoyé de jeton d'accès.")
        profile_payload = _dossier_facile_fetch_profile(access_token)
        connection_status, tenant_id, summary = _dossier_facile_summary(profile_payload)
    except HTTPException as exc:
        with closing(_connect()) as connection:
            connection.execute(
                "UPDATE dossier_facile_connections SET statut = 'erreur', evenement = ?, updated_at = datetime('now') WHERE id = ?",
                (str(exc.detail), row["id"]),
            )
            connection.commit()
        return JSONResponse(status_code=exc.status_code, content={"ok": False, "erreur": str(exc.detail)})

    application_status = None
    if connection_status == "verifiee":
        application_status = "prete"
    elif connection_status == "a_completer":
        application_status = "a_completer"
    with closing(_connect()) as connection:
        connection.execute(
            """
            UPDATE dossier_facile_connections
            SET statut = ?, statut_dossier = ?, evenement = 'PROFILE_RECU', tenant_id = ?,
                resume_json = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                connection_status,
                str(summary.get("statut_dossier", "")),
                tenant_id,
                json.dumps(summary, ensure_ascii=False),
                row["id"],
            ),
        )
        if application_status:
            _set_application_status(
                connection,
                workspace_id=row["workspace_id"],
                application_id=row["application_id"],
                new_status=application_status,
                source="systeme",
                reason=f"Mise à jour DossierFacile : {connection_status}.",
            )
        connection.commit()

    separator = "&" if "?" in FRONTEND_REDIRECT_URI else "?"
    return RedirectResponse(
        f"{FRONTEND_REDIRECT_URI}{separator}dossier_facile={connection_status}&connection_id={row['id']}",
        status_code=303,
    )


@app.get(
    "/api/biens/{property_id}/candidatures/{application_id}/dossier-facile",
    response_model=DossierFacileConnection,
)
def get_dossier_facile_connection(
    property_id: str,
    application_id: str,
    owner: Candidate = Depends(current_candidate),
) -> DossierFacileConnection:
    with closing(_connect()) as connection:
        _owned_property_row(connection, owner, property_id)
        application = connection.execute(
            "SELECT id FROM owner_applications WHERE id = ? AND property_id = ? AND workspace_id = ?",
            (application_id, property_id, owner.workspace_id),
        ).fetchone()
        if application is None:
            raise HTTPException(status_code=404, detail="Candidature introuvable dans ce bien.")
        row = _dossier_facile_connection_for_owner(connection, owner, application_id)
    return _dossier_facile_connection_from_row(row)


@app.post("/api/internal/dossier-facile/webhook")
def dossier_facile_webhook(
    payload: DossierFacileWebhook,
    request: Request,
) -> dict[str, object]:
    """Apply a DossierFacile status event without exposing candidate documents."""

    expected_token = DOSSIER_FACILE_WEBHOOK_TOKEN or os.getenv("PIAULE_DOSSIER_FACILE_WEBHOOK_TOKEN", "").strip()
    received_token = request.headers.get("x-api-key", "")
    if not expected_token:
        raise HTTPException(status_code=503, detail="Le webhook DossierFacile n'est pas configuré.")
    if not hmac.compare_digest(received_token, expected_token):
        raise HTTPException(status_code=401, detail="Clé webhook DossierFacile invalide.")

    tenant_id = str(payload.onTenantId or "")
    event = (payload.partnerCallBackType or "").strip().upper()
    dossier_status = (payload.status or "").strip().upper()
    connection_status = "connectee"
    if event in {"VERIFIED_ACCOUNT"} or dossier_status in {"VALIDATED", "VERIFIED"}:
        connection_status = "verifiee"
    elif event in {"DENIED_ACCOUNT"} or dossier_status in {"DECLINED", "DENIED"}:
        connection_status = "refusee"
    elif dossier_status in {"INCOMPLETE", "TO_PROCESS"}:
        connection_status = "a_completer"
    with closing(_connect()) as connection:
        row = connection.execute(
            """
            SELECT * FROM dossier_facile_connections
            WHERE tenant_id = ? AND tenant_id <> ''
            ORDER BY updated_at DESC LIMIT 1
            """,
            (tenant_id,),
        ).fetchone()
        if row is None:
            return {"ok": True, "ignore": True}
        summary = json.loads(row["resume_json"] or "{}")
        summary.update({"statut_dossier": dossier_status, "evenement": event})
        connection.execute(
            """
            UPDATE dossier_facile_connections
            SET statut = ?, statut_dossier = ?, evenement = ?,
                resume_json = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                connection_status,
                dossier_status,
                event,
                json.dumps(summary, ensure_ascii=False),
                row["id"],
            ),
        )
        if connection_status == "verifiee":
            application_status = "prete"
        elif connection_status == "a_completer":
            application_status = "a_completer"
        elif connection_status == "refusee":
            application_status = "refusee"
        else:
            application_status = None
        if application_status:
            _set_application_status(
                connection,
                workspace_id=row["workspace_id"],
                application_id=row["application_id"],
                new_status=application_status,
                source="systeme",
                reason=f"Événement DossierFacile : {event or dossier_status}.",
            )
        connection.commit()
    return {"ok": True, "connection_id": row["id"], "statut": connection_status}


@app.post(
    "/api/biens/{property_id}/candidatures/{application_id}/lien-candidat",
    response_model=CandidateAccessLink,
)
def create_candidate_access_link(
    property_id: str,
    application_id: str,
    owner: Candidate = Depends(current_candidate),
) -> CandidateAccessLink:
    """Create a revocable, expiring magic link for the candidate portal."""

    with closing(_connect()) as connection:
        _application_for_owner(connection, owner, property_id, application_id)
        link_id, token, expires_at = _issue_candidate_access_link(
            connection,
            workspace_id=owner.workspace_id,
            application_id=application_id,
            property_id=property_id,
        )
        connection.commit()
    return CandidateAccessLink(
        id=link_id,
        candidature_id=application_id,
        url=_candidate_access_url(token),
        expire_le=int(expires_at),
        actif=True,
    )


@app.get("/api/candidature-acces/{token}", response_model=CandidatePortalView)
def candidate_portal_view(token: str) -> CandidatePortalView:
    """Return only the information needed by a candidate's temporary portal."""

    access = _active_candidate_access_row(token)
    with closing(_connect()) as connection:
        completeness = _application_completeness(
            connection, access["workspace_id"], access["application_id"]
        )
    return CandidatePortalView(
        candidature_id=access["application_id"],
        candidat_prenom=access["candidat_prenom"],
        bien_nom=access["bien_nom"],
        statut_candidature=access["candidature_statut"],
        completude=completeness,
    )


@app.get("/api/candidature-acces/{token}/visites", response_model=list[CandidateVisit])
def candidate_portal_visits(token: str) -> list[CandidateVisit]:
    """Show only the candidate's own proposed or confirmed visits."""

    access = _active_candidate_access_row(token)
    with closing(_connect()) as connection:
        rows = connection.execute(
            _visit_query()
            + " WHERE v.workspace_id = ? AND v.application_id = ? "
            + "AND v.status IN ('proposee', 'confirmee') ORDER BY s.starts_at",
            (access["workspace_id"], access["application_id"]),
        ).fetchall()
    return [_candidate_visit_from_row(row) for row in rows]


@app.post(
    "/api/candidature-acces/{token}/visites/{visit_id}/reponse",
    response_model=CandidateVisit,
)
def candidate_portal_visit_response(
    token: str,
    visit_id: str,
    payload: CandidateVisitResponse,
) -> CandidateVisit:
    """Accept or refuse a proposed slot from the candidate portal."""

    access = _active_candidate_access_row(token)
    reason = _clean_text(payload.motif, 500)
    with closing(_connect()) as connection:
        row = connection.execute(
            _visit_query()
            + " WHERE v.id = ? AND v.workspace_id = ? AND v.application_id = ?",
            (visit_id, access["workspace_id"], access["application_id"]),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Visite introuvable dans ce dossier.")
        if row["status"] != "proposee":
            raise HTTPException(status_code=409, detail="Cette proposition de visite a déjà reçu une réponse.")
        if payload.accepte:
            connection.execute(
                "UPDATE visits SET status = 'confirmee', source = 'candidat', reason = ?, updated_at = datetime('now') WHERE id = ?",
                (reason or "Créneau accepté par le candidat.", visit_id),
            )
            _set_application_status(
                connection,
                workspace_id=access["workspace_id"],
                application_id=access["application_id"],
                new_status="visite_confirmee",
                source="candidat",
                reason=reason or "Visite acceptée par le candidat.",
            )
        else:
            connection.execute(
                "UPDATE visits SET status = 'refusee', source = 'candidat', reason = ?, updated_at = datetime('now') WHERE id = ?",
                (reason or "Créneau refusé par le candidat.", visit_id),
            )
            connection.execute("UPDATE visit_slots SET status = 'libre' WHERE id = ?", (row["slot_id"],))
            _set_application_status(
                connection,
                workspace_id=access["workspace_id"],
                application_id=access["application_id"],
                new_status="prete",
                source="candidat",
                reason=reason or "Le candidat a refusé le créneau.",
            )
        connection.commit()
        updated = connection.execute(
            _visit_query() + " WHERE v.id = ? AND v.workspace_id = ?",
            (visit_id, access["workspace_id"]),
        ).fetchone()
    return _candidate_visit_from_row(updated)


@app.post("/api/candidature-acces/{token}/messages", response_model=CandidateMessage, status_code=201)
def candidate_portal_message(
    token: str,
    payload: CandidateMessageCreate,
) -> CandidateMessage:
    """Receive a candidate reply through the expiring portal link."""

    access = _active_candidate_access_row(token)
    message_id = f"message-candidat-{uuid4().hex[:16]}"
    with closing(_connect()) as connection:
        connection.execute(
            """
            INSERT INTO candidate_messages(
                id, workspace_id, application_id, property_id, direction,
                sujet, contenu, source, statut, created_at
            ) VALUES (?, ?, ?, ?, 'entrant', ?, ?, 'portail_candidat', 'recu', datetime('now'))
            """,
            (
                message_id,
                access["workspace_id"],
                access["application_id"],
                access["property_id"],
                _clean_text(payload.sujet, 160),
                _clean_text(payload.contenu, 5_000),
            ),
        )
        connection.commit()
        row = connection.execute("SELECT * FROM candidate_messages WHERE id = ?", (message_id,)).fetchone()
    return _candidate_message_from_row(row)


@app.post(
    "/api/candidature-acces/{token}/pieces",
    response_model=ApplicationDocument,
    status_code=201,
)
async def candidate_portal_upload_document(
    token: str,
    nom: str = Form(...),
    type: str = Form(...),
    date_expiration: str = Form(""),
    file: UploadFile = File(...),
) -> ApplicationDocument:
    """Accept a document from a candidate with a valid temporary link."""

    access = _active_candidate_access_row(token)
    document_type = _clean_text(type, 60)
    if document_type not in set(ApplicationDocumentType.__args__):
        raise HTTPException(status_code=422, detail="Type de pièce non pris en charge.")
    document_name = _clean_text(nom, 120)
    if len(document_name) < 2:
        raise HTTPException(status_code=400, detail="Nomme la pièce avant de la déposer.")
    expiration = _clean_text(date_expiration, 20) or None
    if expiration:
        try:
            date.fromisoformat(expiration)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="La date d'expiration doit être au format AAAA-MM-JJ.") from exc
    extension = _document_extension(file.filename or "", file.content_type or "")
    if extension is None:
        raise HTTPException(status_code=415, detail="Format accepté : PDF, JPG ou PNG.")
    content = await file.read(MAX_DOCUMENT_BYTES + 1)
    if len(content) > MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=413, detail="La pièce ne doit pas dépasser 100 Mo.")
    document_id = f"application-doc-{uuid4().hex}"
    stored_filename = f"{document_id}.{extension}"
    original_filename = _clean_text(file.filename or f"piece.{extension}", 180)
    digest = hashlib.sha256(content).hexdigest()
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIRECTORY / stored_filename).write_bytes(content)
    try:
        with closing(_connect()) as connection:
            connection.execute(
                """
                INSERT INTO application_documents(
                    id, workspace_id, application_id, property_id, document_type,
                    nom, original_filename, stored_filename, content_type, size_bytes,
                    sha256, provenance, statut, date_expiration, note_verification,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'portail_candidat', 'recu', ?, '', datetime('now'), datetime('now'))
                """,
                (
                    document_id,
                    access["workspace_id"],
                    access["application_id"],
                    access["property_id"],
                    document_type,
                    document_name,
                    original_filename,
                    stored_filename,
                    file.content_type or "application/octet-stream",
                    len(content),
                    digest,
                    expiration,
                ),
            )
            inserted = connection.execute(
                "SELECT * FROM application_documents WHERE id = ?",
                (document_id,),
            ).fetchone()
            _document_preflight(connection, inserted)
            _refresh_application_status(connection, access["workspace_id"], access["application_id"])
            connection.commit()
            row = connection.execute("SELECT * FROM application_documents WHERE id = ?", (document_id,)).fetchone()
    except Exception:
        (UPLOAD_DIRECTORY / stored_filename).unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return _application_document_from_row(row)


def _application_for_owner(
    connection: sqlite3.Connection, owner: Candidate, property_id: str, application_id: str
) -> sqlite3.Row:
    _owned_property_row(connection, owner, property_id)
    row = connection.execute(
        """
        SELECT * FROM owner_applications
        WHERE id = ? AND property_id = ? AND workspace_id = ?
        """,
        (application_id, property_id, owner.workspace_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Candidature introuvable dans ce bien.")
    return row


@app.get(
    "/api/biens/{property_id}/candidatures/{application_id}/messages",
    response_model=list[CandidateMessage],
)
def list_candidate_messages(
    property_id: str,
    application_id: str,
    owner: Candidate = Depends(current_candidate),
) -> list[CandidateMessage]:
    with closing(_connect()) as connection:
        _application_for_owner(connection, owner, property_id, application_id)
        rows = connection.execute(
            """
            SELECT * FROM candidate_messages
            WHERE workspace_id = ? AND property_id = ? AND application_id = ?
            ORDER BY created_at, id
            """,
            (owner.workspace_id, property_id, application_id),
        ).fetchall()
    return [_candidate_message_from_row(row) for row in rows]


@app.post(
    "/api/biens/{property_id}/candidatures/{application_id}/messages",
    response_model=CandidateMessage,
    status_code=201,
)
def create_owner_candidate_message(
    property_id: str,
    application_id: str,
    payload: OwnerCandidateMessageCreate,
    owner: Candidate = Depends(current_candidate),
) -> CandidateMessage:
    """Queue a message for the real email provider to send to the candidate."""

    message_id = f"message-candidat-{uuid4().hex[:16]}"
    with closing(_connect()) as connection:
        application = _application_for_owner(connection, owner, property_id, application_id)
        connection.execute(
            """
            INSERT INTO candidate_messages(
                id, workspace_id, application_id, property_id, direction,
                sujet, contenu, source, statut, created_at
            ) VALUES (?, ?, ?, ?, 'sortant', ?, ?, 'proprietaire', 'a_envoyer', datetime('now'))
            """,
            (
                message_id,
                owner.workspace_id,
                application_id,
                property_id,
                _clean_text(payload.sujet, 160),
                _clean_text(payload.contenu, 5_000),
            ),
        )
        connection.commit()
        row = connection.execute("SELECT * FROM candidate_messages WHERE id = ?", (message_id,)).fetchone()
    return _candidate_message_from_row(row)


@app.get(
    "/api/biens/{property_id}/candidatures/{application_id}/pieces",
    response_model=list[ApplicationDocument],
)
def list_application_documents(
    property_id: str,
    application_id: str,
    owner: Candidate = Depends(current_candidate),
) -> list[ApplicationDocument]:
    with closing(_connect()) as connection:
        _application_for_owner(connection, owner, property_id, application_id)
        rows = connection.execute(
            """
            SELECT * FROM application_documents
            WHERE workspace_id = ? AND property_id = ? AND application_id = ?
            ORDER BY created_at DESC, id
            """,
            (owner.workspace_id, property_id, application_id),
        ).fetchall()
    return [_application_document_from_row(row) for row in rows]


@app.post(
    "/api/biens/{property_id}/candidatures/{application_id}/pieces",
    response_model=ApplicationDocument,
    status_code=201,
)
async def upload_application_document(
    property_id: str,
    application_id: str,
    nom: str = Form(...),
    type: str = Form(...),
    provenance: str = Form("portail_candidat"),
    date_expiration: str = Form(""),
    file: UploadFile = File(...),
    owner: Candidate = Depends(current_candidate),
) -> ApplicationDocument:
    """Store one private candidate document and attach it to its application."""

    document_type = _clean_text(type, 60)
    allowed_types = set(ApplicationDocumentType.__args__)
    if document_type not in allowed_types:
        raise HTTPException(status_code=422, detail="Type de pièce non pris en charge.")
    if provenance not in set(ApplicationDocumentProvenance.__args__):
        raise HTTPException(status_code=422, detail="Provenance de pièce non prise en charge.")
    document_name = _clean_text(nom, 120)
    if len(document_name) < 2:
        raise HTTPException(status_code=400, detail="Nomme la pièce avant de la déposer.")
    expiration = _clean_text(date_expiration, 20) or None
    if expiration:
        try:
            date.fromisoformat(expiration)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="La date d'expiration doit être au format AAAA-MM-JJ.") from exc
    extension = _document_extension(file.filename or "", file.content_type or "")
    if extension is None:
        raise HTTPException(status_code=415, detail="Format accepté : PDF, JPG ou PNG.")
    content = await file.read(MAX_DOCUMENT_BYTES + 1)
    if len(content) > MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=413, detail="La pièce ne doit pas dépasser 100 Mo.")

    document_id = f"application-doc-{uuid4().hex}"
    stored_filename = f"{document_id}.{extension}"
    original_filename = _clean_text(file.filename or f"piece.{extension}", 180)
    digest = hashlib.sha256(content).hexdigest()
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIRECTORY / stored_filename).write_bytes(content)
    try:
        with closing(_connect()) as connection:
            _application_for_owner(connection, owner, property_id, application_id)
            connection.execute(
                """
                INSERT INTO application_documents(
                    id, workspace_id, application_id, property_id, document_type,
                    nom, original_filename, stored_filename, content_type, size_bytes,
                    sha256, provenance, statut, date_expiration, note_verification,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'recu', ?, '', datetime('now'), datetime('now'))
                """,
                (
                    document_id,
                    owner.workspace_id,
                    application_id,
                    property_id,
                    document_type,
                    document_name,
                    original_filename,
                    stored_filename,
                    file.content_type or "application/octet-stream",
                    len(content),
                    digest,
                    provenance,
                    expiration,
                ),
            )
            inserted = connection.execute(
                "SELECT * FROM application_documents WHERE id = ?",
                (document_id,),
            ).fetchone()
            _document_preflight(connection, inserted)
            _refresh_application_status(connection, owner.workspace_id, application_id)
            connection.commit()
            row = connection.execute(
                "SELECT * FROM application_documents WHERE id = ?",
                (document_id,),
            ).fetchone()
    except Exception:
        (UPLOAD_DIRECTORY / stored_filename).unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return _application_document_from_row(row)


@app.put(
    "/api/biens/{property_id}/candidatures/{application_id}/pieces/{document_id}/verification",
    response_model=ApplicationDocument,
)
def verify_application_document(
    property_id: str,
    application_id: str,
    document_id: str,
    payload: ApplicationDocumentVerificationUpdate,
    owner: Candidate = Depends(current_candidate),
) -> ApplicationDocument:
    """Set a deterministic review status for one candidate document."""

    expiration = _clean_text(payload.date_expiration, 20) if payload.date_expiration else None
    if expiration:
        try:
            date.fromisoformat(expiration)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="La date d'expiration doit être au format AAAA-MM-JJ.") from exc
    note = _clean_text(payload.note_verification, 2000)
    with closing(_connect()) as connection:
        _application_for_owner(connection, owner, property_id, application_id)
        _owned_application_document_row(connection, owner, property_id, application_id, document_id)
        connection.execute(
            """
            UPDATE application_documents
            SET statut = ?, date_expiration = ?, note_verification = ?,
                verification_level = ?, anomalies_json = '[]', duplicate_of = NULL,
                checked_at = ?, verification_engine_version = 'human-review-v1',
                updated_at = datetime('now')
            WHERE id = ? AND workspace_id = ?
            """,
            (
                payload.statut,
                expiration,
                note,
                "revue_humaine" if payload.statut == "valide" else "non_verifie",
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                document_id,
                owner.workspace_id,
            ),
        )
        _refresh_application_status(connection, owner.workspace_id, application_id)
        connection.commit()
        row = _owned_application_document_row(connection, owner, property_id, application_id, document_id)
    return _application_document_from_row(row)


@app.post(
    "/api/biens/{property_id}/candidatures/{application_id}/pieces/{document_id}/analyser",
    response_model=ApplicationDocumentAnalysisResult,
)
def analyze_application_document(
    property_id: str,
    application_id: str,
    document_id: str,
    owner: Candidate = Depends(current_candidate),
) -> ApplicationDocumentAnalysisResult:
    """Run local integrity, expiry and duplicate checks on one document."""

    with closing(_connect()) as connection:
        _application_for_owner(connection, owner, property_id, application_id)
        row = _owned_application_document_row(connection, owner, property_id, application_id, document_id)
        updated_row, check_row = _document_preflight(connection, row)
        _refresh_application_status(connection, owner.workspace_id, application_id)
        connection.commit()
    return ApplicationDocumentAnalysisResult(
        document=_application_document_from_row(updated_row),
        dernier_controle=_application_document_check_from_row(check_row),
    )


@app.get(
    "/api/biens/{property_id}/candidatures/{application_id}/pieces/{document_id}/controles",
    response_model=list[ApplicationDocumentCheck],
)
def list_application_document_checks(
    property_id: str,
    application_id: str,
    document_id: str,
    owner: Candidate = Depends(current_candidate),
) -> list[ApplicationDocumentCheck]:
    """List the technical checks performed on one document."""

    with closing(_connect()) as connection:
        _application_for_owner(connection, owner, property_id, application_id)
        _owned_application_document_row(connection, owner, property_id, application_id, document_id)
        rows = connection.execute(
            """
            SELECT * FROM application_document_checks
            WHERE workspace_id = ? AND application_id = ? AND document_id = ?
            ORDER BY rowid
            """,
            (owner.workspace_id, application_id, document_id),
        ).fetchall()
    return [_application_document_check_from_row(row) for row in rows]


def _verification_source_allowed(policy: str, source: str) -> bool:
    return source in VERIFICATION_POLICY_SOURCES.get(policy, [])


@app.post(
    "/api/biens/{property_id}/candidatures/{application_id}/pieces/{document_id}/verifications",
    response_model=ApplicationVerificationRequest,
    status_code=201,
)
def create_application_verification_request(
    property_id: str,
    application_id: str,
    document_id: str,
    payload: ApplicationVerificationRequestCreate,
    owner: Candidate = Depends(current_candidate),
) -> ApplicationVerificationRequest:
    """Create a consent-gated verification request without claiming an external result."""

    with closing(_connect()) as connection:
        property_row = _owned_property_row(connection, owner, property_id)
        _application_for_owner(connection, owner, property_id, application_id)
        _owned_application_document_row(connection, owner, property_id, application_id, document_id)
        policy = property_row["verification_policy"] or "standard"
        if not _verification_source_allowed(policy, payload.source):
            raise HTTPException(
                status_code=409,
                detail=f"La source {payload.source} n'est pas incluse dans la politique {policy} de ce bien.",
            )
        existing = connection.execute(
            """
            SELECT * FROM application_verification_requests
            WHERE workspace_id = ? AND application_id = ? AND document_id = ?
              AND source = ? AND status IN ('en_attente_consentement', 'en_attente_source')
            ORDER BY created_at DESC LIMIT 1
            """,
            (owner.workspace_id, application_id, document_id, payload.source),
        ).fetchone()
        if existing is not None:
            return _application_verification_request_from_row(existing)
        request_id = f"verification-request-{uuid4().hex[:16]}"
        motif = _clean_text(payload.motif, 500)
        connection.execute(
            """
            INSERT INTO application_verification_requests(
                id, workspace_id, application_id, document_id, source, status,
                motif, evidence_json, result_summary, expires_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'en_attente_consentement', ?, '{}', '',
                      datetime('now', '+30 days'), datetime('now'), datetime('now'))
            """,
            (request_id, owner.workspace_id, application_id, document_id, payload.source, motif),
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM application_verification_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
    return _application_verification_request_from_row(row)


@app.get(
    "/api/biens/{property_id}/candidatures/{application_id}/verifications",
    response_model=list[ApplicationVerificationRequest],
)
def list_application_verification_requests(
    property_id: str,
    application_id: str,
    owner: Candidate = Depends(current_candidate),
) -> list[ApplicationVerificationRequest]:
    with closing(_connect()) as connection:
        _application_for_owner(connection, owner, property_id, application_id)
        rows = connection.execute(
            """
            SELECT * FROM application_verification_requests
            WHERE workspace_id = ? AND application_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (owner.workspace_id, application_id),
        ).fetchall()
    return [_application_verification_request_from_row(row) for row in rows]


class CandidateVerificationConsent(BaseModel):
    accepte: bool


class ExternalVerificationResult(BaseModel):
    statut: Literal["confirmee", "non_confirmee"]
    resultat: str = Field(min_length=1, max_length=2000)
    preuve: dict[str, object] = Field(default_factory=dict)
    reference_externe: str = Field(default="", max_length=300)


@app.post(
    "/api/candidature-acces/{token}/verifications/{request_id}/consentement",
    response_model=ApplicationVerificationRequest,
)
def candidate_verification_consent(
    token: str,
    request_id: str,
    payload: CandidateVerificationConsent,
) -> ApplicationVerificationRequest:
    """Record candidate consent; an external provider must still return the proof."""

    access = _active_candidate_access_row(token)
    with closing(_connect()) as connection:
        row = connection.execute(
            """
            SELECT * FROM application_verification_requests
            WHERE id = ? AND workspace_id = ? AND application_id = ?
            """,
            (request_id, access["workspace_id"], access["application_id"]),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Demande de vérification introuvable.")
        if row["status"] not in {"en_attente_consentement", "en_attente_source"}:
            return _application_verification_request_from_row(row)
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if payload.accepte:
            status_value = "en_attente_source"
            evidence = {"consentement": "candidat_portail", "consenti_le": now}
            result = "Consentement reçu ; preuve externe attendue."
        else:
            status_value = "annulee"
            evidence = {"consentement": "refuse"}
            result = "Le candidat n'a pas autorisé cette vérification."
        connection.execute(
            """
            UPDATE application_verification_requests
            SET status = ?, consent_given_at = ?, evidence_json = ?, result_summary = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                status_value,
                now if payload.accepte else None,
                json.dumps(evidence, ensure_ascii=False),
                result,
                request_id,
            ),
        )
        connection.commit()
        updated = connection.execute(
            "SELECT * FROM application_verification_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
    return _application_verification_request_from_row(updated)


@app.post("/api/internal/verifications/{request_id}/result", response_model=ApplicationVerificationRequest)
def apply_external_verification_result(
    request_id: str,
    payload: ExternalVerificationResult,
    request: Request,
) -> ApplicationVerificationRequest:
    """Store a provider result; this route never invents a source confirmation."""

    if not VERIFICATION_INTERNAL_TOKEN:
        raise HTTPException(status_code=503, detail="Le canal de vérification externe n'est pas configuré.")
    received_token = request.headers.get("x-piaule-verification-token", "")
    if not hmac.compare_digest(received_token, VERIFICATION_INTERNAL_TOKEN):
        raise HTTPException(status_code=401, detail="Jeton de vérification externe invalide.")
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT * FROM application_verification_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Demande de vérification introuvable.")
        if row["status"] not in {"en_attente_source", "en_attente_consentement"}:
            return _application_verification_request_from_row(row)
        if row["source"] != "revue_humaine" and row["status"] != "en_attente_source":
            raise HTTPException(status_code=409, detail="Le consentement du candidat est requis avant cette vérification.")
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        evidence = dict(payload.preuve)
        evidence["source"] = row["source"]
        evidence["recu_le"] = now
        document_level = (
            "source_officielle"
            if row["source"] in {"dossier_facile", "france_identite", "dgfip"}
            else "source_partenaire"
        )
        document_status = "valide" if payload.statut == "confirmee" else "a_corriger"
        connection.execute(
            """
            UPDATE application_verification_requests
            SET status = ?, evidence_json = ?, result_summary = ?,
                external_reference_hash = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                payload.statut,
                json.dumps(evidence, ensure_ascii=False),
                _clean_text(payload.resultat, 2000),
                hashlib.sha256(payload.reference_externe.encode("utf-8")).hexdigest()
                if payload.reference_externe
                else "",
                request_id,
            ),
        )
        connection.execute(
            """
            UPDATE application_documents
            SET statut = ?, verification_level = ?, note_verification = ?,
                checked_at = ?, verification_engine_version = ?, updated_at = datetime('now')
            WHERE id = ? AND workspace_id = ?
            """,
            (
                document_status,
                document_level if payload.statut == "confirmee" else "non_verifie",
                _clean_text(payload.resultat, 2000),
                now,
                f"provider-{row['source']}-v1",
                row["document_id"],
                row["workspace_id"],
            ),
        )
        _refresh_application_status(connection, row["workspace_id"], row["application_id"])
        connection.commit()
        updated = connection.execute(
            "SELECT * FROM application_verification_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
    return _application_verification_request_from_row(updated)


@app.get(
    "/api/biens/{property_id}/candidatures/{application_id}/completude",
    response_model=ApplicationCompleteness,
)
def get_application_completeness(
    property_id: str,
    application_id: str,
    owner: Candidate = Depends(current_candidate),
) -> ApplicationCompleteness:
    with closing(_connect()) as connection:
        _application_for_owner(connection, owner, property_id, application_id)
        return _application_completeness(connection, owner.workspace_id, application_id)


@app.post(
    "/api/biens/{property_id}/candidatures/{application_id}/verifier",
    response_model=ApplicationCompleteness,
)
def refresh_application_completeness(
    property_id: str,
    application_id: str,
    owner: Candidate = Depends(current_candidate),
) -> ApplicationCompleteness:
    """Recompute completeness and synchronize the safe application status."""

    with closing(_connect()) as connection:
        _application_for_owner(connection, owner, property_id, application_id)
        result = _refresh_application_status(connection, owner.workspace_id, application_id)
        connection.commit()
    return result


@app.post(
    "/api/biens/{property_id}/candidatures/{application_id}/agent/relancer-completude",
    response_model=CandidateCompletenessFollowUp,
    status_code=201,
)
def agent_request_missing_documents(
    property_id: str,
    application_id: str,
    owner: Candidate = Depends(current_candidate),
) -> CandidateCompletenessFollowUp:
    """Queue one safe, idempotent request for missing candidate documents.

    The action may ask for documents but never changes the application to
    ``refusee``. That decision remains an explicit owner action.
    """

    with closing(_connect()) as connection:
        application = _application_for_owner(connection, owner, property_id, application_id)
        completeness = _application_completeness(connection, owner.workspace_id, application_id)
        missing_types = _completeness_followup_types(completeness)
        created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if not missing_types:
            return CandidateCompletenessFollowUp(
                id=f"no-followup-{application_id}",
                candidature_id=application_id,
                pieces_demandees=[],
                statut="aucune_piece_manquante",
                created_at=created_at,
            )

        if not application["candidat_email"]:
            return CandidateCompletenessFollowUp(
                id=f"no-email-{application_id}",
                candidature_id=application_id,
                pieces_demandees=missing_types,
                statut="sans_email",
                created_at=created_at,
            )

        missing_signature = hashlib.sha256(
            ",".join(missing_types).encode("utf-8")
        ).hexdigest()
        existing = connection.execute(
            """
            SELECT * FROM candidate_completeness_followups
            WHERE workspace_id = ? AND application_id = ? AND missing_signature = ?
            """,
            (owner.workspace_id, application_id, missing_signature),
        ).fetchone()
        if existing is not None:
            return _candidate_followup_from_row(existing)

        _, token, _ = _issue_candidate_access_link(
            connection,
            workspace_id=owner.workspace_id,
            application_id=application_id,
            property_id=property_id,
        )
        deposit_link = _candidate_access_url(token)
        message_id = f"message-candidat-{uuid4().hex[:16]}"
        labels = [DOCUMENT_TYPE_LABELS[document_type] for document_type in missing_types]
        requested_lines = "\n".join(f"- {label}" for label in labels)
        message_body = (
            f"Bonjour {application['candidat_prenom']},\n\n"
            "Pour poursuivre votre candidature, merci de transmettre uniquement les pièces suivantes :\n"
            f"{requested_lines}\n\n"
            f"Déposez-les ici : {deposit_link}\n\n"
            "Aucun autre document n'est nécessaire à ce stade. Nous vous recontacterons si une vérification "
            "fait apparaître une incohérence."
        )
        connection.execute(
            """
            INSERT INTO candidate_messages(
                id, workspace_id, application_id, property_id, direction,
                sujet, contenu, source, statut, created_at
            ) VALUES (?, ?, ?, ?, 'sortant', ?, ?, 'agent', 'a_envoyer', datetime('now'))
            """,
            (
                message_id,
                owner.workspace_id,
                application_id,
                property_id,
                "Pièces nécessaires pour votre candidature",
                message_body,
            ),
        )
        followup_id = f"candidate-followup-{uuid4().hex[:16]}"
        connection.execute(
            """
            INSERT INTO candidate_completeness_followups(
                id, workspace_id, application_id, property_id,
                missing_signature, missing_types_json, message_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                followup_id,
                owner.workspace_id,
                application_id,
                property_id,
                missing_signature,
                json.dumps(missing_types, ensure_ascii=False),
                message_id,
            ),
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM candidate_completeness_followups WHERE id = ?",
            (followup_id,),
        ).fetchone()
    return _candidate_followup_from_row(row, status="a_envoyer", link=deposit_link)


@app.get("/api/biens/{property_id}/candidatures", response_model=list[OwnerApplication])
def list_property_applications(
    property_id: str, owner: Candidate = Depends(current_candidate)
) -> list[OwnerApplication]:
    """List applications attached to one owned property."""

    with closing(_connect()) as connection:
        _owned_property_row(connection, owner, property_id)
        rows = connection.execute(
            _application_query()
            + " WHERE a.property_id = ? AND a.workspace_id = ? ORDER BY a.recue_le DESC, a.id",
            (property_id, owner.workspace_id),
        ).fetchall()
    return [_application_from_row(row) for row in rows]


@app.post("/api/biens/{property_id}/candidatures", response_model=OwnerApplication, status_code=201)
def create_property_application(
    property_id: str,
    payload: OwnerApplicationCreate,
    owner: Candidate = Depends(current_candidate),
) -> OwnerApplication:
    """Receive an application and attach it to an owned property and optional lot."""

    cleaned = _clean_application_create(payload)
    application_id = f"candidature-{uuid4().hex[:16]}"
    duplicate_key = _application_duplicate_key(property_id, cleaned.lot_id, cleaned.candidat_email)
    with closing(_connect()) as connection:
        _owned_property_row(connection, owner, property_id)
        if cleaned.lot_id:
            _owned_lot_row(connection, owner, property_id, cleaned.lot_id)
        existing = None
        if duplicate_key:
            existing = connection.execute(
                "SELECT id FROM owner_applications WHERE workspace_id = ? AND duplicate_key = ?",
                (owner.workspace_id, duplicate_key),
            ).fetchone()
        duplicate = existing is not None
        connection.execute(
            """
            INSERT INTO owner_applications(
                id, workspace_id, property_id, lot_id, candidat_prenom, candidat_nom,
                candidat_email, candidat_telephone, source, reference_source, statut,
                statut_motif, statut_source, duplicate_key, doublon_possible,
                notes_privees, recue_le, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', 'proprietaire', ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                application_id,
                owner.workspace_id,
                property_id,
                cleaned.lot_id,
                cleaned.candidat_prenom,
                cleaned.candidat_nom,
                cleaned.candidat_email,
                cleaned.candidat_telephone,
                cleaned.source,
                cleaned.reference_source,
                cleaned.statut,
                duplicate_key,
                int(duplicate),
                cleaned.notes_privees,
            ),
        )
        _record_application_status_event(
            connection,
            workspace_id=owner.workspace_id,
            application_id=application_id,
            property_id=property_id,
            previous_status="",
            new_status=cleaned.statut,
            source="proprietaire",
            reason="Candidature créée.",
        )
        if existing is not None:
            connection.execute(
                "UPDATE owner_applications SET doublon_possible = 1 WHERE id = ?",
                (existing["id"],),
            )
        connection.commit()
        row = _owned_application_row(connection, owner, application_id)
    return _application_from_row(row)


@app.get("/api/biens/{property_id}/candidatures/{application_id}", response_model=OwnerApplication)
def get_property_application(
    property_id: str,
    application_id: str,
    owner: Candidate = Depends(current_candidate),
) -> OwnerApplication:
    with closing(_connect()) as connection:
        _owned_property_row(connection, owner, property_id)
        row = connection.execute(
            _application_query()
            + " WHERE a.id = ? AND a.property_id = ? AND a.workspace_id = ?",
            (application_id, property_id, owner.workspace_id),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Candidature introuvable dans ce bien.")
    return _application_from_row(row)


@app.get(
    "/api/biens/{property_id}/candidatures/{application_id}/historique",
    response_model=list[ApplicationStatusEvent],
)
def list_application_status_history(
    property_id: str,
    application_id: str,
    owner: Candidate = Depends(current_candidate),
) -> list[ApplicationStatusEvent]:
    """Return the explainable status history of one application."""

    with closing(_connect()) as connection:
        _application_for_owner(connection, owner, property_id, application_id)
        rows = connection.execute(
            """
            SELECT * FROM application_status_history
            WHERE workspace_id = ? AND property_id = ? AND application_id = ?
            ORDER BY rowid
            """,
            (owner.workspace_id, property_id, application_id),
        ).fetchall()
    return [_application_status_event_from_row(row) for row in rows]


@app.post(
    "/api/biens/{property_id}/candidatures/{application_id}/statut",
    response_model=OwnerApplication,
)
def transition_application_status(
    property_id: str,
    application_id: str,
    payload: ApplicationStatusUpdate,
    owner: Candidate = Depends(current_candidate),
) -> OwnerApplication:
    """Apply one owner-approved transition and record its reason."""

    with closing(_connect()) as connection:
        _application_for_owner(connection, owner, property_id, application_id)
        row = _set_application_status(
            connection,
            workspace_id=owner.workspace_id,
            application_id=application_id,
            new_status=payload.statut,
            source="proprietaire",
            reason=payload.motif,
        )
        connection.commit()
        row = _owned_application_row(connection, owner, application_id)
    return _application_from_row(row)


@app.put("/api/biens/{property_id}/candidatures/{application_id}", response_model=OwnerApplication)
def update_property_application(
    property_id: str,
    application_id: str,
    payload: OwnerApplicationUpdate,
    owner: Candidate = Depends(current_candidate),
) -> OwnerApplication:
    """Update a candidate application while keeping it in the same workspace."""

    cleaned = _clean_application_update(payload)
    with closing(_connect()) as connection:
        _owned_property_row(connection, owner, property_id)
        current = connection.execute(
            "SELECT * FROM owner_applications WHERE id = ? AND property_id = ? AND workspace_id = ?",
            (application_id, property_id, owner.workspace_id),
        ).fetchone()
        if current is None:
            raise HTTPException(status_code=404, detail="Candidature introuvable dans ce bien.")

        lot_id = cleaned.lot_id if cleaned.lot_id is not None else current["lot_id"]
        if lot_id:
            _owned_lot_row(connection, owner, property_id, lot_id)
        candidat_prenom = cleaned.candidat_prenom if cleaned.candidat_prenom is not None else current["candidat_prenom"]
        candidat_nom = cleaned.candidat_nom if cleaned.candidat_nom is not None else current["candidat_nom"]
        candidat_email = cleaned.candidat_email if cleaned.candidat_email is not None else current["candidat_email"]
        candidat_telephone = cleaned.candidat_telephone if cleaned.candidat_telephone is not None else current["candidat_telephone"]
        source = cleaned.source if cleaned.source is not None else current["source"]
        reference_source = cleaned.reference_source if cleaned.reference_source is not None else current["reference_source"]
        statut = cleaned.statut if cleaned.statut is not None else current["statut"]
        notes_privees = cleaned.notes_privees if cleaned.notes_privees is not None else current["notes_privees"]
        duplicate_key = _application_duplicate_key(property_id, lot_id, candidat_email)
        duplicate = False
        if duplicate_key:
            duplicate = connection.execute(
                """
                SELECT 1 FROM owner_applications
                WHERE workspace_id = ? AND duplicate_key = ? AND id <> ?
                LIMIT 1
                """,
                (owner.workspace_id, duplicate_key, application_id),
            ).fetchone() is not None
        connection.execute(
            """
            UPDATE owner_applications SET
                lot_id = ?, candidat_prenom = ?, candidat_nom = ?, candidat_email = ?,
                candidat_telephone = ?, source = ?, reference_source = ?, statut = ?,
                duplicate_key = ?, doublon_possible = ?, notes_privees = ?, updated_at = datetime('now')
            WHERE id = ? AND property_id = ? AND workspace_id = ?
            """,
            (
                lot_id,
                candidat_prenom,
                candidat_nom,
                candidat_email,
                candidat_telephone,
                source,
                reference_source,
                current["statut"],
                duplicate_key,
                int(duplicate or bool(current["doublon_possible"])),
                notes_privees,
                application_id,
                property_id,
                owner.workspace_id,
            ),
        )
        if duplicate:
            connection.execute(
                "UPDATE owner_applications SET doublon_possible = 1 WHERE workspace_id = ? AND duplicate_key = ?",
                (owner.workspace_id, duplicate_key),
            )
        if cleaned.statut is not None:
            _set_application_status(
                connection,
                workspace_id=owner.workspace_id,
                application_id=application_id,
                new_status=cleaned.statut,
                source="proprietaire",
            )
        connection.commit()
        row = _owned_application_row(connection, owner, application_id)
    return _application_from_row(row)


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
