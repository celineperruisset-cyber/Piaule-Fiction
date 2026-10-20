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

Les transitions sont contrôlées par `POST /api/biens/{id}/candidatures/{application_id}/statut`, avec un `statut` cible et un `motif`. Une candidature ne peut pas être proposée en visite, confirmée ou retenue tant que son moteur de complétude ne la considère pas `complet`. L’historique lisible est disponible avec `GET /api/biens/{id}/candidatures/{application_id}/historique` et conserve l’ancien statut, le nouveau statut, la source et le motif. Les décisions de refus et de retenue restent des actions du propriétaire ; les recalculs de complétude et les retours DossierFacile sont enregistrés comme événements système.

Toutes ces routes exigent une session propriétaire et filtrent par `workspace_id`. Un lot possède un identifiant unique dans son bien, ses caractéristiques principales, ses paramètres financiers et un statut de cycle de vie (`brouillon`, `disponible`, `occupe`, `archive`).

## Réception des candidatures depuis les annonces

Une annonce externe peut afficher une adresse de réception dédiée, générée par Piaule Fiction pour un bien ou un lot. Le propriétaire peut la créer et la consulter avec :

- `GET /api/biens/{id}/canaux-candidatures` pour lister les canaux d’un bien ;
- `POST /api/biens/{id}/canaux-candidatures` pour créer une adresse liée à une publication ou à un lot ;
- `GET /api/candidatures/inbox` pour consulter les messages entrants bruts du workspace.

Le fournisseur de messagerie entrant transmet ensuite un message normalisé à `POST /api/internal/candidatures/inbound`. Cette route est protégée par l’en-tête `x-piaule-inbound-token`, comparé à `PIAULE_INBOUND_WEBHOOK_TOKEN`, et déduplique les messages avec leur `message_id` externe. Un message est d’abord enregistré avec le statut `recue` : il ne devient pas automatiquement une candidature fiable.

Après extraction des informations, contrôle des pièces et détection des incohérences par le futur agent, l’API permet de rattacher le message à une candidature avec `PUT /api/candidatures/inbox/{message_id}/associer`. Le rattachement reste limité au même workspace et au même bien, afin d’éviter qu’un e-mail reçu pour une annonce soit attaché au mauvais dossier.

Pour une boîte Hostinger, le worker peut lire les messages non lus avec `POST /api/internal/candidatures/inbox/synchroniser`. Il reconnaît les adresses de canaux connues, importe le texte, ignore les messages destinés à une autre adresse et stocke les pièces jointes PDF/JPG/PNG acceptées jusqu’à 100 Mo avant de les rattacher au dossier lorsqu’une correspondance unique est trouvée. La route est protégée par `x-piaule-email-token` et `PIAULE_EMAIL_INTERNAL_TOKEN`.

## Vérification DossierFacile Connect

Piaule Fiction prépare la liaison officielle DossierFacile Connect pour une candidature reçue par e-mail. Le propriétaire peut créer une demande avec `POST /api/biens/{id}/candidatures/{application_id}/dossier-facile/connect`. La réponse contient une URL OAuth2 à transmettre au candidat. Le candidat se connecte à DossierFacile ou via FranceConnect et consent explicitement au partage de son dossier.

Le callback `GET /api/dossier-facile/callback` échange le code à usage unique, récupère le profil DossierFacile et enregistre uniquement un résumé de statut et de progression. Les pièces originales restent gérées par DossierFacile. Le propriétaire consulte l’état avec `GET /api/biens/{id}/candidatures/{application_id}/dossier-facile`.

Le webhook `POST /api/internal/dossier-facile/webhook` met à jour le statut lorsqu’un dossier est créé, complété, validé, décliné, supprimé ou lorsque l’accès partenaire est révoqué. Il est protégé par `x-api-key` et `PIAULE_DOSSIER_FACILE_WEBHOOK_TOKEN`. Un statut DossierFacile validé peut faire passer la candidature à `prete` ; un dossier incomplet, décliné ou révoqué remonte comme exception à traiter.

Le connecteur reste désactivé par défaut. DossierFacile exige un partenariat, une charte et des identifiants de préproduction avant les tests ; l’application ne doit donc jamais simuler une validation officielle lorsqu’elle n’est pas connectée.

## Pièces et complétude d’une candidature

Chaque bien possède une politique de preuve documentaire : `standard`, `renforcee` ou `officielle`. Elle se lit et se modifie avec `GET/PUT /api/biens/{id}/politique-verification`. Elle définit les sources que l'agent peut proposer, mais ne permet pas de demander une pièce interdite par la réglementation. La politique est choisie au niveau du bien et s'applique de la même manière à ses candidatures.

Les pièces sont rattachées à la candidature, au bien et au workspace. Les cinq catégories minimales suivies par le moteur sont `identite`, `domicile`, `situation_professionnelle`, `ressources` et `imposition`. `garant` et `autre` sont disponibles en complément.

Les routes sont :

- `GET /api/biens/{id}/candidatures/{application_id}/pieces` pour lister les pièces privées ;
- `POST /api/biens/{id}/candidatures/{application_id}/pieces` pour déposer un PDF, JPG ou PNG de 100 Mo maximum par fichier ;
- `PUT /api/biens/{id}/candidatures/{application_id}/pieces/{document_id}/verification` pour changer le statut de vérification ;
- `POST /api/biens/{id}/candidatures/{application_id}/pieces/{document_id}/analyser` pour lancer les contrôles techniques ;
- `GET /api/biens/{id}/candidatures/{application_id}/pieces/{document_id}/controles` pour consulter les contrôles effectués ;
- `POST /api/biens/{id}/candidatures/{application_id}/pieces/{document_id}/verifications` pour préparer une demande de preuve externe ;
- `GET /api/biens/{id}/candidatures/{application_id}/verifications` pour suivre les demandes de preuve ;
- `POST /api/candidature-acces/{token}/verifications/{request_id}/consentement` pour recueillir le consentement du candidat ;
- `POST /api/internal/verifications/{request_id}/result` pour recevoir le résultat signé d'un connecteur, avec `x-piaule-verification-token` ;
- `GET /api/biens/{id}/candidatures/{application_id}/completude` pour lire le résultat ;
- `POST /api/biens/{id}/candidatures/{application_id}/verifier` pour recalculer et synchroniser le statut de la candidature.

Une pièce conserve son type, sa provenance (`email`, `dossier_facile`, `portail_candidat`, `import` ou `autre`), son empreinte SHA-256, son statut et sa date d'expiration. Les statuts sont `recu`, `en_verification`, `valide`, `a_corriger`, `expire` et `refuse`. Elle conserve aussi le niveau de preuve (`non_verifie`, `controles_techniques`, `revue_humaine` ou `source_officielle`) et les anomalies détectées.

Le moteur de pré-vérification est déterministe : il vérifie la présence du fichier, sa taille stockée, l'accord extension/MIME, sa signature PDF/JPG/PNG, sa date d'expiration, les doublons dans le dossier et une éventuelle incompatibilité probable entre le nom du fichier et la catégorie déclarée. Une anomalie bloque ou place la pièce `a_corriger`; un contrôle technique réussi la place `en_verification`, jamais `valide` automatiquement. Le moteur conserve chaque résultat et sa version.

La pré-vérification locale ne certifie pas l'authenticité d'un document, l'identité du candidat, ses revenus ou l'absence de retouche. Ces éléments sont signalés comme `non_verifiable_localement` tant qu'aucun extracteur contrôlé, source officielle ou examinateur humain n'a fourni une preuve. Les niveaux de preuve disponibles sont `non_verifie`, `controles_techniques`, `source_partenaire`, `revue_humaine` et `source_officielle`. Un dossier DossierFacile officiellement vérifié peut couvrir les catégories requises avec la mention `verifiee_par_dossier_facile`, sans recopier les documents originaux dans Piaule Fiction.

Une demande vers France Identité, la DGFiP, DossierFacile ou un employeur commence par `en_attente_consentement`. Après accord depuis le portail candidat, elle passe à `en_attente_source`. Le backend n'accorde le niveau `source_officielle` ou `source_partenaire` qu'après réception d'un résultat par le canal interne authentifié ; il ne simule aucune réponse de fournisseur.

Le dépôt exposé dans cette première tranche est protégé par la session propriétaire. Le lien candidat sécurisé et le dépôt autonome depuis l’espace candidat seront ajoutés sur cette même table, afin de ne pas créer un second modèle documentaire.

## Échange avec le candidat

Le propriétaire peut créer un lien temporaire avec `POST /api/biens/{id}/candidatures/{application_id}/lien-candidat`. La réponse contient une URL à insérer dans l’e-mail envoyé au candidat. Le jeton brut n’est jamais stocké en base : seul son hash est conservé, avec une expiration de trente jours et une révocation des anciens liens lors de la création d’un nouveau lien.

Le portail candidat expose uniquement :

- `GET /api/candidature-acces/{token}` pour voir le bien et l’état de complétude ;
- `POST /api/candidature-acces/{token}/pieces` pour déposer une pièce ;
- `POST /api/candidature-acces/{token}/messages` pour répondre à une demande.

Les messages du candidat sont stockés dans `candidate_messages` et restent rattachés au bon workspace, bien et dossier. Le propriétaire peut consulter la conversation et préparer une réponse via `GET/POST /api/biens/{id}/candidatures/{application_id}/messages`. Une réponse sortante est d’abord marquée `a_envoyer`. Le worker SMTP traite la file avec `POST /api/internal/candidatures/outbox/traiter`, enregistre `envoye` ou `erreur`, le nombre d’essais et la dernière erreur.

L’agent peut préparer une demande ciblée avec `POST /api/biens/{id}/candidatures/{application_id}/agent/relancer-completude`. Cette action ne demande que les catégories manquantes, expirées, refusées ou à corriger, crée un message sortant `source=agent` dans la file d’envoi et génère un nouveau lien de dépôt valable trente jours. Elle est idempotente pour un même ensemble de pièces afin d’éviter les relances en double. L’envoi de cette demande ne nécessite pas de validation du propriétaire une fois le fournisseur d’e-mails configuré. L’agent ne peut pas passer la candidature à `refusee` : cette décision reste une action explicite du propriétaire.

Lorsqu’un e-mail entrant arrive sur une adresse d’annonce, le backend tente une association déterministe avec une candidature du même bien et de la même adresse e-mail. Une correspondance unique crée aussi un message entrant dans la conversation. Une correspondance ambiguë reste dans l’inbox pour traitement par l’agent.

La fiche comprend maintenant les types de location, équipements, disponibilité, photos, visibilité de l’adresse, informations DPE, mode de détention et premiers champs de copropriété. Les routes `POST/GET/PUT /api/biens/{id}/suivis` permettent de suivre diagnostics, assurances, contrats fournisseurs et documents de copropriété avec leurs échéances. `GET /api/echeances` remonte les éléments expirés ou arrivant à échéance.

La comptabilité, la fiscalité, le financement, la rentabilité et les tableaux financiers ne font pas partie du produit. Les champs de loyer, charges et dépôt servent uniquement à configurer une mise en location et ses règles opérationnelles.
