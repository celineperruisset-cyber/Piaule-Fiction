# Backend Piaule Fiction

Cette API devient le socle du workspace propriétaire. Le slice historique compte/session/documents reste réutilisable, mais les prochaines routes doivent être rattachées à un workspace propriétaire et à son portefeuille de biens.

## Domaine cible

- `workspace` et membres autorisés ;
- `property` / `lot` et règles du bien ;
- `application` rattachée à un bien et à une source ;
- `document` avec statut, provenance et accès ;
- `agent_run`, `action`, `approval` et `audit_event` ;
- `visit` et disponibilités ;
- `connector` avec permissions et révocation.

Le candidat reste un participant du dossier. Les données fictives utilisées par les tests ne doivent jamais être interprétées comme des décisions de solvabilité ou d’authenticité prises par l’IA.

## Lancer localement

```bash
python3 -m pip install -r backend/requirements.txt
PIAULE_STATE_DIRECTORY=.local-state uvicorn backend.main:app --reload --port 8000
```

Routes de socle actuellement conservées : `GET /health`, compte/session, profil, documents privés et source synthétique. Le premier bloc propriétaire est maintenant disponible : `GET /api/workspace`, `PUT /api/workspace` et `GET /api/workspace/membres`. Les routes biens, candidatures, validations et audit suivent le contrat décrit dans [`docs/API_OWNER_WORKSPACE_CONTRACT.md`](../docs/API_OWNER_WORKSPACE_CONTRACT.md).

La base `.local-state/` et les uploads privés ne doivent jamais être versionnés. Aucun connecteur réel, message, publication, signature ou paiement ne doit être activé avant d’avoir une permission explicite, une file de validation et un audit.
