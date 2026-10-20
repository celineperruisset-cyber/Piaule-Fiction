# Backend Piaule Fiction

Cette API devient le socle du workspace propriétaire. Le slice historique compte/session/documents reste réutilisable, mais les prochaines routes doivent être rattachées à un workspace propriétaire et à son portefeuille de biens.

## Domaine cible

- `workspace` et membres autorisés ;
- `property` / `lot` et règles du bien ;
- `application` rattachée à un bien et à une source ;
- `document` avec statut, provenance et accès ;
- `agent_run`, `action`, `approval` et `audit_event` ;
- `workspace_agent` et `agent_message` pour l'équipe privée du propriétaire ;
- `visit` et disponibilités ;
- `connector` avec permissions et révocation.

Le candidat reste un participant du dossier. Les données fictives utilisées par les tests ne doivent jamais être interprétées comme des décisions de solvabilité ou d’authenticité prises par l’IA.

Le domaine biens/lots couvre maintenant la structure du bien, les équipements, les photos, la disponibilité, les types de location, le DPE, les informations de copropriété et les suivis à échéance. Le pipeline de candidatures est rattaché aux biens et aux lots, avec source, statut, notes privées et détection de doublons. Chaque publication peut recevoir une adresse de candidature dédiée ; les e-mails entrants sont placés dans une inbox d’analyse avant association au bon dossier. Les pièces candidates acceptent les PDF/JPG/PNG jusqu’à 100 Mo par fichier. Le moteur de pré-vérification contrôle automatiquement l’intégrité technique, l’expiration, les doublons et les incohérences probables de classement, mais ne certifie jamais l’authenticité d’un document sans preuve officielle ou revue humaine. L’agent peut préparer une relance ciblée pour les pièces manquantes sans pouvoir refuser une candidature. Le cycle de candidature expose maintenant des transitions contrôlées et un historique avec motif, et bloque la proposition de visite tant que le dossier n’est pas complet. La plateforme ne gère pas la comptabilité, la fiscalité, le financement ou les tableaux de rentabilité.

Le calendrier de visites expose des créneaux du propriétaire avec fuseau horaire, mode et statut. Une proposition de visite réserve le créneau uniquement pour une candidature complète ; le candidat peut l’accepter ou la refuser depuis son lien temporaire. Les e-mails, SMS et invitations de calendrier restent des actions de connecteur séparées.

La stratégie complète de confiance documentaire est décrite dans [`docs/DOCUMENT_VERIFICATION_AND_FRAUD.md`](../docs/DOCUMENT_VERIFICATION_AND_FRAUD.md). Elle sépare la complétude, les contrôles techniques, les comparaisons entre pièces, les preuves officielles et la revue humaine. La vérification fiscale doit s'appuyer sur le service officiel de vérification des avis ou le code 2D-Doc, sous réserve d'un parcours automatisé autorisé ; l'API Particulier est soumise à habilitation et n'est pas présumée accessible à Piaule Fiction. Chaque bien possède aussi une politique `standard`, `renforcee` ou `officielle`, configurable via `/api/biens/{id}/politique-verification`. Les demandes de preuve externe sont consenties par le candidat et reçoivent le résultat d'un futur connecteur via `/api/internal/verifications/{request_id}/result`.

## Lancer localement

```bash
python3 -m pip install -r backend/requirements.txt
PIAULE_STATE_DIRECTORY=.local-state uvicorn backend.main:app --reload --port 8000
```

Routes de socle actuellement conservées : `GET /health`, compte/session, profil, documents privés et source synthétique. Le premier bloc propriétaire est maintenant disponible : `GET /api/workspace`, `PUT /api/workspace`, `GET /api/workspace/membres`, les routes `/api/biens`, les routes `/api/biens/{id}/lots`, les routes `/api/biens/{id}/suivis`, `GET /api/echeances`, `GET /api/candidatures` et les routes `/api/biens/{id}/candidatures`. La réception est préparée avec les routes `/api/biens/{id}/canaux-candidatures`, `GET /api/candidatures/inbox`, le webhook interne `/api/internal/candidatures/inbound` et l’association `/api/candidatures/inbox/{message_id}/associer`. DossierFacile Connect est préparé avec la demande OAuth2 `/api/biens/{id}/candidatures/{application_id}/dossier-facile/connect`, le callback `/api/dossier-facile/callback`, le suivi et le webhook `/api/internal/dossier-facile/webhook`. Les pièces de candidature utilisent `GET/POST /api/biens/{id}/candidatures/{application_id}/pieces`, `PUT .../pieces/{document_id}/verification`, `GET .../completude` et `POST .../verifier`. Le parcours e-mail/candidat utilise `POST .../lien-candidat`, `GET/POST /api/candidature-acces/{token}`, `POST .../pieces`, ainsi que les messages `/api/biens/{id}/candidatures/{application_id}/messages`. L’agent peut demander les pièces manquantes avec `POST .../agent/relancer-completude`, sans pouvoir refuser une candidature. Les routes documents, validations et audit suivent le contrat décrit dans [`docs/API_OWNER_WORKSPACE_CONTRACT.md`](../docs/API_OWNER_WORKSPACE_CONTRACT.md).

La connexion Google utilise OpenID Connect avec les scopes `openid email profile`. Elle ne demande aucun accès Gmail. Les routes sont `GET /api/auth/google/start` et `GET /api/auth/google/callback`. Il faut créer un client OAuth Web dans Google Cloud et déclarer exactement la valeur de `PIAULE_GOOGLE_REDIRECT_URI`.

## Équipe d'agents du propriétaire

À la création d'un compte classique ou Google, le backend provisionne automatiquement une équipe privée dans le workspace du propriétaire. Le catalogue initial comprend l'Orchestrateur, Bien, Candidatures, Complétude, Confiance, Comparaison, Visites, Communication, Conformité et Suivi. Ces instances ont des identifiants propres au workspace ; elles ne partagent ni messages, ni missions, ni données avec un autre propriétaire.

Le propriétaire peut afficher son équipe avec `GET /api/agents`. L'Orchestrateur est le point de contact principal : `POST /api/agents/orchestrateur/messages` enregistre une demande, crée une mission `queued` et ajoute un événement d'audit. `GET /api/agents/orchestrateur/messages` relit l'échange. Le worker devra ensuite prendre la mission, produire une réponse et mettre à jour le message ; ce branchement n'est pas simulé par l'API.

Les visites utilisent actuellement les routes `/api/biens/{id}/visite-creneaux`, `/api/biens/{id}/visites` et `/api/biens/{id}/candidatures/{application_id}/visites/proposer`. Le portail candidat répond via `/api/candidature-acces/{token}/visites/{visit_id}/reponse`. Aucun calendrier externe n’est appelé par ces routes.

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

Chaque action liée à une mission est aussi contrôlée par le rôle de l'agent. Une capacité absente de sa politique est refusée en `403` et produit un événement `agent_action_bloquee`. La liste actuelle des capacités sert de garde-fou de départ ; les contrats détaillés des agents seront définis ensuite.
