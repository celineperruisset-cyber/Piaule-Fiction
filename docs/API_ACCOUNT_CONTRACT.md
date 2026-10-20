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

Authentification externe : `GET /api/auth/google/start` et `GET /api/auth/google/callback` utilisent Google OpenID Connect avec `openid email profile`. Aucun scope Gmail n’est demandé. Récupération de compte : `POST /api/mot-de-passe-oublie` prépare un lien à usage unique, puis `POST /api/mot-de-passe-reinitialiser` change le mot de passe et révoque les sessions.

Extension prévue : récupération par SMS sur un numéro préalablement vérifié. Elle nécessitera un fournisseur SMS, un code à usage unique avec expiration, une limite de tentatives et un journal d’audit. Elle viendra après la récupération par e-mail et ne sera pas activée par défaut.

## Règles

Chaque route vérifie l’identité, le workspace, le rôle et la permission. Une route de lecture ne doit jamais être utilisée pour déclencher une transmission. Les actions sensibles exigent un aperçu idempotent, une confirmation et un événement d’audit.
