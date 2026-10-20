# Contrat de compte et workspace propriétaire

## Objectif

Le compte sert à isoler un workspace propriétaire et les personnes explicitement autorisées à y travailler. Les anciens endpoints de session peuvent être conservés pour compatibilité pendant la migration, mais le domaine cible est le workspace.

## Ressources cibles

- `GET /api/moi` : identité et workspace courant ;
- `GET /api/workspace` / `PUT /api/workspace` : paramètres du workspace ;
- `GET /api/biens` / `POST /api/biens` : portefeuille ;
- `GET /api/biens/{id}/candidatures` : pipeline rattaché au bien ;
- `GET /api/actions` : propositions et validations ;
- `POST /api/actions/{id}/approve` ou `/reject` : décision autorisée et auditée ;
- `GET /api/agents/runs` : activité et preuves ;
- `GET /api/audit` : journal filtré par workspace.

## Règles

Chaque route vérifie l’identité, le workspace, le rôle et la permission. Une route de lecture ne doit jamais être utilisée pour déclencher une transmission. Les actions sensibles exigent un aperçu idempotent, une confirmation et un événement d’audit.
