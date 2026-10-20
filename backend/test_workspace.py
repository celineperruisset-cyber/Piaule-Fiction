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
