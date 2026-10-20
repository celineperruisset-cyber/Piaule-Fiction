# Architecture de confiance — Piaule Fiction

## Architecture fonctionnelle

```text
Workspace propriétaire
  ├── Portefeuille
  │     ├── Bien / lot / règles
  │     └── Annonce et canaux autorisés
  ├── Dossiers
  │     ├── Candidature / source / doublon
  │     ├── Pièces / provenance / statut
  │     └── Complétude / cohérence / preuves
  ├── Agents
  │     ├── exécution limitée
  │     ├── proposition structurée
  │     └── journal et escalade
  ├── Actions
  │     ├── brouillon
  │     ├── validation propriétaire ou partenaire
  │     └── transmission autorisée
  └── Visites / documents / audit
```

## Le contrat d’un agent

Chaque exécution reçoit un workspace, un objet métier, une intention et une permission. Elle rend : faits extraits, sources, incertitudes, proposition, données qui seraient transmises, niveau de risque et prochaine action. Un agent ne peut pas élargir seul sa mission.

## Séparation des responsabilités

- le modèle peut extraire et rédiger ;
- les règles déterministes contrôlent champs, dates, permissions, pièces autorisées et doublons ;
- le propriétaire ou le partenaire habilité décide des actes sensibles ;
- l’audit conserve proposition, validation, envoi, résultat et révocation.

## Sécurité

Les données sont isolées par workspace. Les documents restent privés, avec accès temporaire et journalisé. Les secrets de connecteurs sont chiffrés et révocables. Une suppression doit couvrir base, stockage, index, caches et sauvegardes selon la politique de rétention annoncée.

## États d’une action

`proposée → à vérifier → autorisée → exécutée → confirmée` ou `refusée / expirée / bloquée`.

Une action externe, un partage de pièce, une signature, un paiement, une publication ou un acte réglementé ne peut pas passer directement de `proposée` à `exécutée`.
