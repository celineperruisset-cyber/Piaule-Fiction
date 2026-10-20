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

## Candidatures disponibles

Le pipeline propriétaire est disponible avec :

- `GET /api/candidatures` pour la vue portefeuille ;
- `GET /api/biens/{id}/candidatures` pour les candidatures d’un bien ;
- `POST /api/biens/{id}/candidatures` pour recevoir une candidature ;
- `GET` et `PUT /api/biens/{id}/candidatures/{application_id}` pour une candidature précise.

Une candidature est rattachée au workspace, au bien et éventuellement au lot. Elle conserve la source, la référence externe, les coordonnées minimales du candidat, les notes privées, les dates et un statut explicable : `recue`, `a_completer`, `en_verification`, `prete`, `visite_proposee`, `visite_confirmee`, `retenue`, `refusee` ou `retiree`. Une adresse e-mail répétée pour le même bien/lot déclenche `doublon_possible` au lieu de supprimer silencieusement l’information.

Toutes ces routes exigent une session propriétaire et filtrent par `workspace_id`. Un lot possède un identifiant unique dans son bien, ses caractéristiques principales, ses paramètres financiers et un statut de cycle de vie (`brouillon`, `disponible`, `occupe`, `archive`).

## Réception des candidatures depuis les annonces

Une annonce externe peut afficher une adresse de réception dédiée, générée par Piaule Fiction pour un bien ou un lot. Le propriétaire peut la créer et la consulter avec :

- `GET /api/biens/{id}/canaux-candidatures` pour lister les canaux d’un bien ;
- `POST /api/biens/{id}/canaux-candidatures` pour créer une adresse liée à une publication ou à un lot ;
- `GET /api/candidatures/inbox` pour consulter les messages entrants bruts du workspace.

Le fournisseur de messagerie entrant transmet ensuite un message normalisé à `POST /api/internal/candidatures/inbound`. Cette route est protégée par l’en-tête `x-piaule-inbound-token`, comparé à `PIAULE_INBOUND_WEBHOOK_TOKEN`, et déduplique les messages avec leur `message_id` externe. Un message est d’abord enregistré avec le statut `recue` : il ne devient pas automatiquement une candidature fiable.

Après extraction des informations, contrôle des pièces et détection des incohérences par le futur agent, l’API permet de rattacher le message à une candidature avec `PUT /api/candidatures/inbox/{message_id}/associer`. Le rattachement reste limité au même workspace et au même bien, afin d’éviter qu’un e-mail reçu pour une annonce soit attaché au mauvais dossier.

Cette brique prépare le contrat d’intégration ; elle ne configure pas encore la réception réelle du domaine, le fournisseur de boîte e-mail, l’analyse des pièces jointes ni les relances automatiques. Ces éléments seront branchés séparément, après choix du fournisseur entrant.

La fiche comprend maintenant les types de location, équipements, disponibilité, photos, visibilité de l’adresse, informations DPE, mode de détention et premiers champs de copropriété. Les routes `POST/GET/PUT /api/biens/{id}/suivis` permettent de suivre diagnostics, assurances, contrats fournisseurs et documents de copropriété avec leurs échéances. `GET /api/echeances` remonte les éléments expirés ou arrivant à échéance.

La comptabilité, la fiscalité, le financement, la rentabilité et les tableaux financiers ne font pas partie du produit. Les champs de loyer, charges et dépôt servent uniquement à configurer une mise en location et ses règles opérationnelles.
