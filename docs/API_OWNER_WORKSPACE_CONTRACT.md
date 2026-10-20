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
  ├── private agent team / orchestrator messages / contracts
  ├── publication connections / publication jobs / first validation
  ├── actions / approvals
  ├── visits
  └── audit events
```

## Principes

Toutes les ressources portent un `workspace_id`. Une candidature porte aussi un `property_id`. Un document ne devient jamais accessible uniquement parce qu’un modèle l’a reconnu : le rôle, le rattachement, le consentement et la durée d’accès sont vérifiés par l’API.

Les agents écrivent des propositions et des preuves. Les transmissions externes passent par `actions`, avec un aperçu immuable, une autorisation, une idempotence et un événement d’audit.

## Équipe privée du propriétaire

Chaque création de compte provisionne le même catalogue fonctionnel d'agents dans une instance propre au workspace : Orchestrateur, Bien, Diffusion, Candidatures, Complétude, Confiance, Comparaison, Visites, Communication, Conformité et Suivi. Chaque agent conserve un contrat versionné (`entrees`, `sorties`, `actions`, `escalades`) dans `workspace_agents.contract_json`. L'identifiant, les missions, les messages et les futures mémoires restent isolés par `workspace_id`.

Le propriétaire consulte l'équipe avec `GET /api/agents`. L'Orchestrateur est son point de contact :

- `POST /api/agents/orchestrateur/messages` reçoit une demande et crée une mission `queued` ;
- `GET /api/agents/orchestrateur/messages` relit les demandes et réponses ;
- `GET /api/agents/{agent_id}` affiche un agent et son contrat de son propre workspace.

Une demande est conservée dans `agent_messages`, rattachée à `agent_runs` et auditée. Le worker interne `POST /api/internal/agent-runs/process-next` consomme une mission Orchestrateur et crée des sous-missions spécialisées avec un routage déterministe. Une pièce reçue par le portail candidat ou l'inbox e-mail met automatiquement en file une mission `agent-completude` et une mission `agent-confiance`, avec déduplication des missions `queued` ou `running`. `POST /api/internal/agent-runs/process-next-completude` calcule les pièces manquantes et met en file un message ciblé au candidat avec un lien valable trente jours. `POST /api/internal/agent-runs/process-next-confiance` réanalyse les contrôles et prépare les demandes de preuve externe. L'envoi matériel reste effectué par le worker SMTP, après passage par la boîte de sortie. Le fournisseur LLM et les connecteurs officiels restent derrière ces contrats.

## Publication et autorisation d'un compte propriétaire

L'Agent Diffusion prépare les annonces et les transmet uniquement à des canaux autorisés. Le backend sépare le compte de diffusion, la première publication et l'autorisation d'automatiser les suivantes.

Les routes sont :

- `GET /api/diffusion/connexions` pour lister les comptes du workspace ;
- `POST /api/diffusion/connexions` pour enregistrer un compte à connecter, sans mot de passe ;
- `POST /api/internal/diffusion/connexions/{id}/activer` pour le connecteur officiel après OAuth ou activation partenaire ;
- `POST /api/diffusion/connexions/{id}/autoriser-automatique` après une première publication validée et exécutée ;
- `POST /api/diffusion/connexions/{id}/desactiver-automatique` pour revenir à une validation à chaque annonce ;
- `POST /api/diffusion/connexions/{id}/revoquer` pour couper la connexion et l'autorisation automatique.

Les jobs d'annonce sont exposés avec :

- `POST /api/internal/diffusion/publications` pour créer un job idempotent rattaché à une mission `agent-diffusion` ;
- `GET /api/diffusion/publications` et `GET /api/diffusion/publications/{id}` pour le cockpit propriétaire.

La première publication est une action `publier_annonce` de l'Agent Diffusion. Elle doit être approuvée par le propriétaire avant l'exécution. Le canal interne marque alors `first_publication_validated_at` et conserve l'identifiant de l'action. Tant que ce champ est vide, l'autorisation automatique répond `409`. Une publication automatique ultérieure doit déclarer la connexion dans son payload et le mode automatique doit être actif.

Aucun mot de passe n'est stocké. La connexion reste propre au workspace, les références de compte sont hachées et les activations, autorisations, désactivations, révocations et transitions des jobs sont inscrites dans l'audit. Cette couche ne contourne aucun CAPTCHA, aucune règle de plateforme et ne crée pas encore de connecteur réel.

## Première tranche

1. Ajouter les tables `workspaces`, `properties`, `applications`, `agent_runs`, `actions` et `audit_events`.
2. Ajouter les routes de lecture propriétaire et les contrôles d’isolation.
3. Ajouter la file de validation sans exécution externe.
4. Relier le dashboard à des réponses persistées synthétiques.
5. Ajouter les connecteurs un par un, uniquement après documentation des permissions.

## Actions, validations et audit

Le centre d'actions constitue la frontière entre le travail des agents et les effets qui peuvent engager le propriétaire. Une mission d'agent est enregistrée dans `agent_runs`, puis l'agent peut produire une proposition persistée dans `actions`. Le contenu de la proposition est conservé sous forme JSON, avec une empreinte SHA-256 et une clé d'idempotence propre au workspace.

Les routes privées du worker sont protégées par `x-piaule-agent-token` et `PIAULE_AGENT_INTERNAL_TOKEN` :

- `POST /api/internal/agent-runs` crée une mission `queued` ;
- `PUT /api/internal/agent-runs/{id}` met à jour son statut, sa sortie et ses preuves ;
- `POST /api/internal/actions` crée une action ou renvoie la même action lorsqu'une clé d'idempotence est rejouée ;
- `POST /api/internal/actions/{id}/execute` marque l'action exécutée après autorisation, sans appeler de fournisseur externe.

Les routes du propriétaire sont :

- `GET /api/agent-runs` et `GET /api/agent-runs/{id}` ;
- `GET /api/actions` et `GET /api/actions/{id}` ;
- `POST /api/actions/{id}/approve` pour autoriser une action sensible ;
- `POST /api/actions/{id}/reject` pour la refuser avec un motif ;
- `GET /api/audit` pour relire les propositions, décisions, expirations et exécutions.

Les risques reconnus sont `lecture`, `brouillon`, `transmission`, `engagement_financier`, `decision` et `irreversible`. Les actions de transmission, de décision ou d'engagement restent `a_valider` jusqu'à l'autorisation explicite du propriétaire. Une tentative d'exécution avant validation est refusée. L'exécution est idempotente : une répétition ne crée pas de second effet enregistré.

Les événements d'audit sont append-only via l'API : création et mise à jour de mission, proposition d'action, autorisation, refus, expiration et exécution. Chaque événement conserve l'acteur, le workspace, l'entité concernée et des métadonnées limitées. Les nouvelles routes ne déclenchent aucun e-mail, SMS, paiement, publication ou rendez-vous externe ; ces connecteurs seront branchés ensuite derrière cette frontière.

Une seconde barrière contrôle le périmètre de l'agent. Une action liée à une mission est comparée à la politique du rôle. Si le rôle ne possède pas cette capacité, l'API répond `403`, ne crée pas d'action et ajoute `agent_action_bloquee` dans l'audit. Les contrats persistés donnent le vocabulaire métier ; la matrice d'actions reste un garde-fou technique et sera affinée avec les réponses aux questions de cadrage ci-dessous.

## Décisions de cadrage des contrats v1

Les contrats v1 suivent les décisions du produit :

1. L'Agent Complétude peut envoyer directement un e-mail au candidat depuis la boîte configurée, avec uniquement les pièces autorisées manquantes et un lien de dépôt valable trente jours.
2. L'Agent Diffusion attend une première validation et exécution du propriétaire. Les publications suivantes suivent le paramètre du compte : automatique si le propriétaire l'a autorisé, validation systématique sinon.
3. L'Agent Comparaison prépare une shortlist expliquée. Le propriétaire décide toujours de retenir ou refuser.
4. L'Agent Confiance peut préparer une vérification officielle, mais elle ne démarre qu'après le consentement du candidat et le retour d'un connecteur reconnu.
5. L'Agent Visites peut lire les créneaux internes et les périodes occupées synchronisées en lecture seule depuis Google ou Outlook. Il ne confirme pas une décision de location.
6. Le propriétaire garde la décision finale pour le refus, la sélection, la signature, le paiement, la suppression définitive et toute action réglementée.

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

Une candidature complète passe d’abord par une visite proposée puis confirmée par le candidat. Le propriétaire marque ensuite la visite comme réalisée avec `POST /api/biens/{id}/visites/{visit_id}/terminer`. Tant qu’aucune visite liée n’est `terminee`, l’API refuse le passage à `retenue`. Après cette étape, le backend crée une fiche durable dans `owner_tenants`, accessible avec `GET /api/locataires`, `GET /api/locataires/{tenant_id}` ou `GET /api/biens/{id}/locataires`. Cette fiche reprend uniquement les informations nécessaires au suivi du locataire et reste liée à la candidature source. Le lien temporaire candidat est alors révoqué : il n’y a pas de compte candidat permanent créé par ce parcours.

Lorsqu’une candidature passe à `refusee` ou `retiree`, le backend programme une purge selon `PIAULE_APPLICATION_REJECTED_RETENTION_DAYS` (90 jours par défaut). Le worker interne `POST /api/internal/candidatures/purger`, protégé par `x-piaule-agent-token`, supprime les documents bruts, pièces jointes et messages, puis anonymise les coordonnées de la candidature en conservant uniquement la trace nécessaire du pipeline et de l’audit. Une candidature déjà convertie en locataire n’est pas purgée par ce worker.

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

## États des lieux

Le cycle métier est volontairement séparé : dossier étudié, visite réalisée, candidature retenue, puis état des lieux d'entrée. Le backend prépare l'état des lieux sans confondre la visite avec la remise des clés.

Les routes de la première tranche sont :

- `POST/GET /api/biens/{id}/etats-des-lieux` ;
- `GET /api/biens/{id}/etats-des-lieux/{edl_id}` ;
- `POST .../{edl_id}/pieces` ;
- `POST .../{edl_id}/pieces/{piece_id}/elements` et `PUT .../{entry_id}` ;
- `POST .../{edl_id}/compteurs` et `POST .../{edl_id}/cles` ;
- `POST .../{edl_id}/photos` ;
- `POST .../{edl_id}/verifier` ;
- `POST .../{edl_id}/preparer-signature`.

Un état des lieux contient son type (`entree`, `sortie`, `intermediaire`), son bien, son lot éventuel, sa candidature et son locataire. Les pièces contiennent les éléments observés, chacun avec une catégorie, un état, une observation et éventuellement une quantité. Les compteurs, clés, photos et empreintes SHA-256 sont conservés séparément. Les photos restent privées et sont stockées hors de la base.

Le moteur de préparation signale les bloquants suivants : aucune pièce, pièce sans élément, élément `non_verifie` et absence de locataire pour un état des lieux d'entrée. Les compteurs, clés et photos manquants sont des avertissements explicites. La route `preparer-signature` ne peut passer à `pret_signature` qu'après résolution des bloquants. Elle ne réalise pas la signature électronique : le verrouillage et l'envoi aux signataires devront passer par un connecteur séparé avec validation humaine et audit.

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

Le moteur de pré-vérification est déterministe : il vérifie la présence du fichier, sa taille stockée, l'accord extension/MIME, sa signature PDF/JPG/PNG, sa date d'expiration, les doublons dans le dossier et une éventuelle incompatibilité probable entre le nom du fichier et la catégorie déclarée. Une anomalie bloque ou place la pièce `a_corriger`; un contrôle technique réussi la place `en_verification`, jamais `valide` automatiquement. Le moteur conserve chaque résultat et sa version. À chaque nouveau dépôt, l'Agent Confiance reçoit aussi une mission idempotente pour rejouer ces contrôles et préparer, selon la politique du bien, une demande de preuve officielle ou partenaire.

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

## Créneaux et visites

Le propriétaire peut créer des créneaux de visite indépendants d’un calendrier externe avec :

- `GET/POST /api/biens/{id}/visite-creneaux` pour consulter ou créer les disponibilités ;
- `GET /api/biens/{id}/visite-creneaux?statut=libre` pour filtrer les créneaux utilisables ;
- `GET /api/biens/{id}/visites` pour suivre les propositions et rendez-vous du bien ;
- `POST /api/biens/{id}/candidatures/{application_id}/visites/proposer` pour réserver un créneau à une candidature complète ;
- `POST /api/biens/{id}/visites/{visit_id}/annuler` pour libérer un créneau avec un motif.

Une proposition est créée avec le statut `proposee` et réserve immédiatement le créneau. Le backend refuse une candidature incomplète, un créneau déjà réservé, un chevauchement de disponibilités ou un créneau associé à un autre lot. La proposition ne déclenche encore aucun e-mail, SMS ou invitation de calendrier : ces transmissions seront des actions de connecteur séparées et journalisées.

Les calendriers externes sont préparés derrière un connecteur officiel :

- `GET/POST /api/calendriers/connexions` pour enregistrer un calendrier du workspace en statut `a_connecter` ;
- `POST /api/internal/calendriers/connexions/{id}/activer` après le handshake OAuth ou ICS, sans stocker le jeton dans cette API ;
- `POST /api/internal/calendriers/connexions/{id}/synchroniser` pour remplacer l'instantané des périodes occupées, normalisées en UTC ;
- `POST /api/calendriers/connexions/{id}/revoquer` pour arrêter leur prise en compte.

Une période d'un calendrier actif bloque la création et la proposition d'un créneau qui la chevauche. La connexion réelle à Google Calendar ou Microsoft Graph reste la prochaine étape du connecteur ; ces routes constituent la frontière de données et de permissions sur laquelle il pourra s'appuyer.

Depuis son lien temporaire, le candidat peut consulter et répondre à ses propres propositions avec :

- `GET /api/candidature-acces/{token}/visites` ;
- `POST /api/candidature-acces/{token}/visites/{visit_id}/reponse`.

Une acceptation passe la visite à `confirmee` et la candidature à `visite_confirmee`. Un refus libère le créneau et replace la candidature à `prete`. Les données d’un autre workspace ou d’une autre candidature ne sont jamais exposées par le lien candidat.

La fiche comprend maintenant les types de location, équipements, disponibilité, photos, visibilité de l’adresse, informations DPE, mode de détention et premiers champs de copropriété. Les routes `POST/GET/PUT /api/biens/{id}/suivis` permettent de suivre diagnostics, assurances, contrats fournisseurs et documents de copropriété avec leurs échéances. `GET /api/echeances` remonte les éléments expirés ou arrivant à échéance.

La comptabilité, la fiscalité, le financement, la rentabilité et les tableaux financiers ne font pas partie du produit. Les champs de loyer, charges et dépôt servent uniquement à configurer une mise en location et ses règles opérationnelles.
