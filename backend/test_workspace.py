import tempfile
import os
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

import backend.main as main


def test_owner_account_creates_isolated_workspace_and_metadata():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        first = TestClient(main.app)
        second = TestClient(main.app)

        response = first.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Celine Demo",
                "email": "owner-one@example.test",
                "mdp": "correct horse battery staple",
            },
        )
        assert response.status_code == 200
        first_workspace_id = response.json()["workspace_id"]

        workspace = first.get("/api/workspace")
        assert workspace.status_code == 200
        assert workspace.json()["id"] == first_workspace_id
        assert workspace.json()["owner_email"] == "owner-one@example.test"

        renamed = first.put("/api/workspace", json={"name": "Mon portefeuille test"})
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "Mon portefeuille test"
        assert len(first.get("/api/workspace/membres").json()) == 1

        response = second.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Autre Demo",
                "email": "owner-two@example.test",
                "mdp": "correct horse battery staple",
            },
        )
        assert response.status_code == 200
        assert response.json()["workspace_id"] != first_workspace_id
        assert second.get("/api/workspace").json()["owner_email"] == "owner-two@example.test"

        anonymous = TestClient(main.app)
        assert anonymous.get("/api/workspace").status_code == 401


def test_owner_gets_private_agent_team_and_can_contact_orchestrator():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        first = TestClient(main.app)
        second = TestClient(main.app)

        first_created = first.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Owner One",
                "email": "team-one@example.test",
                "mdp": "correct horse battery staple",
            },
        )
        second_created = second.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Owner Two",
                "email": "team-two@example.test",
                "mdp": "correct horse battery staple",
            },
        )
        assert first_created.status_code == 200
        assert second_created.status_code == 200

        first_agents = first.get("/api/agents")
        second_agents = second.get("/api/agents")
        assert first_agents.status_code == 200
        assert second_agents.status_code == 200
        assert len(first_agents.json()) == len(main.OWNER_AGENT_CATALOG) == 11
        assert {agent["role"] for agent in first_agents.json()} == set(main.OWNER_AGENT_CATALOG)
        assert [agent["nom"] for agent in first_agents.json()][0] == "Orchestrateur"
        assert {agent["workspace_id"] for agent in first_agents.json()} == {
            first_created.json()["workspace_id"]
        }
        assert {agent["workspace_id"] for agent in second_agents.json()} == {
            second_created.json()["workspace_id"]
        }
        assert {agent["id"] for agent in first_agents.json()}.isdisjoint(
            {agent["id"] for agent in second_agents.json()}
        )

        message = first.post(
            "/api/agents/orchestrateur/messages",
            json={
                "contenu": "Prépare-moi le prochain plan pour mon premier bien.",
                "contexte_type": "bien",
                "contexte_id": "bien-demo",
            },
        )
        assert message.status_code == 201
        assert message.json()["agent_role"] == "orchestrateur"
        assert message.json()["statut"] == "a_traiter"
        assert message.json()["run_id"]

        messages = first.get("/api/agents/orchestrateur/messages")
        assert messages.status_code == 200
        assert messages.json()[0]["contenu"].startswith("Prépare-moi")
        assert second.get("/api/agents/orchestrateur/messages").json() == []

        runs = first.get("/api/agent-runs")
        assert runs.status_code == 200
        assert runs.json()[0]["type_agent"] == "orchestrateur"
        audit = first.get(
            "/api/audit",
            params={"entite_type": "agent_message", "entite_id": message.json()["id"]},
        )
        assert audit.status_code == 200
        assert audit.json()[0]["evenement"] == "demande_orchestrateur_recue"


def test_orchestrator_worker_routes_request_into_workspace_submissions():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        main.AGENT_INTERNAL_TOKEN = "agent-test-token"
        owner = TestClient(main.app)
        created = owner.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Owner",
                "email": "worker-owner@example.test",
                "mdp": "correct horse battery staple",
            },
        )
        assert created.status_code == 200
        workspace_id = created.json()["workspace_id"]

        agents = owner.get("/api/agents")
        assert agents.status_code == 200
        orchestrator = next(agent for agent in agents.json() if agent["role"] == "orchestrateur")
        assert "actions" in orchestrator["contrat"]
        assert "escalades" in orchestrator["contrat"]

        message = owner.post(
            "/api/agents/orchestrateur/messages",
            json={
                "contenu": "Prépare la publication de mon appartement et vérifie les documents du candidat.",
                "contexte_type": "bien",
                "contexte_id": "bien-demo",
            },
        )
        assert message.status_code == 201
        run_id = message.json()["run_id"]

        processed = owner.post(
            "/api/internal/agent-runs/process-next",
            headers={"x-piaule-agent-token": "agent-test-token"},
        )
        assert processed.status_code == 200
        assert processed.json()["traite"] is True
        assert processed.json()["run_id"] == run_id
        assert set(processed.json()["missions_enfants"])  # at least one child mission was created

        runs = owner.get("/api/agent-runs")
        assert runs.status_code == 200
        run_types = {run["type_agent"] for run in runs.json()}
        assert "orchestrateur" in run_types
        assert "agent-diffusion" in run_types
        assert "agent-conformite" in run_types
        assert all(run["workspace_id"] == workspace_id for run in runs.json())
        orchestrator_run = next(run for run in runs.json() if run["id"] == run_id)
        assert orchestrator_run["statut"] == "completed"

        messages = owner.get("/api/agents/orchestrateur/messages")
        assert messages.status_code == 200
        assert any(item["direction"] == "agent" and item["statut"] == "repondu" for item in messages.json())


def test_publication_job_requires_first_owner_validation_then_allows_automatic_mode():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        main.AGENT_INTERNAL_TOKEN = "agent-test-token"
        owner = TestClient(main.app)
        created = owner.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Owner",
                "email": "publication-job-owner@example.test",
                "mdp": "correct horse battery staple",
            },
        )
        assert created.status_code == 200
        workspace_id = created.json()["workspace_id"]

        property_response = owner.post(
            "/api/biens",
            json={
                "nom": "Appartement publication",
                "type": "appartement",
                "adresse_ligne1": "1 rue des annonces",
                "ville": "Lyon",
            },
        )
        assert property_response.status_code == 201
        property_id = property_response.json()["id"]

        connection = owner.post(
            "/api/diffusion/connexions",
            json={"plateforme": "leboncoin", "compte_libelle": "Compte propriétaire"},
        )
        assert connection.status_code == 201
        connection_id = connection.json()["id"]
        activated = owner.post(
            f"/api/internal/diffusion/connexions/{connection_id}/activer",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={"reference_compte": "provider-account-ref"},
        )
        assert activated.status_code == 200

        run = owner.post(
            "/api/internal/agent-runs",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={
                "workspace_id": workspace_id,
                "type_agent": "agent-diffusion",
                "mission": "Préparer la publication de l'annonce",
            },
        )
        assert run.status_code == 201
        run_id = run.json()["id"]

        first_job = owner.post(
            "/api/internal/diffusion/publications",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={
                "workspace_id": workspace_id,
                "connection_id": connection_id,
                "bien_id": property_id,
                "titre": "T2 lumineux",
                "description": "Annonce préparée par l'agent.",
                "contenu": {"loyer": 800, "ville": "Lyon"},
                "idempotency_key": "publication-job-first-001",
                "agent_run_id": run_id,
            },
        )
        assert first_job.status_code == 201
        first_job_data = first_job.json()
        assert first_job_data["statut"] == "a_valider"
        assert first_job_data["premiere_publication"] is True
        action_id = first_job_data["action_id"]

        approved = owner.post(f"/api/actions/{action_id}/approve", json={"motif": "Annonce relue"})
        assert approved.status_code == 200
        assert owner.get(f"/api/diffusion/publications/{first_job_data['id']}").json()["statut"] == "autorisee"
        executed = owner.post(
            f"/api/internal/actions/{action_id}/execute",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={"reference_execution": "provider-publication-1", "resultat": {"publiee": True}},
        )
        assert executed.status_code == 200
        assert owner.get(f"/api/diffusion/publications/{first_job_data['id']}").json()["statut"] == "publiee"
        assert owner.get("/api/diffusion/connexions").json()[0]["premiere_publication_validee_le"]

        automatic = owner.post(f"/api/diffusion/connexions/{connection_id}/autoriser-automatique")
        assert automatic.status_code == 200
        assert automatic.json()["mode_publication"] == "automatique"

        second_job = owner.post(
            "/api/internal/diffusion/publications",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={
                "workspace_id": workspace_id,
                "connection_id": connection_id,
                "bien_id": property_id,
                "titre": "T2 lumineux mis à jour",
                "description": "Nouvelle version de l'annonce.",
                "contenu": {"loyer": 820, "ville": "Lyon"},
                "publication_automatique": True,
                "idempotency_key": "publication-job-second-001",
                "agent_run_id": run_id,
            },
        )
        assert second_job.status_code == 201
        assert second_job.json()["statut"] == "autorisee"
        second_action = second_job.json()["action_id"]
        executed_second = owner.post(
            f"/api/internal/actions/{second_action}/execute",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={"reference_execution": "provider-publication-2", "resultat": {"publiee": True}},
        )
        assert executed_second.status_code == 200
        assert owner.get(f"/api/diffusion/publications/{second_job.json()['id']}").json()["statut"] == "publiee"


def test_completeness_worker_queues_direct_candidate_email_for_missing_documents():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        main.AGENT_INTERNAL_TOKEN = "agent-test-token"
        main.CANDIDATE_PORTAL_BASE_URL = "https://piaulefiction.fr/candidature.html"
        owner = TestClient(main.app)
        created = owner.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Owner",
                "email": "completeness-worker@example.test",
                "mdp": "correct horse battery staple",
            },
        )
        assert created.status_code == 200
        workspace_id = created.json()["workspace_id"]

        property_response = owner.post(
            "/api/biens",
            json={
                "nom": "Appartement dossier",
                "type": "appartement",
                "adresse_ligne1": "1 rue des pièces",
                "ville": "Lyon",
            },
        )
        assert property_response.status_code == 201
        property_id = property_response.json()["id"]
        application = owner.post(
            f"/api/biens/{property_id}/candidatures",
            json={
                "candidat_prenom": "Alex",
                "candidat_nom": "Test",
                "candidat_email": "alex@example.test",
            },
        )
        assert application.status_code == 201
        application_id = application.json()["id"]

        run = owner.post(
            "/api/internal/agent-runs",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={
                "workspace_id": workspace_id,
                "type_agent": "agent-completude",
                "mission": "Demander les pièces manquantes au candidat",
                "cible_type": "candidature",
                "cible_id": application_id,
                "entree": {"property_id": property_id, "application_id": application_id},
            },
        )
        assert run.status_code == 201

        processed = owner.post(
            "/api/internal/agent-runs/process-next-completude",
            headers={"x-piaule-agent-token": "agent-test-token"},
        )
        assert processed.status_code == 200
        assert processed.json()["statut"] == "completed"
        assert processed.json()["message_reponse_id"]

        messages = owner.get(f"/api/biens/{property_id}/candidatures/{application_id}/messages")
        assert messages.status_code == 200
        outgoing = [message for message in messages.json() if message["direction"] == "sortant"]
        assert len(outgoing) == 1
        assert outgoing[0]["statut"] == "a_envoyer"
        assert "https://piaulefiction.fr/candidature.html?access=" in outgoing[0]["contenu"]

        run_state = owner.get(f"/api/agent-runs/{run.json()['id']}")
        assert run_state.status_code == 200
        assert run_state.json()["statut"] == "completed"
        assert run_state.json()["sortie"]["followup"]["pieces_demandees"]


def test_received_piece_requeues_completeness_and_confidence_workers():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        main.AGENT_INTERNAL_TOKEN = "agent-test-token"
        owner = TestClient(main.app)
        created = owner.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Owner",
                "email": "pipeline-owner@example.test",
                "mdp": "correct horse battery staple",
            },
        )
        assert created.status_code == 200
        property_response = owner.post(
            "/api/biens",
            json={
                "nom": "Bien pipeline confiance",
                "type": "appartement",
                "adresse_ligne1": "1 rue du pipeline",
                "ville": "Lyon",
                "politique_verification": "officielle",
            },
        )
        property_id = property_response.json()["id"]
        application = owner.post(
            f"/api/biens/{property_id}/candidatures",
            json={
                "candidat_prenom": "Alex",
                "candidat_nom": "Pipeline",
                "candidat_email": "alex-pipeline@example.test",
            },
        )
        application_id = application.json()["id"]
        link = owner.post(f"/api/biens/{property_id}/candidatures/{application_id}/lien-candidat")
        token = link.json()["url"].split("?access=", 1)[1]

        uploaded = owner.post(
            f"/api/candidature-acces/{token}/pieces",
            data={"nom": "Pièce d'identité", "type": "identite"},
            files={"file": ("identite.pdf", b"%PDF-pipeline", "application/pdf")},
        )
        assert uploaded.status_code == 201

        runs = owner.get("/api/agent-runs").json()
        queued_types = {run["type_agent"] for run in runs if run["statut"] == "queued"}
        assert {"agent-completude", "agent-confiance"}.issubset(queued_types)

        confidence = owner.post(
            "/api/internal/agent-runs/process-next-confiance",
            headers={"x-piaule-agent-token": "agent-test-token"},
        )
        assert confidence.status_code == 200
        assert confidence.json()["statut"] == "completed"

        portal = owner.get(f"/api/candidature-acces/{token}")
        assert portal.status_code == 200
        assert portal.json()["verifications"][0]["source"] == "france_identite"
        assert portal.json()["verifications"][0]["statut"] == "en_attente_consentement"


def test_calendar_connection_sync_blocks_conflicting_visit_slot():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        main.AGENT_INTERNAL_TOKEN = "agent-test-token"
        owner = TestClient(main.app)
        created = owner.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Owner",
                "email": "calendar-owner@example.test",
                "mdp": "correct horse battery staple",
            },
        )
        assert created.status_code == 200
        workspace_id = created.json()["workspace_id"]

        property_response = owner.post(
            "/api/biens",
            json={
                "nom": "Appartement calendrier",
                "type": "appartement",
                "adresse_ligne1": "1 rue du calendrier",
                "ville": "Lyon",
            },
        )
        assert property_response.status_code == 201
        property_id = property_response.json()["id"]
        calendar = owner.post(
            "/api/calendriers/connexions",
            json={"fournisseur": "microsoft_graph", "compte_libelle": "Outlook propriétaire"},
        )
        assert calendar.status_code == 201
        connection_id = calendar.json()["id"]
        activated = owner.post(
            f"/api/internal/calendriers/connexions/{connection_id}/activer",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={"reference_compte": "outlook-account-ref"},
        )
        assert activated.status_code == 200

        synced = owner.post(
            f"/api/internal/calendriers/connexions/{connection_id}/synchroniser",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={
                "periodes_occupees": [
                    {
                        "external_id": "outlook-event-1",
                        "debut": "2026-10-21T18:00:00+02:00",
                        "fin": "2026-10-21T19:00:00+02:00",
                        "titre": "Indisponible",
                    }
                ]
            },
        )
        assert synced.status_code == 200
        assert synced.json()["derniere_synchronisation_le"]

        slot = owner.post(
            f"/api/biens/{property_id}/visite-creneaux",
            json={
                "debut": "2026-10-21T18:30:00+02:00",
                "fin": "2026-10-21T19:30:00+02:00",
            },
        )
        assert slot.status_code == 409, slot.text
        assert owner.get("/api/calendriers/connexions").json()[0]["statut"] == "active"

        revoked = owner.post(f"/api/calendriers/connexions/{connection_id}/revoquer")
        assert revoked.status_code == 200
        assert revoked.json()["statut"] == "revoquee"
        available_after_revoke = owner.post(
            f"/api/biens/{property_id}/visite-creneaux",
            json={
                "debut": "2026-10-21T18:30:00+02:00",
                "fin": "2026-10-21T19:30:00+02:00",
            },
        )
        assert available_after_revoke.status_code == 201


def test_publication_auto_requires_first_approved_publication_and_can_be_revoked():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        main.AGENT_INTERNAL_TOKEN = "agent-test-token"
        owner = TestClient(main.app)
        created = owner.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Owner",
                "email": "publication-owner@example.test",
                "mdp": "correct horse battery staple",
            },
        )
        assert created.status_code == 200

        connection = owner.post(
            "/api/diffusion/connexions",
            json={"plateforme": "leboncoin", "compte_libelle": "Compte propriétaire"},
        )
        assert connection.status_code == 201
        connection_id = connection.json()["id"]
        assert connection.json()["statut"] == "a_connecter"
        assert owner.post(f"/api/diffusion/connexions/{connection_id}/autoriser-automatique").status_code == 409

        activated = owner.post(
            f"/api/internal/diffusion/connexions/{connection_id}/activer",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={"reference_compte": "provider-account-ref"},
        )
        assert activated.status_code == 200
        workspace_id = created.json()["workspace_id"]
        run = owner.post(
            "/api/internal/agent-runs",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={
                "workspace_id": workspace_id,
                "type_agent": "agent-diffusion",
                "mission": "Publier la première annonce validée",
            },
        )
        assert run.status_code == 201
        action = owner.post(
            "/api/internal/actions",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={
                "workspace_id": workspace_id,
                "agent_run_id": run.json()["id"],
                "type_action": "publier_annonce",
                "libelle": "Publier la première annonce",
                "niveau_risque": "transmission",
                "payload": {
                    "connection_id": connection_id,
                    "premiere_publication": True,
                },
                "idempotency_key": "first-publication-001",
            },
        )
        assert action.status_code == 201
        action_id = action.json()["id"]
        assert owner.post(f"/api/actions/{action_id}/approve", json={}).status_code == 200
        executed = owner.post(
            f"/api/internal/actions/{action_id}/execute",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={"reference_execution": "provider-publication-1", "resultat": {"publiee": True}},
        )
        assert executed.status_code == 200

        automatic = owner.post(f"/api/diffusion/connexions/{connection_id}/autoriser-automatique")
        assert automatic.status_code == 200
        assert automatic.json()["mode_publication"] == "automatique"
        assert automatic.json()["premiere_publication_validee_le"]

        revoked = owner.post(f"/api/diffusion/connexions/{connection_id}/revoquer")
        assert revoked.status_code == 200
        assert revoked.json()["statut"] == "revoquee"
        assert revoked.json()["mode_publication"] == "validation_a_chaque_fois"


def test_verification_policy_and_external_proof_are_consent_gated():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        main.VERIFICATION_INTERNAL_TOKEN = "verification-test-token"
        owner = TestClient(main.app)
        assert owner.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Owner",
                "email": "verification-owner@example.test",
                "mdp": "correct horse battery staple",
            },
        ).status_code == 200

        property_response = owner.post(
            "/api/biens",
            json={
                "nom": "Bien vérification",
                "type": "appartement",
                "adresse_ligne1": "1 rue des preuves",
                "ville": "Lyon",
                "politique_verification": "renforcee",
            },
        )
        assert property_response.status_code == 201
        property_id = property_response.json()["id"]
        assert property_response.json()["politique_verification"] == "renforcee"

        switched = owner.put(
            f"/api/biens/{property_id}/politique-verification",
            json={"politique": "officielle"},
        )
        assert switched.status_code == 200
        assert "france_identite" in switched.json()["sources_disponibles"]

        application = owner.post(
            f"/api/biens/{property_id}/candidatures",
            json={
                "candidat_prenom": "Alex",
                "candidat_nom": "Demo",
                "candidat_email": "alex-verification@example.test",
                "source": "email",
            },
        )
        assert application.status_code == 201
        application_id = application.json()["id"]
        uploaded = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/pieces",
            data={"nom": "Identité", "type": "identite"},
            files={"file": ("identite.pdf", b"%PDF-identity", "application/pdf")},
        )
        assert uploaded.status_code == 201
        document_id = uploaded.json()["id"]

        request_response = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/pieces/{document_id}/verifications",
            json={"source": "france_identite", "motif": "Confirmer l'identité du candidat"},
        )
        assert request_response.status_code == 201
        request_id = request_response.json()["id"]
        assert request_response.json()["statut"] == "en_attente_consentement"

        link = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/lien-candidat"
        )
        token = link.json()["url"].split("?access=", 1)[1]
        consent = owner.post(
            f"/api/candidature-acces/{token}/verifications/{request_id}/consentement",
            json={"accepte": True},
        )
        assert consent.status_code == 200
        assert consent.json()["statut"] == "en_attente_source"

        result = owner.post(
            f"/api/internal/verifications/{request_id}/result",
            headers={"x-piaule-verification-token": "verification-test-token"},
            json={
                "statut": "confirmee",
                "resultat": "Justificatif confirmé par la source officielle.",
                "preuve": {"type": "identite", "signature": "valide"},
                "reference_externe": "provider-reference-1",
            },
        )
        assert result.status_code == 200
        assert result.json()["statut"] == "confirmee"
        document = owner.get(
            f"/api/biens/{property_id}/candidatures/{application_id}/pieces"
        ).json()[0]
        assert document["niveau_verification"] == "source_officielle"
        assert document["statut"] == "valide"


def test_visit_slots_are_reserved_and_candidate_can_confirm_once_complete():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        owner = TestClient(main.app)
        assert owner.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Owner",
                "email": "visit-owner@example.test",
                "mdp": "correct horse battery staple",
            },
        ).status_code == 200
        property_response = owner.post(
            "/api/biens",
            json={
                "nom": "Bien visites",
                "type": "appartement",
                "adresse_ligne1": "1 rue des rendez-vous",
                "ville": "Chambéry",
            },
        )
        property_id = property_response.json()["id"]
        application = owner.post(
            f"/api/biens/{property_id}/candidatures",
            json={
                "candidat_prenom": "Alex",
                "candidat_nom": "Demo",
                "candidat_email": "alex-visit@example.test",
                "source": "email",
            },
        )
        application_id = application.json()["id"]

        for document_type in ("identite", "domicile", "situation_professionnelle", "ressources", "imposition"):
            uploaded = owner.post(
                f"/api/biens/{property_id}/candidatures/{application_id}/pieces",
                data={"nom": f"Pièce {document_type}", "type": document_type},
                files={"file": (f"{document_type}.pdf", b"%PDF-1.4 demo", "application/pdf")},
            )
            assert uploaded.status_code == 201
            document_id = uploaded.json()["id"]
            verified = owner.put(
                f"/api/biens/{property_id}/candidatures/{application_id}/pieces/{document_id}/verification",
                json={"statut": "valide", "note_verification": "Revue humaine de test"},
            )
            assert verified.status_code == 200

        slot = owner.post(
            f"/api/biens/{property_id}/visite-creneaux",
            json={
                "debut": "2027-01-10T10:00:00+01:00",
                "fin": "2027-01-10T10:30:00+01:00",
                "mode": "sur_place",
            },
        )
        assert slot.status_code == 201
        slot_id = slot.json()["id"]
        proposed = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/visites/proposer",
            json={"slot_id": slot_id, "note": "Créneau proposé par l'agent."},
        )
        assert proposed.status_code == 201
        visit_id = proposed.json()["id"]
        assert proposed.json()["statut"] == "proposee"

        link = owner.post(f"/api/biens/{property_id}/candidatures/{application_id}/lien-candidat")
        token = link.json()["url"].split("?access=", 1)[1]
        candidate_view = owner.get(f"/api/candidature-acces/{token}/visites")
        assert candidate_view.status_code == 200
        assert candidate_view.json()[0]["id"] == visit_id
        confirmed = owner.post(
            f"/api/candidature-acces/{token}/visites/{visit_id}/reponse",
            json={"accepte": True},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["statut"] == "confirmee"
        assert owner.get(f"/api/biens/{property_id}/visites").json()[0]["statut"] == "confirmee"
        assert owner.get(f"/api/biens/{property_id}/candidatures/{application_id}").json()["statut"] == "visite_confirmee"

        duplicate = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/visites/proposer",
            json={"slot_id": slot_id},
        )
        assert duplicate.status_code == 409


def test_password_reset_token_is_single_use():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        client = TestClient(main.app)
        client.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Celine",
                "email": "reset@example.test",
                "mdp": "old secure password",
            },
        )

        os.environ["PIAULE_EXPOSE_DEV_RESET_TOKEN"] = "true"
        try:
            requested = client.post(
                "/api/mot-de-passe-oublie",
                json={"email": "reset@example.test", "prenom": "Celine"},
            )
            token = requested.json()["dev_reset_token"]
        finally:
            os.environ.pop("PIAULE_EXPOSE_DEV_RESET_TOKEN", None)

        assert client.post(
            "/api/mot-de-passe-reinitialiser",
            json={"token": token, "nouveau_mdp": "new secure password"},
        ).status_code == 200
        assert client.post(
            "/api/compte",
            json={
                "action": "connexion",
                "email": "reset@example.test",
                "mdp": "new secure password",
            },
        ).status_code == 200
        assert client.post(
            "/api/mot-de-passe-reinitialiser",
            json={"token": token, "nouveau_mdp": "another password"},
        ).status_code == 400


def test_properties_and_lots_are_persisted_and_isolated_by_workspace():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        owner = TestClient(main.app)
        other = TestClient(main.app)

        for client, prenom, email in (
            (owner, "Celine", "property-owner@example.test"),
            (other, "Other", "other-owner@example.test"),
        ):
            assert client.post(
                "/api/compte",
                json={
                    "action": "creer",
                    "prenom": prenom,
                    "email": email,
                    "mdp": "correct horse battery staple",
                },
            ).status_code == 200

        created = owner.post(
            "/api/biens",
            json={
                "nom": "Maison de démonstration",
                "type": "maison",
                "structure": "bien_individuel",
                "adresse_ligne1": "12 rue des Tests",
                "code_postal": "73000",
                "ville": "Chambéry",
                "description_publique": "Maison test prête à louer",
                "statut": "vacant",
                "date_disponibilite": "2026-11-01",
                "mode_detention": "nom_propre",
                "equipements": ["jardin", "parking"],
                "photos": ["photo-demo-1"],
                "tags": ["centre-ville", "test"],
            },
        )
        assert created.status_code == 201
        property_id = created.json()["id"]
        assert created.json()["lots_count"] == 0
        assert created.json()["statut"] == "vacant"
        assert created.json()["equipements"] == ["jardin", "parking"]

        lot = owner.post(
            f"/api/biens/{property_id}/lots",
            json={
                "identifiant": "T2 - 1er étage",
                "type": "appartement",
                "surface_m2": 42.5,
                "pieces": 2,
                "chambres": 1,
                "loyer_mensuel_eur": 700,
                "charges_mensuelles_eur": 60,
                "type_charges": "provision",
                "type_location": "meuble",
                "date_disponibilite": "2026-11-01",
                "dpe_classe": "D",
                "ges_classe": "B",
                "chauffage": "Individuel électrique",
                "ascenseur": True,
                "equipements": ["balcon"],
                "statut": "disponible",
            },
        )
        assert lot.status_code == 201
        lot_id = lot.json()["id"]
        assert lot.json()["bien_id"] == property_id
        assert lot.json()["type_location"] == "meuble"
        assert lot.json()["dpe_classe"] == "D"
        assert len(owner.get(f"/api/biens/{property_id}/lots").json()) == 1
        assert owner.get(f"/api/biens/{property_id}").json()["lots_count"] == 1

        record = owner.post(
            f"/api/biens/{property_id}/suivis",
            json={
                "type": "diagnostic",
                "titre": "Diagnostic de performance énergétique",
                "lot_id": lot_id,
                "date_etablissement": "2026-10-01",
                "date_expiration": (date.today() + timedelta(days=7)).isoformat(),
                "statut": "valide",
            },
        )
        assert record.status_code == 201
        assert record.json()["lot_id"] == lot_id
        assert len(owner.get("/api/echeances?jours=30").json()) == 1

        duplicate = owner.post(
            f"/api/biens/{property_id}/lots",
            json={"identifiant": "T2 - 1er étage"},
        )
        assert duplicate.status_code == 409

        assert other.get(f"/api/biens/{property_id}").status_code == 404
        assert other.get(f"/api/biens/{property_id}/lots/{lot_id}").status_code == 404

        updated = owner.put(
            f"/api/biens/{property_id}/lots/{lot_id}",
            json={
                "identifiant": "T2 - 1er étage",
                "type": "appartement",
                "loyer_mensuel_eur": 720,
                "statut": "occupe",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["loyer_mensuel_eur"] == 720
        assert updated.json()["statut"] == "occupe"


def test_owner_applications_are_attached_to_property_and_duplicates_are_flagged():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        owner = TestClient(main.app)
        other = TestClient(main.app)

        for client, prenom, email in (
            (owner, "Celine", "application-owner@example.test"),
            (other, "Other", "application-other@example.test"),
        ):
            assert client.post(
                "/api/compte",
                json={
                    "action": "creer",
                    "prenom": prenom,
                    "email": email,
                    "mdp": "correct horse battery staple",
                },
            ).status_code == 200

        property_response = owner.post(
            "/api/biens",
            json={
                "nom": "Immeuble candidatures",
                "type": "immeuble",
                "adresse_ligne1": "1 avenue des Dossiers",
                "ville": "Lyon",
            },
        )
        property_id = property_response.json()["id"]
        lot_response = owner.post(
            f"/api/biens/{property_id}/lots",
            json={"identifiant": "Lot A", "type": "appartement"},
        )
        lot_id = lot_response.json()["id"]

        channel = owner.post(
            f"/api/biens/{property_id}/canaux-candidatures",
            json={"lot_id": lot_id, "canal": "leboncoin", "libelle": "Annonce Lot A"},
        )
        assert channel.status_code == 201
        reception_address = channel.json()["adresse_reception"]
        assert reception_address.endswith("@piaulefiction.fr")

        os.environ["PIAULE_INBOUND_WEBHOOK_TOKEN"] = "test-inbound-token"
        try:
            inbound = owner.post(
                "/api/internal/candidatures/inbound",
                headers={"x-piaule-inbound-token": "test-inbound-token"},
                json={
                    "adresse_reception": reception_address,
                    "message_id": "provider-message-1",
                    "expediteur_email": "Alex.Demo@example.test",
                    "objet": "Candidature pour le T2",
                    "contenu_texte": "Bonjour, je souhaite visiter le logement.",
                    "pieces_jointes": ["dossier.pdf", "piece-identite.pdf"],
                },
            )
        finally:
            os.environ.pop("PIAULE_INBOUND_WEBHOOK_TOKEN", None)
        assert inbound.status_code == 200
        inbound_id = inbound.json()["id"]
        assert inbound.json()["statut"] == "recue"
        assert inbound.json()["bien_id"] == property_id
        assert inbound.json()["lot_id"] == lot_id

        assert owner.get("/api/candidatures/inbox").json()[0]["id"] == inbound_id

        created = owner.post(
            f"/api/biens/{property_id}/candidatures",
            json={
                "lot_id": lot_id,
                "candidat_prenom": "Alex",
                "candidat_nom": "Demo",
                "candidat_email": "Alex.Demo@example.test",
                "source": "dossier_facile",
            },
        )
        assert created.status_code == 201
        application_id = created.json()["id"]
        assert created.json()["candidat_email"] == "alex.demo@example.test"
        assert created.json()["bien_id"] == property_id
        assert created.json()["lot_id"] == lot_id
        assert created.json()["statut"] == "recue"
        assert created.json()["doublon_possible"] is False

        followup = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/agent/relancer-completude"
        )
        assert followup.status_code == 201
        assert followup.json()["statut"] == "a_envoyer"
        assert set(followup.json()["pieces_demandees"]) == {
            "identite",
            "domicile",
            "situation_professionnelle",
            "ressources",
            "imposition",
        }
        assert followup.json()["human_approval_required"] is False
        assert followup.json()["refus_decision_proprietaire"] is True
        assert followup.json()["lien_depot"]
        agent_message = owner.get(
            f"/api/biens/{property_id}/candidatures/{application_id}/messages"
        ).json()[0]
        assert agent_message["source"] == "agent"
        assert agent_message["statut"] == "a_envoyer"

        duplicate_followup = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/agent/relancer-completude"
        )
        assert duplicate_followup.status_code == 201
        assert duplicate_followup.json()["statut"] == "deja_preparee"
        assert duplicate_followup.json()["id"] == followup.json()["id"]

        unsupported = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/pieces",
            data={"nom": "Photo HEIC", "type": "identite"},
            files={"file": ("identite.heic", b"fake-heic", "image/heic")},
        )
        assert unsupported.status_code == 415

        oversized = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/pieces",
            data={"nom": "Document trop lourd", "type": "identite"},
            files={
                "file": (
                    "trop-lourd.pdf",
                    b"x" * (main.MAX_DOCUMENT_BYTES + 1),
                    "application/pdf",
                )
            },
        )
        assert oversized.status_code == 413

        identity = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/pieces",
            data={"nom": "Pièce d'identité", "type": "identite", "provenance": "portail_candidat"},
            files={"file": ("identite.pdf", b"%PDF-demo-identite", "application/pdf")},
        )
        assert identity.status_code == 201
        identity_id = identity.json()["id"]
        assert identity.json()["statut"] == "en_verification"
        assert identity.json()["niveau_verification"] == "controles_techniques"
        assert identity.json()["anomalies"] == []
        assert identity.json()["provenance"] == "portail_candidat"
        assert owner.get(
            f"/api/biens/{property_id}/candidatures/{application_id}/completude"
        ).json()["statut"] == "en_verification"

        verified_identity = owner.put(
            f"/api/biens/{property_id}/candidatures/{application_id}/pieces/{identity_id}/verification",
            json={"statut": "valide", "note_verification": "Document lisible."},
        )
        assert verified_identity.status_code == 200
        assert verified_identity.json()["statut"] == "valide"

        for document_type in ("domicile", "situation_professionnelle", "ressources", "imposition"):
            uploaded = owner.post(
                f"/api/biens/{property_id}/candidatures/{application_id}/pieces",
                data={"nom": document_type, "type": document_type, "provenance": "email"},
                files={"file": (f"{document_type}.pdf", b"%PDF-demo", "application/pdf")},
            )
            assert uploaded.status_code == 201
            verified = owner.put(
                f"/api/biens/{property_id}/candidatures/{application_id}/pieces/{uploaded.json()['id']}/verification",
                json={"statut": "valide"},
            )
            assert verified.status_code == 200

        completeness = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/verifier"
        )
        assert completeness.status_code == 200
        assert completeness.json()["statut"] == "complet"
        assert completeness.json()["score"] == 100
        assert owner.get(f"/api/biens/{property_id}/candidatures/{application_id}").json()["statut"] == "prete"

        access_link = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/lien-candidat"
        )
        assert access_link.status_code == 200
        access_token = access_link.json()["url"].split("?access=", 1)[1]
        portal = owner.get(f"/api/candidature-acces/{access_token}")
        assert portal.status_code == 200
        assert portal.json()["candidat_prenom"] == "Alex"
        assert portal.json()["completude"]["score"] == 100

        candidate_message = owner.post(
            f"/api/candidature-acces/{access_token}/messages",
            json={"sujet": "Question", "contenu": "Je reste disponible pour une visite."},
        )
        assert candidate_message.status_code == 201
        assert candidate_message.json()["direction"] == "entrant"
        owner_message = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/messages",
            json={"sujet": "Suite du dossier", "contenu": "Merci pour votre retour."},
        )
        assert owner_message.status_code == 201
        assert owner_message.json()["statut"] == "a_envoyer"
        assert len(owner.get(f"/api/biens/{property_id}/candidatures/{application_id}/messages").json()) == 3

        duplicate = owner.post(
            f"/api/biens/{property_id}/candidatures",
            json={
                "lot_id": lot_id,
                "candidat_prenom": "Alex",
                "candidat_nom": "Demo",
                "candidat_email": "alex.demo@example.test",
            },
        )
        assert duplicate.status_code == 201
        assert duplicate.json()["doublon_possible"] is True
        assert owner.get(f"/api/biens/{property_id}/candidatures").json()[0]["doublon_possible"] is True

        updated = owner.put(
            f"/api/biens/{property_id}/candidatures/{application_id}",
            json={"statut": "en_verification", "notes_privees": "Pièce d'identité à vérifier."},
        )
        assert updated.status_code == 200
        assert updated.json()["statut"] == "en_verification"
        assert updated.json()["notes_privees"] == "Pièce d'identité à vérifier."
        assert len(owner.get("/api/candidatures").json()) == 2

        associated = owner.put(
            f"/api/candidatures/inbox/{inbound_id}/associer",
            json={"candidature_id": application_id},
        )
        assert associated.status_code == 200
        assert associated.json()["statut"] == "associee"
        assert associated.json()["candidature_id"] == application_id

        assert other.get(f"/api/biens/{property_id}/candidatures/{application_id}").status_code == 404


def test_dossier_facile_connect_requires_partner_configuration_and_keeps_summary_minimal():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        owner = TestClient(main.app)
        assert owner.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Celine",
                "email": "dossier-facile-owner@example.test",
                "mdp": "correct horse battery staple",
            },
        ).status_code == 200
        property_id = owner.post(
            "/api/biens",
            json={
                "nom": "Bien DossierFacile",
                "type": "appartement",
                "adresse_ligne1": "2 rue du Test",
                "ville": "Lille",
            },
        ).json()["id"]
        application_id = owner.post(
            f"/api/biens/{property_id}/candidatures",
            json={
                "candidat_prenom": "Alex",
                "candidat_nom": "Demo",
                "candidat_email": "alex@example.test",
            },
        ).json()["id"]

        response = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/dossier-facile/connect"
        )
        assert response.status_code == 503
        assert "identifiants partenaires" in response.json()["detail"]

    status, tenant_id, summary = main._dossier_facile_summary(
        {
            "tenantId": "tenant-123",
            "status": "VALIDATED",
            "documents": [{"status": "VALIDATED"}],
            "private_document_content": "must not be stored",
        }
    )
    assert status == "verifiee"
    assert tenant_id == "tenant-123"
    assert summary == {
        "statut_dossier": "VALIDATED",
        "documents_total": 1,
        "documents_statuts": ["VALIDATED"],
    }


def test_candidate_email_outbox_sends_queued_messages(monkeypatch):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        owner = TestClient(main.app)
        assert owner.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Celine",
                "email": "email-owner@example.test",
                "mdp": "correct horse battery staple",
            },
        ).status_code == 200

        property_id = owner.post(
            "/api/biens",
            json={
                "nom": "Bien e-mail",
                "type": "appartement",
                "adresse_ligne1": "1 rue du Test",
                "ville": "Lyon",
            },
        ).json()["id"]
        application_id = owner.post(
            f"/api/biens/{property_id}/candidatures",
            json={
                "candidat_prenom": "Alex",
                "candidat_nom": "Demo",
                "candidat_email": "alex@example.test",
            },
        ).json()["id"]
        queued = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/messages",
            json={"sujet": "Dossier", "contenu": "Merci de compléter votre dossier."},
        )
        assert queued.status_code == 201

        sent: list[tuple[str, str, str]] = []

        def fake_send(recipient: str, subject: str, body: str) -> None:
            sent.append((recipient, subject, body))

        monkeypatch.setattr(main, "_send_smtp_message", fake_send)
        monkeypatch.setenv("PIAULE_EMAIL_ENABLED", "true")
        monkeypatch.setenv("PIAULE_SMTP_HOST", "smtp.hostinger.com")
        monkeypatch.setenv("PIAULE_SMTP_USERNAME", "robot@piaulefiction.fr")
        monkeypatch.setenv("PIAULE_SMTP_PASSWORD", "synthetic-password")
        monkeypatch.setenv("PIAULE_SMTP_FROM", "robot@piaulefiction.fr")
        monkeypatch.setenv("PIAULE_EMAIL_INTERNAL_TOKEN", "email-worker-token")

        processed = owner.post(
            "/api/internal/candidatures/outbox/traiter",
            headers={"x-piaule-email-token": "email-worker-token"},
        )
        assert processed.status_code == 200
        assert processed.json() == {
            "traite": 1,
            "envoyes": 1,
            "erreurs": 0,
            "configuration": "smtp",
        }
        assert sent[0][0] == "alex@example.test"
        assert owner.get(
            f"/api/biens/{property_id}/candidatures/{application_id}/messages"
        ).json()[0]["statut"] == "envoye"


def test_unified_owner_inbox_keeps_email_and_candidate_portal_in_one_conversation():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        owner = TestClient(main.app)
        assert owner.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Celine",
                "email": "inbox-owner@example.test",
                "mdp": "correct horse battery staple",
            },
        ).status_code == 200

        property_id = owner.post(
            "/api/biens",
            json={
                "nom": "Bien boîte unifiée",
                "type": "appartement",
                "adresse_ligne1": "1 rue des messages",
                "ville": "Lyon",
            },
        ).json()["id"]
        application_id = owner.post(
            f"/api/biens/{property_id}/candidatures",
            json={
                "candidat_prenom": "Alex",
                "candidat_nom": "Demo",
                "candidat_email": "alex-inbox@example.test",
            },
        ).json()["id"]

        first = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/messages",
            json={"sujet": "Premier contact", "contenu": "Bonjour Alex."},
        )
        assert first.status_code == 201
        assert first.json()["canal"] == "email"

        access = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/lien-candidat"
        )
        access_token = access.json()["url"].split("?access=", 1)[1]
        reply = owner.post(
            f"/api/candidature-acces/{access_token}/messages",
            json={"sujet": "Re: Premier contact", "contenu": "Merci, je suis disponible."},
        )
        assert reply.status_code == 201
        assert reply.json()["canal"] == "portail_candidat"

        conversations = owner.get("/api/messages/conversations")
        assert conversations.status_code == 200
        assert len(conversations.json()) == 1
        conversation = conversations.json()[0]
        assert conversation["candidature_id"] == application_id
        assert conversation["messages_non_lus"] == 1
        conversation_id = conversation["id"]

        detail = owner.get(f"/api/messages/conversations/{conversation_id}")
        assert detail.status_code == 200
        assert len(detail.json()["messages"]) == 2

        marked = owner.post(f"/api/messages/conversations/{conversation_id}/lire")
        assert marked.status_code == 200
        assert marked.json()["messages_non_lus"] == 0

        outgoing = owner.post(
            f"/api/messages/conversations/{conversation_id}",
            json={"sujet": "Suite", "contenu": "Votre dossier est en cours."},
        )
        assert outgoing.status_code == 201
        assert outgoing.json()["statut"] == "a_envoyer"
        assert outgoing.json()["conversation_id"] == conversation_id


def test_application_status_cycle_records_history_and_blocks_early_visit():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        owner = TestClient(main.app)
        assert owner.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Celine",
                "email": "status-owner@example.test",
                "mdp": "correct horse battery staple",
            },
        ).status_code == 200
        property_id = owner.post(
            "/api/biens",
            json={
                "nom": "Bien workflow",
                "type": "appartement",
                "adresse_ligne1": "3 rue du Test",
                "ville": "Grenoble",
            },
        ).json()["id"]
        application_id = owner.post(
            f"/api/biens/{property_id}/candidatures",
            json={
                "candidat_prenom": "Alex",
                "candidat_nom": "Demo",
                "candidat_email": "workflow@example.test",
            },
        ).json()["id"]

        initial_history = owner.get(
            f"/api/biens/{property_id}/candidatures/{application_id}/historique"
        )
        assert initial_history.status_code == 200
        assert initial_history.json()[0]["nouveau_statut"] == "recue"

        incomplete = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/statut",
            json={"statut": "a_completer", "motif": "Deux pièces sont manquantes."},
        )
        assert incomplete.status_code == 200
        assert incomplete.json()["statut"] == "a_completer"
        assert incomplete.json()["statut_motif"] == "Deux pièces sont manquantes."

        too_early = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/statut",
            json={"statut": "visite_proposee"},
        )
        assert too_early.status_code == 409

        refused = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/statut",
            json={"statut": "refusee", "motif": "Dossier non complété."},
        )
        assert refused.status_code == 200
        reopened = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/statut",
            json={"statut": "recue", "motif": "Le candidat revient avec un nouveau dossier."},
        )
        assert reopened.status_code == 200

        history = owner.get(
            f"/api/biens/{property_id}/candidatures/{application_id}/historique"
        )
        assert [event["nouveau_statut"] for event in history.json()] == [
            "recue",
            "a_completer",
            "refusee",
            "recue",
        ]


def test_document_preflight_flags_integrity_type_and_duplicate_without_certifying_content():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        owner = TestClient(main.app)
        assert owner.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Celine",
                "email": "document-owner@example.test",
                "mdp": "correct horse battery staple",
            },
        ).status_code == 200
        property_id = owner.post(
            "/api/biens",
            json={
                "nom": "Bien documents",
                "type": "appartement",
                "adresse_ligne1": "4 rue du Test",
                "ville": "Nantes",
            },
        ).json()["id"]
        application_id = owner.post(
            f"/api/biens/{property_id}/candidatures",
            json={
                "candidat_prenom": "Alex",
                "candidat_nom": "Demo",
                "candidat_email": "documents@example.test",
            },
        ).json()["id"]

        mismatched = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/pieces",
            data={"nom": "Identité", "type": "identite"},
            files={"file": ("avis-imposition.pdf", b"%PDF-valid-header", "application/pdf")},
        )
        assert mismatched.status_code == 201
        assert mismatched.json()["statut"] == "a_corriger"
        assert "type_probable_incompatible_avec_le_nom" in mismatched.json()["anomalies"]

        unreadable = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/pieces",
            data={"nom": "Domicile", "type": "domicile"},
            files={"file": ("domicile.pdf", b"texte sans signature PDF", "application/pdf")},
        )
        assert unreadable.status_code == 201
        assert unreadable.json()["statut"] == "a_corriger"
        assert "signature_fichier_incoherente" in unreadable.json()["anomalies"]

        valid_bytes = b"%PDF-identite-valide"
        first = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/pieces",
            data={"nom": "Identité 2", "type": "identite"},
            files={"file": ("identite-2.pdf", valid_bytes, "application/pdf")},
        )
        second = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/pieces",
            data={"nom": "Identité 3", "type": "identite"},
            files={"file": ("identite-3.pdf", valid_bytes, "application/pdf")},
        )
        assert first.status_code == 201
        assert second.status_code == 201
        assert second.json()["statut"] == "a_corriger"
        assert "doublon_dans_le_dossier" in second.json()["anomalies"]

        checks = owner.get(
            f"/api/biens/{property_id}/candidatures/{application_id}/pieces/{second.json()['id']}/controles"
        )
        assert checks.status_code == 200
        assert checks.json()[-1]["controles"]["authenticite"] == "non_verifiable_localement"

        analyzed = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/pieces/{second.json()['id']}/analyser"
        )
        assert analyzed.status_code == 200
        assert analyzed.json()["dernier_controle"]["resultat"] == "attention"
def test_agent_actions_require_owner_approval_are_idempotent_and_audited():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        main.AGENT_INTERNAL_TOKEN = "agent-test-token"
        owner = TestClient(main.app)
        other_owner = TestClient(main.app)

        created = owner.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Owner",
                "email": "action-owner@example.test",
                "mdp": "correct horse battery staple",
            },
        )
        assert created.status_code == 200
        workspace_id = created.json()["workspace_id"]
        other_created = other_owner.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Other",
                "email": "action-other@example.test",
                "mdp": "correct horse battery staple",
            },
        )
        assert other_created.status_code == 200

        property_id = owner.post(
            "/api/biens",
            json={
                "nom": "Bien action test",
                "type": "appartement",
                "adresse_ligne1": "1 rue de la validation",
                "ville": "Lille",
            },
        ).json()["id"]
        run = owner.post(
            "/api/internal/agent-runs",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={
                "workspace_id": workspace_id,
                "type_agent": "agent-completude",
                "mission": "Préparer une demande de pièce manquante",
                "cible_type": "bien",
                "cible_id": property_id,
                "entree": {"raison": "dossier incomplet"},
            },
        )
        assert run.status_code == 201
        run_id = run.json()["id"]

        action_payload = {
            "workspace_id": workspace_id,
            "agent_run_id": run_id,
            "type_action": "preparer_message_candidat",
            "libelle": "Demander le justificatif de domicile",
            "description": "Préparer un message ciblé sans l'envoyer.",
            "niveau_risque": "transmission",
            "destinataire": "alex@example.test",
            "cible_type": "bien",
            "cible_id": property_id,
            "bien_id": property_id,
            "payload": {"pieces": ["domicile"], "mode": "brouillon"},
            "idempotency_key": "missing-home-proof-001",
        }
        action = owner.post(
            "/api/internal/actions",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json=action_payload,
        )
        assert action.status_code == 201
        action_id = action.json()["id"]
        assert action.json()["statut"] == "a_valider"
        assert action.json()["necessite_validation"] is True

        replay = owner.post(
            "/api/internal/actions",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json=action_payload,
        )
        assert replay.status_code == 200
        assert replay.json()["id"] == action_id

        conflict = dict(action_payload)
        conflict["payload"] = {"pieces": ["identite"], "mode": "brouillon"}
        assert owner.post(
            "/api/internal/actions",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json=conflict,
        ).status_code == 409

        assert other_owner.get("/api/actions").json() == []
        assert other_owner.get(f"/api/actions/{action_id}").status_code == 404
        assert owner.post(
            f"/api/internal/actions/{action_id}/execute",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={"reference_execution": "provider-test-1"},
        ).status_code == 409

        approved = owner.post(
            f"/api/actions/{action_id}/approve",
            json={"motif": "Le propriétaire valide la préparation."},
        )
        assert approved.status_code == 200
        assert approved.json()["statut"] == "autorisee"

        executed = owner.post(
            f"/api/internal/actions/{action_id}/execute",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={
                "reference_execution": "provider-test-1",
                "resultat": {"mode": "test", "aucun_envoi": True},
            },
        )
        assert executed.status_code == 200
        assert executed.json()["statut"] == "executee"
        assert owner.post(
            f"/api/internal/actions/{action_id}/execute",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={"reference_execution": "provider-test-1"},
        ).json()["statut"] == "executee"

        audit = owner.get("/api/audit", params={"entite_id": action_id})
        assert audit.status_code == 200
        assert [event["evenement"] for event in audit.json()] == [
            "action_executee",
            "action_autorisee",
            "action_proposee",
        ]


def test_agent_action_can_be_rejected_without_execution():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        main.AGENT_INTERNAL_TOKEN = "agent-test-token"
        owner = TestClient(main.app)
        created = owner.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Owner",
                "email": "reject-owner@example.test",
                "mdp": "correct horse battery staple",
            },
        )
        workspace_id = created.json()["workspace_id"]
        action = owner.post(
            "/api/internal/actions",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={
                "workspace_id": workspace_id,
                "type_action": "preparer_relance",
                "libelle": "Préparer une relance",
                "niveau_risque": "transmission",
                "payload": {"texte": "brouillon"},
                "idempotency_key": "reject-follow-up-001",
            },
        )
        action_id = action.json()["id"]
        rejected = owner.post(
            f"/api/actions/{action_id}/reject",
            json={"motif": "Le propriétaire souhaite relire le dossier."},
        )
        assert rejected.status_code == 200
        assert rejected.json()["statut"] == "refusee"
        assert owner.post(
            f"/api/internal/actions/{action_id}/execute",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={},
        ).status_code == 409


def test_agent_scope_blocks_out_of_role_action_and_records_audit():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        main.AGENT_INTERNAL_TOKEN = "agent-test-token"
        owner = TestClient(main.app)
        created = owner.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Owner",
                "email": "scope-owner@example.test",
                "mdp": "correct horse battery staple",
            },
        )
        workspace_id = created.json()["workspace_id"]
        run = owner.post(
            "/api/internal/agent-runs",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={
                "workspace_id": workspace_id,
                "type_agent": "agent-completude",
                "mission": "Contrôler un dossier incomplet",
            },
        )
        assert run.status_code == 201
        run_id = run.json()["id"]

        blocked = owner.post(
            "/api/internal/actions",
            headers={"x-piaule-agent-token": "agent-test-token"},
            json={
                "workspace_id": workspace_id,
                "agent_run_id": run_id,
                "type_action": "publier_annonce",
                "libelle": "Publier une annonce",
                "niveau_risque": "transmission",
                "payload": {"titre": "Annonce hors rôle"},
                "idempotency_key": "scope-blocked-action-001",
            },
        )
        assert blocked.status_code == 403
        assert "hors du périmètre" in blocked.json()["detail"]
        events = owner.get("/api/audit", params={"entite_type": "agent_run", "entite_id": run_id})
        assert events.status_code == 200
        assert events.json()[0]["evenement"] == "agent_action_bloquee"
        assert events.json()[0]["metadata"]["action_demandee"] == "publier_annonce"


def test_selected_application_becomes_tenant_and_rejected_application_is_purged():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        main.AGENT_INTERNAL_TOKEN = "agent-test-token"
        owner = TestClient(main.app)
        assert owner.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Owner",
                "email": "lifecycle-owner@example.test",
                "mdp": "correct horse battery staple",
            },
        ).status_code == 200
        property_id = owner.post(
            "/api/biens",
            json={
                "nom": "Bien lifecycle",
                "type": "appartement",
                "adresse_ligne1": "5 rue du Test",
                "ville": "Lyon",
            },
        ).json()["id"]
        application_id = owner.post(
            f"/api/biens/{property_id}/candidatures",
            json={
                "candidat_prenom": "Alex",
                "candidat_nom": "Retenu",
                "candidat_email": "alex-retained@example.test",
            },
        ).json()["id"]

        for document_type in ("identite", "domicile", "situation_professionnelle", "ressources", "imposition"):
            uploaded = owner.post(
                f"/api/biens/{property_id}/candidatures/{application_id}/pieces",
                data={"nom": document_type, "type": document_type},
                files={"file": (f"{document_type}.pdf", b"%PDF-lifecycle", "application/pdf")},
            )
            assert uploaded.status_code == 201
            assert owner.put(
                f"/api/biens/{property_id}/candidatures/{application_id}/pieces/{uploaded.json()['id']}/verification",
                json={"statut": "valide"},
            ).status_code == 200
        assert owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/verifier"
        ).json()["statut"] == "complet"
        access = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/lien-candidat"
        )
        access_token = access.json()["url"].split("?access=", 1)[1]

        slot = owner.post(
            f"/api/biens/{property_id}/visite-creneaux",
            json={
                "debut": "2027-01-10T10:00:00+01:00",
                "fin": "2027-01-10T10:30:00+01:00",
                "mode": "sur_place",
            },
        )
        assert slot.status_code == 201
        proposed_visit = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/visites/proposer",
            json={"slot_id": slot.json()["id"]},
        )
        assert proposed_visit.status_code == 201
        confirmed_visit = owner.post(
            f"/api/candidature-acces/{access_token}/visites/{proposed_visit.json()['id']}/reponse",
            json={"accepte": True},
        )
        assert confirmed_visit.status_code == 200
        assert owner.get(
            f"/api/biens/{property_id}/candidatures/{application_id}"
        ).json()["statut"] == "visite_confirmee"

        before_visit = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/statut",
            json={"statut": "retenue"},
        )
        assert before_visit.status_code == 409

        completed_visit = owner.post(
            f"/api/biens/{property_id}/visites/{proposed_visit.json()['id']}/terminer",
            json={"note": "Visite réalisée, logement présenté au candidat."},
        )
        assert completed_visit.status_code == 200
        assert completed_visit.json()["statut"] == "terminee"

        selected = owner.post(
            f"/api/biens/{property_id}/candidatures/{application_id}/statut",
            json={"statut": "retenue", "motif": "Dossier sélectionné par le propriétaire."},
        )
        assert selected.status_code == 200
        assert selected.json()["locataire_id"]
        assert selected.json()["purge_prevue_le"] is None
        tenant = owner.get("/api/locataires").json()
        assert len(tenant) == 1
        assert tenant[0]["candidature_id"] == application_id
        assert tenant[0]["email"] == "alex-retained@example.test"
        assert owner.get(f"/api/candidature-acces/{access_token}").status_code == 404

        rejected_id = owner.post(
            f"/api/biens/{property_id}/candidatures",
            json={
                "candidat_prenom": "Sam",
                "candidat_nom": "Refuse",
                "candidat_email": "sam-rejected@example.test",
            },
        ).json()["id"]
        rejected_document = owner.post(
            f"/api/biens/{property_id}/candidatures/{rejected_id}/pieces",
            data={"nom": "Identité", "type": "identite"},
            files={"file": ("identite-rejected.pdf", b"%PDF-rejected", "application/pdf")},
        )
        rejected_document_id = rejected_document.json()["id"]
        with main._connect() as connection:
            rejected_filename = connection.execute(
                "SELECT stored_filename FROM application_documents WHERE id = ?",
                (rejected_document_id,),
            ).fetchone()["stored_filename"]
        assert (main.UPLOAD_DIRECTORY / rejected_filename).exists()
        rejected_link = owner.post(
            f"/api/biens/{property_id}/candidatures/{rejected_id}/lien-candidat"
        )
        rejected_token = rejected_link.json()["url"].split("?access=", 1)[1]
        refused = owner.post(
            f"/api/biens/{property_id}/candidatures/{rejected_id}/statut",
            json={"statut": "refusee", "motif": "Candidature non retenue."},
        )
        assert refused.status_code == 200
        assert refused.json()["purge_prevue_le"]

        with main._connect() as connection:
            connection.execute(
                "UPDATE owner_applications SET purge_after = ? WHERE id = ?",
                ("2000-01-01T00:00:00Z", rejected_id),
            )
            connection.commit()
        purged = owner.post(
            "/api/internal/candidatures/purger",
            headers={"x-piaule-agent-token": "agent-test-token"},
        )
        assert purged.status_code == 200
        assert rejected_id in purged.json()["candidatures_purgees"]
        anonymized = owner.get(f"/api/biens/{property_id}/candidatures/{rejected_id}")
        assert anonymized.status_code == 200
        assert anonymized.json()["candidat_nom"] == "supprimé"
        assert anonymized.json()["candidat_email"] == ""
        assert anonymized.json()["anonymisee_le"]
        assert owner.get(f"/api/candidature-acces/{rejected_token}").status_code == 404
        assert owner.get(
            f"/api/biens/{property_id}/candidatures/{rejected_id}/pieces"
        ).json() == []
        assert not (main.UPLOAD_DIRECTORY / rejected_filename).exists()


def test_inspection_lifecycle_checks_rooms_entries_and_prepares_signature():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        owner = TestClient(main.app)
        created = owner.post(
            "/api/compte",
            json={
                "action": "creer",
                "prenom": "Owner",
                "email": "inspection-owner@example.test",
                "mdp": "correct horse battery staple",
            },
        )
        assert created.status_code == 200
        workspace_id = created.json()["workspace_id"]
        property_id = owner.post(
            "/api/biens",
            json={
                "nom": "Appartement état des lieux",
                "type": "appartement",
                "adresse_ligne1": "1 rue des pièces",
                "ville": "Lyon",
            },
        ).json()["id"]
        application = owner.post(
            f"/api/biens/{property_id}/candidatures",
            json={
                "candidat_prenom": "Alex",
                "candidat_nom": "Retenu",
                "candidat_email": "alex-inspection@example.test",
            },
        )
        assert application.status_code == 201
        application_id = application.json()["id"]
        tenant_id = "locataire-inspection-test"
        with main._connect() as connection:
            connection.execute(
                "UPDATE owner_applications SET statut = 'retenue' WHERE id = ? AND workspace_id = ?",
                (application_id, workspace_id),
            )
            connection.execute(
                """
                INSERT INTO owner_tenants(
                    id, workspace_id, property_id, application_id, prenom, nom, email,
                    telephone, statut, retenu_le, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'Alex', 'Retenu', 'alex-inspection@example.test', '', 'actif', ?, ?, ?)
                """,
                (tenant_id, workspace_id, property_id, application_id, main._iso_now(), main._iso_now(), main._iso_now()),
            )
            connection.commit()

        inspection = owner.post(
            f"/api/biens/{property_id}/etats-des-lieux",
            json={
                "type": "entree",
                "identifiant": "EDL-ENTREE-001",
                "candidature_id": application_id,
                "locataire_id": tenant_id,
            },
        )
        assert inspection.status_code == 201
        inspection_id = inspection.json()["id"]
        room = owner.post(
            f"/api/biens/{property_id}/etats-des-lieux/{inspection_id}/pieces",
            json={"nom": "Séjour"},
        )
        assert room.status_code == 201
        room_id = room.json()["id"]
        entry = owner.post(
            f"/api/biens/{property_id}/etats-des-lieux/{inspection_id}/pieces/{room_id}/elements",
            json={"categorie": "Murs", "libelle": "Peinture", "etat": "non_verifie"},
        )
        assert entry.status_code == 201
        entry_id = entry.json()["id"]

        incomplete = owner.post(f"/api/biens/{property_id}/etats-des-lieux/{inspection_id}/verifier")
        assert incomplete.status_code == 200
        assert incomplete.json()["statut"] == "en_cours"
        assert any("non vérifié" in item for item in incomplete.json()["bloquants"])
        assert owner.post(
            f"/api/biens/{property_id}/etats-des-lieux/{inspection_id}/preparer-signature"
        ).status_code == 409

        updated = owner.put(
            f"/api/biens/{property_id}/etats-des-lieux/{inspection_id}/pieces/{room_id}/elements/{entry_id}",
            json={
                "categorie": "Murs",
                "libelle": "Peinture",
                "etat": "bon",
                "observation": "Aucune dégradation visible.",
            },
        )
        assert updated.status_code == 200
        assert owner.post(
            f"/api/biens/{property_id}/etats-des-lieux/{inspection_id}/compteurs",
            json={"type_compteur": "electricite", "index": "01234", "unite": "kWh"},
        ).status_code == 201
        assert owner.post(
            f"/api/biens/{property_id}/etats-des-lieux/{inspection_id}/cles",
            json={"type_cle": "Porte d'entrée", "quantite": 2},
        ).status_code == 201
        photo = owner.post(
            f"/api/biens/{property_id}/etats-des-lieux/{inspection_id}/photos",
            files={"fichier": ("sejour.jpg", b"photo", "image/jpeg")},
            data={"piece_id": room_id, "entry_id": entry_id, "note": "Vue générale"},
        )
        assert photo.status_code == 201

        ready = owner.post(f"/api/biens/{property_id}/etats-des-lieux/{inspection_id}/verifier")
        assert ready.status_code == 200
        assert ready.json()["pret_signature"] is True
        prepared = owner.post(
            f"/api/biens/{property_id}/etats-des-lieux/{inspection_id}/preparer-signature"
        )
        assert prepared.status_code == 200
        assert prepared.json()["statut"] == "pret_signature"
        assert len(prepared.json()["rooms"]) == 1
        assert len(prepared.json()["entries"]) == 1
        assert len(prepared.json()["media"]) == 1
        listed = owner.get(f"/api/biens/{property_id}/etats-des-lieux")
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == inspection_id


def test_dashboard_summary_is_workspace_scoped_and_aggregates_owner_activity():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        main.AGENT_INTERNAL_TOKEN = "dashboard-agent-token"
        owner = TestClient(main.app)
        other = TestClient(main.app)
        owner_created = owner.post(
            "/api/compte",
            json={"action": "creer", "prenom": "Owner", "email": "dashboard-owner@example.test", "mdp": "correct horse battery staple"},
        )
        other_created = other.post(
            "/api/compte",
            json={"action": "creer", "prenom": "Other", "email": "dashboard-other@example.test", "mdp": "correct horse battery staple"},
        )
        assert owner_created.status_code == 200
        assert other_created.status_code == 200
        workspace_id = owner_created.json()["workspace_id"]
        property_id = owner.post(
            "/api/biens",
            json={"nom": "Bien dashboard", "type": "appartement", "adresse_ligne1": "1 rue accueil", "ville": "Lyon", "statut": "vacant"},
        ).json()["id"]
        application = owner.post(
            f"/api/biens/{property_id}/candidatures",
            json={"candidat_prenom": "Alex", "candidat_nom": "Dashboard", "candidat_email": "alex-dashboard@example.test", "statut": "a_completer"},
        )
        assert application.status_code == 201
        application_id = application.json()["id"]
        inspection = owner.post(f"/api/biens/{property_id}/etats-des-lieux", json={"type": "entree"})
        assert inspection.status_code == 201

        with main._connect() as connection:
            slot_id = "slot-dashboard"
            visit_id = "visit-dashboard"
            future = "2099-01-01T10:00:00+01:00"
            connection.execute(
                """
                INSERT INTO visit_slots(id, workspace_id, property_id, starts_at, ends_at, timezone, mode, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'Europe/Paris', 'sur_place', 'reserve', ?)
                """,
                (slot_id, workspace_id, property_id, future, "2099-01-01T11:00:00+01:00", main._iso_now()),
            )
            connection.execute(
                """
                INSERT INTO visits(id, workspace_id, property_id, application_id, slot_id, status, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'confirmee', 'agent', ?, ?)
                """,
                (visit_id, workspace_id, property_id, application_id, slot_id, main._iso_now(), main._iso_now()),
            )
            connection.commit()

        run = owner.post(
            "/api/internal/agent-runs",
            headers={"x-piaule-agent-token": "dashboard-agent-token"},
            json={"workspace_id": workspace_id, "type_agent": "agent-completude", "mission": "Vérifier le dossier dashboard", "cible_type": "candidature", "cible_id": application_id},
        )
        assert run.status_code == 201
        action = owner.post(
            "/api/internal/actions",
            headers={"x-piaule-agent-token": "dashboard-agent-token"},
            json={
                "workspace_id": workspace_id,
                "type_action": "preparer_message_candidat",
                "libelle": "Demander une pièce",
                "description": "Une pièce manque.",
                "niveau_risque": "transmission",
                "cible_type": "candidature",
                "cible_id": application_id,
                "bien_id": property_id,
                "agent_run_id": run.json()["id"],
                "idempotency_key": "dashboard-action-1",
            },
        )
        assert action.status_code == 201

        dashboard = owner.get("/api/dashboard")
        assert dashboard.status_code == 200
        data = dashboard.json()
        assert data["biens"] == {"total": 1, "preparation": 0, "vacants": 1, "occupes": 0, "archives": 0}
        assert data["candidatures"]["total"] == 1
        assert data["candidatures"]["par_statut"]["a_completer"] == 1
        assert data["dossiers_incomplets"] == 1
        assert data["visites_a_venir"] == 1
        assert data["etats_des_lieux_en_cours"] == 1
        assert data["actions_en_attente"] == 1
        assert len(data["activite_agents"]) == 1
        assert data["activite_agents"][0]["type_agent"] == "agent-completude"
        assert data["mis_a_jour_le"]

        other_dashboard = other.get("/api/dashboard")
        assert other_dashboard.status_code == 200
        other_data = other_dashboard.json()
        assert other_data["biens"]["total"] == 0
        assert other_data["candidatures"]["total"] == 0
        assert other_data["actions_en_attente"] == 0
        assert other_data["activite_agents"] == []


def test_application_search_supports_filters_pagination_and_workspace_isolation():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        main.DATABASE_PATH = root / "test.sqlite3"
        main.UPLOAD_DIRECTORY = root / "uploads"
        owner = TestClient(main.app)
        other = TestClient(main.app)
        first = owner.post(
            "/api/compte",
            json={"action": "creer", "prenom": "Owner", "email": "pagination-owner@example.test", "mdp": "correct horse battery staple"},
        )
        second = other.post(
            "/api/compte",
            json={"action": "creer", "prenom": "Other", "email": "pagination-other@example.test", "mdp": "correct horse battery staple"},
        )
        assert first.status_code == 200
        assert second.status_code == 200
        property_id = owner.post(
            "/api/biens",
            json={"nom": "Bien pagination", "type": "appartement", "adresse_ligne1": "1 rue recherche", "ville": "Lyon"},
        ).json()["id"]
        for prenom, nom, statut, source in [
            ("Zoé", "Martin", "recue", "email"),
            ("Alex", "Bernard", "a_completer", "import"),
            ("Sam", "Durand", "prete", "email"),
        ]:
            created = owner.post(
                f"/api/biens/{property_id}/candidatures",
                json={
                    "candidat_prenom": prenom,
                    "candidat_nom": nom,
                    "candidat_email": f"{prenom.lower()}@example.test",
                    "statut": statut,
                    "source": source,
                },
            )
            assert created.status_code == 201

        page = owner.get("/api/candidatures-page", params={"page": 2, "page_size": 2})
        assert page.status_code == 200
        assert page.json()["total"] == 3
        assert page.json()["pages"] == 2
        assert page.json()["page"] == 2
        assert len(page.json()["items"]) == 1

        filtered = owner.get(
            f"/api/biens/{property_id}/candidatures-page",
            params={"statut": "a_completer", "source": "import", "search": "alex", "page_size": 10},
        )
        assert filtered.status_code == 200
        assert filtered.json()["total"] == 1
        assert filtered.json()["items"][0]["candidat_nom"] == "Bernard"

        by_name = owner.get(
            f"/api/biens/{property_id}/candidatures-page",
            params={"sort": "nom", "page_size": 10},
        )
        assert [item["candidat_nom"] for item in by_name.json()["items"]] == ["Bernard", "Durand", "Martin"]

        other_page = other.get("/api/candidatures-page")
        assert other_page.status_code == 200
        assert other_page.json()["total"] == 0
        assert other_page.json()["items"] == []
