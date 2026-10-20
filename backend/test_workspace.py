import tempfile
import os
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
