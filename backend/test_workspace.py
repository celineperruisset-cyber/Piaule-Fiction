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
        assert identity.json()["statut"] == "recu"
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
