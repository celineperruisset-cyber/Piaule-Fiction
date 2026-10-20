# Contrat API — workspace propriétaire

## Ressources

```text
workspace
  ├── members
  ├── properties / lots
  ├── applications
  │     ├── candidate reference
  │     ├── documents
  │     └── completeness / coherence findings
  ├── agent runs
  ├── actions / approvals
  ├── visits
  └── audit events
```

## Principes

Toutes les ressources portent un `workspace_id`. Une candidature porte aussi un `property_id`. Un document ne devient jamais accessible uniquement parce qu’un modèle l’a reconnu : le rôle, le rattachement, le consentement et la durée d’accès sont vérifiés par l’API.

Les agents écrivent des propositions et des preuves. Les transmissions externes passent par `actions`, avec un aperçu immuable, une autorisation, une idempotence et un événement d’audit.

## Première tranche

1. Ajouter les tables `workspaces`, `properties`, `applications`, `agent_runs`, `actions` et `audit_events`.
2. Ajouter les routes de lecture propriétaire et les contrôles d’isolation.
3. Ajouter la file de validation sans exécution externe.
4. Relier le dashboard à des réponses persistées synthétiques.
5. Ajouter les connecteurs un par un, uniquement après documentation des permissions.

## Biens et lots disponibles

Le premier domaine persistant est maintenant disponible :

- `GET /api/biens` et `POST /api/biens` pour le portefeuille du propriétaire ;
- `GET /api/biens/{id}` et `PUT /api/biens/{id}` pour la fiche d’un bien ;
- `GET /api/biens/{id}/lots` et `POST /api/biens/{id}/lots` pour ses unités louables ;
- `GET` et `PUT /api/biens/{id}/lots/{lot_id}` pour une unité précise.

Toutes ces routes exigent une session propriétaire et filtrent par `workspace_id`. Un lot possède un identifiant unique dans son bien, ses caractéristiques principales, ses paramètres financiers et un statut de cycle de vie (`brouillon`, `disponible`, `occupe`, `archive`).

Cette première fiche est volontairement minimale. Les extensions prévues sont documentées dans [`PROPERTY_MANAGEMENT_RESEARCH.md`](PROPERTY_MANAGEMENT_RESEARCH.md) : types de location, équipements, disponibilité, diagnostics et échéances, puis immeubles, tantièmes, copropriété et rentabilité.
