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
