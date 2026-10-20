# Backend Piaule Fiction

Cette API devient le socle du workspace propriétaire. Le slice historique compte/session/documents reste réutilisable, mais les prochaines routes doivent être rattachées à un workspace propriétaire et à son portefeuille de biens.

## Domaine cible

- `workspace` et membres autorisés ;
- `property` / `lot` et règles du bien ;
- `application` rattachée à un bien et à une source ;
- `document` avec statut, provenance et accès ;
- `agent_run`, `action`, `approval` et `audit_event` ;
- `workspace_agent` et `agent_message` pour l'équipe privée du propriétaire, avec un contrat versionné par agent ;
- `publication_connection` pour les comptes de diffusion et leurs autorisations ;
- `publication_job` pour chaque annonce préparée, validée, publiée ou échouée ;
- `visit` et disponibilités ;
- `inspection` / état des lieux avec pièces, éléments observés, compteurs, clés et médias privés ;
- `connector` avec permissions et révocation.

Le candidat reste un participant du dossier. Les données fictives utilisées par les tests ne doivent jamais être interprétées comme des décisions de solvabilité ou d’authenticité prises par l’IA.

Le domaine biens/lots couvre maintenant la structure du bien, les équipements, les photos, la disponibilité, les types de location, le DPE, les informations de copropriété et les suivis à échéance. Le pipeline de candidatures est rattaché aux biens et aux lots, avec source, statut, notes privées et détection de doublons. Chaque publication peut recevoir une adresse de candidature dédiée ; les e-mails entrants sont placés dans une inbox d’analyse avant association au bon dossier. Les pièces candidates acceptent les PDF/JPG/PNG jusqu’à 100 Mo par fichier. Le moteur de pré-vérification contrôle automatiquement l’intégrité technique, l’expiration, les doublons et les incohérences probables de classement, mais ne certifie jamais l’authenticité d’un document sans preuve officielle ou revue humaine. L’agent peut préparer une relance ciblée pour les pièces manquantes sans pouvoir refuser une candidature. Le cycle de candidature expose maintenant des transitions contrôlées et un historique avec motif, et bloque la proposition de visite tant que le dossier n’est pas complet. Une candidature ne peut être retenue qu’après une visite confirmée puis marquée `terminee` par le propriétaire via `POST /api/biens/{id}/visites/{visit_id}/terminer`. Une candidature retenue est ensuite convertie en fiche locataire durable via `GET /api/locataires` ou `GET /api/biens/{id}/locataires` ; son lien temporaire est révoqué. Une candidature refusée ou retirée reçoit une échéance de purge configurable (`PIAULE_APPLICATION_REJECTED_RETENTION_DAYS`, 90 jours par défaut), puis le worker `POST /api/internal/candidatures/purger` supprime les fichiers et anonymise la trace métier. La plateforme ne gère pas la comptabilité, la fiscalité, le financement ou les tableaux de rentabilité.

Le calendrier de visites expose des créneaux du propriétaire avec fuseau horaire, mode et statut. Une proposition de visite réserve le créneau uniquement pour une candidature complète ; le candidat peut l’accepter ou la refuser depuis son lien temporaire. Les e-mails, SMS et invitations de calendrier restent des actions de connecteur séparées.

## États des lieux

Après une visite effectivement terminée et la sélection de la candidature, le propriétaire peut préparer un état des lieux d'entrée. Le backend conserve un brouillon par bien, avec un éventuel lot, locataire et candidature retenue. Les informations opérationnelles sont séparées en pièces, éléments observés, relevés de compteurs, clés/télécommandes et photos privées. Les photos sont stockées hors de la base, avec empreinte SHA-256 et rattachement facultatif à une pièce ou à un élément.

Les routes sont :

- `POST/GET /api/biens/{id}/etats-des-lieux` pour créer et lister les états des lieux ;
- `GET /api/biens/{id}/etats-des-lieux/{edl_id}` pour charger le dossier complet ;
- `POST .../{edl_id}/pieces` pour ajouter une pièce ;
- `POST .../{edl_id}/pieces/{piece_id}/elements` et `PUT .../{entry_id}` pour décrire puis corriger les éléments observés ;
- `POST .../{edl_id}/compteurs` et `POST .../{edl_id}/cles` pour les relevés et la remise des clés ;
- `POST .../{edl_id}/photos` pour déposer une photo JPEG/PNG de 100 Mo maximum ;
- `POST .../{edl_id}/verifier` pour calculer les bloquants et avertissements ;
- `POST .../{edl_id}/preparer-signature` pour passer à `pret_signature` lorsque chaque pièce comporte au moins un élément vérifié et que le locataire est rattaché.

Le contrôle est explicable : il bloque une pièce sans élément, un élément encore `non_verifie` et, pour un état des lieux d'entrée, l'absence de locataire. Les compteurs, clés et photos sont signalés comme avertissements afin de laisser le propriétaire décider selon le logement. La signature électronique, le verrouillage juridique et l'envoi aux signataires restent une étape de connecteur séparée ; cette API ne prétend pas signer ni certifier le document.

La stratégie complète de confiance documentaire est décrite dans [`docs/DOCUMENT_VERIFICATION_AND_FRAUD.md`](../docs/DOCUMENT_VERIFICATION_AND_FRAUD.md). Elle sépare la complétude, les contrôles techniques, les comparaisons entre pièces, les preuves officielles et la revue humaine. La vérification fiscale doit s'appuyer sur le service officiel de vérification des avis ou le code 2D-Doc, sous réserve d'un parcours automatisé autorisé ; l'API Particulier est soumise à habilitation et n'est pas présumée accessible à Piaule Fiction. Chaque bien possède aussi une politique `standard`, `renforcee` ou `officielle`, configurable via `/api/biens/{id}/politique-verification`. Les demandes de preuve externe sont consenties par le candidat et reçoivent le résultat d'un futur connecteur via `/api/internal/verifications/{request_id}/result`.

## Lancer localement

```bash
python3 -m pip install -r backend/requirements.txt
PIAULE_STATE_DIRECTORY=.local-state uvicorn backend.main:app --reload --port 8000
```

Routes de socle actuellement conservées : `GET /health`, compte/session, profil, documents privés et source synthétique. Le premier bloc propriétaire est maintenant disponible : `GET /api/workspace`, `PUT /api/workspace`, `GET /api/workspace/membres`, les routes `/api/biens`, les routes `/api/biens/{id}/lots`, les routes `/api/biens/{id}/suivis`, `GET /api/echeances`, `GET /api/candidatures` et les routes `/api/biens/{id}/candidatures`. La réception est préparée avec les routes `/api/biens/{id}/canaux-candidatures`, `GET /api/candidatures/inbox`, le webhook interne `/api/internal/candidatures/inbound` et l’association `/api/candidatures/inbox/{message_id}/associer`. DossierFacile Connect est préparé avec la demande OAuth2 `/api/biens/{id}/candidatures/{application_id}/dossier-facile/connect`, le callback `/api/dossier-facile/callback`, le suivi et le webhook `/api/internal/dossier-facile/webhook`. Les pièces de candidature utilisent `GET/POST /api/biens/{id}/candidatures/{application_id}/pieces`, `PUT .../pieces/{document_id}/verification`, `GET .../completude` et `POST .../verifier`. Le parcours e-mail/candidat utilise `POST .../lien-candidat`, `GET/POST /api/candidature-acces/{token}`, `POST .../pieces`, ainsi que les messages `/api/biens/{id}/candidatures/{application_id}/messages`. L’agent peut demander les pièces manquantes avec `POST .../agent/relancer-completude`, sans pouvoir refuser une candidature. Les routes documents, validations et audit suivent le contrat décrit dans [`docs/API_OWNER_WORKSPACE_CONTRACT.md`](../docs/API_OWNER_WORKSPACE_CONTRACT.md).

La connexion Google utilise OpenID Connect avec les scopes `openid email profile`. Elle ne demande aucun accès Gmail. Les routes sont `GET /api/auth/google/start` et `GET /api/auth/google/callback`. Il faut créer un client OAuth Web dans Google Cloud et déclarer exactement la valeur de `PIAULE_GOOGLE_REDIRECT_URI`.

## Équipe d'agents du propriétaire

À la création d'un compte classique ou Google, le backend provisionne automatiquement une équipe privée dans le workspace du propriétaire. Le catalogue initial comprend l'Orchestrateur, Bien, Diffusion, Candidatures, Complétude, Confiance, Comparaison, Visites, Communication, Conformité et Suivi. Chaque instance reçoit un contrat versionné qui décrit ses entrées, sorties, actions et cas d'escalade. Ces instances ont des identifiants propres au workspace ; elles ne partagent ni messages, ni missions, ni données avec un autre propriétaire.

Le propriétaire peut afficher son équipe avec `GET /api/agents` et consulter le contrat d'un agent avec `GET /api/agents/{id}`. L'Orchestrateur est le point de contact principal : `POST /api/agents/orchestrateur/messages` enregistre une demande, crée une mission `queued` et ajoute un événement d'audit. `GET /api/agents/orchestrateur/messages` relit l'échange. Le worker interne `POST /api/internal/agent-runs/process-next` consomme une mission Orchestrateur, applique le routage déterministe des contrats et crée des sous-missions dans le même workspace. Les pièces reçues par portail ou par e-mail mettent automatiquement en file une mission Complétude et une mission Confiance, de manière idempotente. `POST /api/internal/agent-runs/process-next-completude` calcule les pièces manquantes et met en file un e-mail ciblé au candidat avec un lien valable trente jours ; le worker SMTP `POST /api/internal/candidatures/outbox/traiter` effectue ensuite l'envoi réel. `POST /api/internal/agent-runs/process-next-confiance` réanalyse les pièces et prépare les demandes de preuve externe adaptées à la politique du bien. Le fournisseur LLM et les connecteurs officiels restent à brancher derrière ces contrats.

## Diffusion des annonces

L'Agent Diffusion est provisionné dans l'équipe. Les comptes de publication sont enregistrés avec `POST /api/diffusion/connexions` et consultables avec `GET /api/diffusion/connexions`. Une connexion reste `a_connecter` jusqu'à ce qu'un connecteur officiel termine son OAuth ou son activation partenaire via `POST /api/internal/diffusion/connexions/{id}/activer`.

La première publication doit être proposée comme une action `publier_annonce`, validée par le propriétaire puis exécutée par le connecteur. L'exécution marque la première publication comme validée. Seulement après cette étape, le propriétaire peut appeler `POST /api/diffusion/connexions/{id}/autoriser-automatique`. Il peut revenir à une validation systématique avec `.../desactiver-automatique` ou révoquer complètement la connexion avec `.../revoquer`.

L'Agent Diffusion crée une mission de publication avec `POST /api/internal/diffusion/publications`. Le job est visible par le propriétaire avec `GET /api/diffusion/publications` et `GET /api/diffusion/publications/{id}`. Une première publication reste `a_valider` jusqu'à l'approbation puis l'exécution de son action. Une publication automatique ultérieure est possible uniquement si la connexion a été autorisée par le propriétaire après cette première exécution ; elle conserve la même frontière d'action et d'audit.

Le backend ne stocke pas de mot de passe et n'appelle encore aucune plateforme réelle. Les références de compte reçues par le canal interne sont conservées sous forme d'empreinte. Toute publication doit utiliser un connecteur autorisé, une action auditée et les permissions de la plateforme concernée.

Les visites utilisent actuellement les routes `/api/biens/{id}/visite-creneaux`, `/api/biens/{id}/visites` et `/api/biens/{id}/candidatures/{application_id}/visites/proposer`. Le portail candidat répond via `/api/candidature-acces/{token}/visites/{visit_id}/reponse`. Les connexions calendrier sont préparées en lecture seule avec `GET/POST /api/calendriers/connexions`, activation interne après le handshake officiel, `POST /api/internal/calendriers/connexions/{id}/synchroniser` pour recevoir un instantané normalisé des périodes occupées et `POST /api/calendriers/connexions/{id}/revoquer`. Les périodes actives bloquent la création et la proposition d'un créneau de visite. Les appels OAuth Google/Microsoft et les invitations externes ne sont pas encore implémentés : aucun jeton n'est stocké par ces routes.

La messagerie Hostinger se configure dans l’environnement du VPS, jamais dans Git : SMTP `smtp.hostinger.com` (SSL 465 ou STARTTLS 587) et IMAP `imap.hostinger.com` (SSL 993). Le worker sortant est `POST /api/internal/candidatures/outbox/traiter`, et le worker entrant est `POST /api/internal/candidatures/inbox/synchroniser`. Les deux exigent `x-piaule-email-token` et `PIAULE_EMAIL_INTERNAL_TOKEN`.

La récupération de compte utilise `POST /api/mot-de-passe-oublie` puis `POST /api/mot-de-passe-reinitialiser`. Le prénom peut servir de vérification complémentaire, mais le secret de récupération doit être transmis par e-mail et reste valable quinze minutes. L’envoi SMTP réel sera branché avant la production ; `PIAULE_EXPOSE_DEV_RESET_TOKEN` est réservé aux tests locaux.

Une récupération par SMS est prévue après ce socle. Elle devra utiliser un numéro vérifié, un fournisseur SMS, un code à usage unique expirant rapidement, des limites anti-abus et un audit. Elle ne remplace pas encore le parcours e-mail actuel.

La base `.local-state/` et les uploads privés ne doivent jamais être versionnés. Aucun connecteur réel, message, publication, signature ou paiement ne doit être activé avant d’avoir une permission explicite, une file de validation et un audit.

## Actions des agents, validations et audit

Le centre de contrôle est disponible sans frontend :

- le worker interne crée une mission avec `POST /api/internal/agent-runs` et la met à jour avec `PUT /api/internal/agent-runs/{id}` ;
- il propose une action immuable avec `POST /api/internal/actions` ;
- le propriétaire consulte la file avec `GET /api/actions`, puis utilise `POST /api/actions/{id}/approve` ou `POST /api/actions/{id}/reject` ;
- le worker ne peut marquer une action sensible exécutée qu'après autorisation avec `POST /api/internal/actions/{id}/execute` ;
- le parcours complet est disponible dans `GET /api/audit`.

Les routes privées exigent `x-piaule-agent-token` correspondant à `PIAULE_AGENT_INTERNAL_TOKEN`. La clé d'idempotence empêche une proposition rejouée de créer un doublon. La première exécution est un marqueur de test : aucun e-mail, SMS, paiement, calendrier ou publication externe n'est déclenché par ce centre.

Chaque action liée à une mission est aussi contrôlée par le rôle de l'agent. Une capacité absente de sa politique est refusée en `403` et produit un événement `agent_action_bloquee`. La liste actuelle des capacités et les contrats persistés servent de garde-fou de départ ; les questions de cadrage métier restantes sont listées dans [`docs/API_OWNER_WORKSPACE_CONTRACT.md`](../docs/API_OWNER_WORKSPACE_CONTRACT.md).
