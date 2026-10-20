const R = {
  fastapi: { label: "FastAPI", url: "https://fastapi.tiangolo.com/" },
  stripe: { label: "Stripe Billing", url: "https://docs.stripe.com/billing" },
  cnilAuto: { label: "CNIL — décisions automatisées", url: "https://www.cnil.fr/fr/profilage-et-decision-entierement-automatisee" },
  cnilDocs: { label: "CNIL — justificatifs de location", url: "https://www.cnil.fr/fr/location-dun-bien-immobilier-quels-justificatifs" },
  dossierDocs: { label: "Service Public — justificatifs", url: "https://www.service-public.fr/particuliers/vosdroits/F1169" },
  gdpr: { label: "RGPD — Commission européenne", url: "https://commission.europa.eu/law/law-topic/data-protection/data-protection-eu_en" },
  legifrance: { label: "Légifrance — loi Hoguet", url: "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006902223" },
  cci: { label: "CCI — carte professionnelle", url: "https://www.cci.fr/offre/obtenir-carte-agent-immobilier" },
  playwright: { label: "Playwright", url: "https://playwright.dev/docs/intro" },
  githubActions: { label: "GitHub Actions", url: "https://docs.github.com/en/actions/quickstart" },
  caddy: { label: "Caddy HTTPS", url: "https://caddyserver.com/docs/" },
  franceIdentite: { label: "France Identité — espace pro", url: "https://france-identite.gouv.fr/espace-pro/" },
  dgfipVerif: { label: "DGFiP — Vérif Avis", url: "https://www.impots.gouv.fr/precisions-sur-le-service-de-verification-en-ligne" },
  apiParticulier: { label: "API Particulier — habilitation", url: "https://particulier.api.gouv.fr/faq" },
  youtube: { label: "YouTube — gestion locative", url: "https://www.youtube.com/results?search_query=gestion+locative+proprietaire+logiciel" }
};

const task = (id, title, type, priority, minutes, purpose, steps, doneWhen, resources = []) => ({
  id, title, type, priority, minutes, purpose, steps, doneWhen, resources
});

const initialTaskStatuses = {
  "owner-ui": "doing",
  "owner-domain": "done",
  "demo-data": "todo",
  "owner-api": "doing",
  "property-1": "done",
  "candidate-1": "done",
  "document-1": "done",
  "agent-1": "todo",
  "validation-1": "done",
  "visit-1": "done",
  "source-1": "doing",
  "launch-1": "todo"
};

const initialObjectiveStatuses = {
  "objective-brand": "doing",
  "objective-owner-account": "done",
  "objective-property": "done",
  "objective-applications": "done",
  "objective-document-vault": "doing",
  "objective-completeness": "done",
  "objective-comparison": "todo",
  "objective-agents": "doing",
  "objective-validation": "doing",
  "objective-visits": "doing",
  "objective-connectors": "todo",
  "objective-audit": "doing",
  "objective-regulatory": "doing",
  "objective-partners": "todo",
  "objective-payments": "todo",
  "objective-launch": "todo",
  "objective-scale": "todo"
};

const productPhases = [
  { id: "phase-brand", number: 1, title: "Marque et promesse propriétaire", purpose: "Faire comprendre que Piaule Fiction est une équipe logicielle pour gérer les tâches locatives.", doneWhen: "Un propriétaire comprend le bénéfice, le rôle des agents et la limite de responsabilité." },
  { id: "phase-workspace", number: 2, title: "Workspace propriétaire", purpose: "Réunir biens, candidatures, documents, actions et visites dans un seul espace.", doneWhen: "Un propriétaire peut suivre un bien et ses prochaines actions depuis un tableau lisible." },
  { id: "phase-dossiers", number: 3, title: "Dossiers et confiance", purpose: "Lire les candidatures, demander les pièces manquantes et expliquer les incohérences.", doneWhen: "Chaque dossier affiche sa complétude, ses preuves, ses inconnues et sa prochaine action." },
  { id: "phase-agents", number: 4, title: "Équipe d'agents IA", purpose: "Distribuer le travail entre des agents spécialisés avec des permissions limitées.", doneWhen: "Chaque agent possède un contrat, un journal et une règle d'escalade." },
  { id: "phase-connectors", number: 5, title: "Connecteurs et validations", purpose: "Relier les canaux officiellement accessibles sans transformer le logiciel en opérateur caché.", doneWhen: "Chaque connecteur déclare ses droits et chaque action sensible passe par une validation." },
  { id: "phase-production", number: 6, title: "Confiance, conformité et échelle", purpose: "Préparer la mise en production, les partenaires habilités et la croissance.", doneWhen: "Le produit est testable, sauvegardé, auditable et son rôle juridique est explicite." }
];

const projectStreams = [
  { id: "stream-brand", title: "Marque et interface propriétaire", label: "Donner envie de déléguer la gestion", status: "doing", color: "lime", now: "Le site Piaule Fiction existe ; son centre de gravité doit devenir l'espace propriétaire.", next: "Construire le tableau de bord biens → candidatures → validations → visites.", proof: "Un propriétaire comprend en moins d'une minute ce que ses agents font pour lui." },
  { id: "stream-workspace", title: "Workspace de gestion", label: "Une vue claire pour chaque bien", status: "doing", color: "blue", now: "La nouvelle architecture fonctionnelle est définie dans la documentation.", next: "Remplacer la prévisualisation candidat par une prévisualisation propriétaire interactive.", proof: "Un propriétaire peut passer d'un bien à ses dossiers et ses prochaines actions." },
  { id: "stream-dossiers", title: "Dossiers candidats", label: "Lire sans perdre le contexte", status: "doing", color: "teal", now: "Les candidatures, pièces, complétude et demandes ciblées sont persistées ; chaque pièce reçue relance automatiquement Complétude et Confiance.", next: "Relier le coffre, les demandes de consentement et les contrôles au frontend propriétaire.", proof: "Une pièce reçue est rattachée au bon dossier et son état est explicable." },
  { id: "stream-agents", title: "Agents de gestion", label: "Une équipe, pas un chatbot", status: "doing", color: "orange", now: "Le catalogue de 11 rôles est provisionné dans chaque workspace et le worker Complétude peut demander directement les pièces manquantes au candidat.", next: "Brancher les workers Confiance, Comparaison et Visites derrière le routage déterministe, puis le fournisseur LLM.", proof: "Chaque propriétaire voit sa propre équipe, ses contrats, ses autorisations de diffusion et peut lui transmettre une demande auditée." },
  { id: "stream-backend", title: "Backend workspace", label: "Une mémoire fiable des biens", status: "doing", color: "pink", now: "Le backend persiste le workspace, l’équipe d’agents, les messages Orchestrateur, les biens, lots, candidatures, pièces, vérifications, visites, calendriers, actions et audit.", next: "Relier le cockpit propriétaire aux missions, à la file de complétude et aux connexions calendrier.", proof: "Le frontend et les agents lisent la même source de vérité par propriétaire." },
  { id: "stream-connectors", title: "Connecteurs autorisés", label: "Brancher les bons canaux", status: "doing", color: "purple", now: "Le backend distingue la connexion d’un compte, le job d’annonce, la première publication validée et l’autorisation automatique.", next: "Documenter API, flux, permissions, coût et droits de publication avant chaque adaptateur.", proof: "Aucun connecteur n'utilise un compte tiers ou un accès non autorisé, et chaque annonce garde son statut et sa preuve." },
  { id: "stream-boundary", title: "Cadre et partenaires", label: "Rester un logiciel clair", status: "doing", color: "red", now: "La limite logiciel / activité immobilière est documentée.", next: "Faire valider le mode propriétaire et préparer un mode partenaire pour les actes réglementés.", proof: "Chaque écran affiche qui décide, qui envoie et qui porte l'action." },
  { id: "stream-production", title: "Déploiement et exploitation", label: "Un service fiable dans le temps", status: "todo", color: "green", now: "Le VPS existe et servira à la première version de test.", next: "Configurer HTTPS, sauvegardes, surveillance, restauration et séparation des environnements.", proof: "Une mise à jour peut être déployée et restaurée sans perdre les dossiers." }
];

const productObjectives = [
  { id: "objective-brand", phase: "phase-brand", title: "Repositionner la promesse", audience: "Produit", purpose: "Présenter Piaule Fiction comme une équipe IA qui aide les propriétaires à gérer sans devenir une agence cachée.", capabilities: ["Promesse claire", "Démonstration", "Rôle des agents", "Limites visibles", "Mobile"], doneWhen: "La page explique le bénéfice et le rôle juridique du propriétaire." },
  { id: "objective-owner-account", phase: "phase-workspace", title: "Créer l'espace propriétaire", audience: "Propriétaire", purpose: "Donner un compte, des permissions et une vue de portefeuille.", capabilities: ["Connexion", "Profil propriétaire", "Permissions", "Notifications", "Sécurité"], doneWhen: "Un propriétaire dispose d'un espace isolé et comprend ses autorisations." },
  { id: "objective-property", phase: "phase-workspace", title: "Gérer les biens et lots", audience: "Portefeuille", purpose: "Faire du bien la première unité de travail des agents.", capabilities: ["Bien", "Lots", "Caractéristiques", "Règles", "Documents"], doneWhen: "Un bien peut être créé, modifié et suivi sans données fictives mélangées." },
  { id: "objective-applications", phase: "phase-dossiers", title: "Centraliser les candidatures", audience: "Dossiers", purpose: "Réunir les réponses de plusieurs canaux autour d'un bien.", capabilities: ["Candidature", "Source", "Statuts", "Doublons", "Historique"], doneWhen: "Une candidature est rattachée à un bien et possède un état explicable." },
  { id: "objective-document-vault", phase: "phase-dossiers", title: "Construire le coffre documentaire", audience: "Confidentialité", purpose: "Conserver les pièces avec versions, accès ciblés et suppression.", capabilities: ["Pièces", "Versions", "Empreintes", "Accès temporaires", "Suppression"], doneWhen: "Une pièce est lisible seulement par les rôles autorisés et son accès est auditable." },
  { id: "objective-completeness", phase: "phase-dossiers", title: "Boucler la complétude", audience: "Agent Complétude", purpose: "Demander directement au candidat la seule pièce autorisée qui manque.", capabilities: ["Liste attendue", "Pièce manquante", "E-mail direct", "Rattachement", "Relecture"], doneWhen: "Une nouvelle pièce relance le bon dossier sans intervention inutile du propriétaire." },
  { id: "objective-comparison", phase: "phase-dossiers", title: "Comparer sans score opaque", audience: "Décision propriétaire", purpose: "Présenter les éléments du dossier sans automatiser une décision discriminatoire.", capabilities: ["Critères visibles", "Preuves", "Inconnues", "Comparaison", "Correction"], doneWhen: "Le propriétaire voit pourquoi un dossier est proposé et ce qui reste à vérifier." },
  { id: "objective-agents", phase: "phase-agents", title: "Donner un rôle à chaque agent", audience: "Orchestration", purpose: "Faire travailler une équipe spécialisée plutôt qu'un chatbot généraliste.", capabilities: ["Contrats", "Permissions", "Mémoire", "Journal", "Escalade"], doneWhen: "Chaque agent possède une entrée, une sortie et une limite testables." },
  { id: "objective-validation", phase: "phase-connectors", title: "Créer la file de validations", audience: "Contrôle humain", purpose: "Rendre rapides les décisions et transmissions qui engagent le propriétaire.", capabilities: ["Aperçu", "Destinataire", "Données", "Autoriser", "Refuser"], doneWhen: "Aucune action externe sensible ne part sans l'acteur autorisé." },
  { id: "objective-visits", phase: "phase-connectors", title: "Organiser les visites", audience: "Rendez-vous", purpose: "Lire les disponibilités du propriétaire et préparer les créneaux.", capabilities: ["Google", "Outlook", "Disponibilités", "Proposition", "Rappels"], doneWhen: "Un créneau est proposé puis confirmé avec un historique complet." },
  { id: "objective-connectors", phase: "phase-connectors", title: "Brancher les canaux autorisés", audience: "Intégrations", purpose: "Ajouter des sources sans scraping ni accès non documenté.", capabilities: ["API", "Flux", "Webhooks", "Export", "Révocation"], doneWhen: "Chaque source possède une fiche de capacités et une autorisation vérifiable." },
  { id: "objective-audit", phase: "phase-production", title: "Journaliser et supprimer", audience: "Confiance", purpose: "Savoir qui a proposé, validé, envoyé ou supprimé chaque élément.", capabilities: ["Audit", "Preuves", "Export", "Suppression", "Rétention"], doneWhen: "Le propriétaire peut relire le parcours et supprimer les données prévues." },
  { id: "objective-regulatory", phase: "phase-production", title: "Tenir la frontière réglementaire", audience: "Cadre français", purpose: "Empêcher le produit de se présenter comme une agence sans montage adapté.", capabilities: ["Acteur juridique", "Mandat", "Carte T/G", "RCP", "Blocages"], doneWhen: "Les actes réglementés sont bloqués ou portés par le propriétaire ou le partenaire habilité." },
  { id: "objective-partners", phase: "phase-production", title: "Préparer le mode partenaire", audience: "Agences et administrateurs", purpose: "Permettre aux professionnels habilités d'utiliser les agents comme équipe logicielle.", capabilities: ["Compte agence", "Droits", "Mandats", "Connecteurs", "Responsable"], doneWhen: "Un partenaire peut assumer ses actes et voir les actions réalisées pour son compte." },
  { id: "objective-payments", phase: "phase-production", title: "Préparer les abonnements", audience: "Modèle économique", purpose: "Vendre le logiciel sans monétiser les pièces ou les décisions.", capabilities: ["Plans", "Quotas", "Stripe test", "Factures", "Annulation"], doneWhen: "Le paiement est testable sans carte réelle et sans conditionner la sécurité." },
  { id: "objective-launch", phase: "phase-production", title: "Déployer le pilote", audience: "Exploitation", purpose: "Ouvrir une version de test avec données synthétiques et retour contrôlé.", capabilities: ["VPS", "HTTPS", "Sauvegardes", "Monitoring", "Retour arrière"], doneWhen: "Un pilote peut être lancé, surveillé et restauré proprement." },
  { id: "objective-scale", phase: "phase-production", title: "Préparer la montée en charge", audience: "Architecture", purpose: "Séparer web, API, tâches et stockage quand le portefeuille grandit.", capabilities: ["File", "Workers", "Base", "Stockage", "Coûts"], doneWhen: "L'architecture décrit le passage du VPS à des services séparés." }
];

const initialPersonalObjectiveStatuses = {
  "personal-brief": "doing", "personal-owner-ui": "doing", "personal-domain": "done", "personal-property": "done", "personal-dossiers": "done", "personal-agents": "todo", "personal-validation": "doing", "personal-connectors": "doing", "personal-backend": "doing", "personal-legal": "doing", "personal-launch": "todo"
};

const personalObjectives = [
  { id: "personal-brief", order: 1, stage: "Direction", title: "Fixer la promesse propriétaire", why: "Toute l'interface doit parler du temps rendu au propriétaire.", steps: ["Remplacer les textes candidat-first.", "Décrire les agents et leurs limites.", "Conserver le candidat comme partie du dossier."], doneWhen: "Le produit se comprend comme un logiciel de gestion assistée." },
  { id: "personal-owner-ui", order: 2, stage: "Frontend", title: "Construire le workspace propriétaire", why: "Le propriétaire doit voir son portefeuille, ses dossiers et les actions à valider.", steps: ["Créer la vue portefeuille.", "Créer la file d'actions.", "Créer la vue d'un bien et son pipeline candidat.", "Prévoir les états vide, chargement, blocage et succès."], doneWhen: "La prévisualisation est parcourable avec des données synthétiques." },
  { id: "personal-domain", order: 3, stage: "Architecture", title: "Définir le modèle de domaine", why: "Les agents ont besoin d'objets stables et rattachés au bon propriétaire.", steps: ["Propriétaire, bien, lot et règle.", "Candidat, candidature et pièce.", "Action, validation, preuve et événement."], doneWhen: "Chaque objet et son propriétaire sont documentés." },
  { id: "personal-property", order: 4, stage: "MVP · Biens", title: "Brancher le premier bien", why: "Le bien devient le point d'entrée du travail des agents.", steps: ["Créer les tables et routes.", "Enregistrer caractéristiques et règles.", "Afficher l'activité du bien."], doneWhen: "Un bien synthétique remonte dans le dashboard propriétaire." },
  { id: "personal-dossiers", order: 5, stage: "MVP · Dossiers", title: "Boucler la complétude", why: "La valeur immédiate est de résoudre les dossiers incomplets.", steps: ["Rattacher les pièces au candidat et au bien.", "Calculer les manquants autorisés.", "Préparer une demande.", "Relancer automatiquement Complétude et Confiance à réception."], doneWhen: "Une pièce reçue met à jour le bon dossier, déclenche les contrôles et peut générer la demande suivante." },
  { id: "personal-agents", order: 6, stage: "MVP · Agents", title: "Écrire les contrats des agents", why: "Chaque agent doit avoir une mission et une limite lisibles.", steps: ["Persister les entrées et sorties.", "Séparer faits et recommandations.", "Contrôler les actions par rôle.", "Faire tourner Complétude et préparer les workers Visites, Confiance et Comparaison."], doneWhen: "Les contrats sont persistés, le routage et le worker de complétude sont testés, et les autres workers peuvent être ajoutés sans changer le périmètre." },
  { id: "personal-validation", order: 7, stage: "MVP · Actions", title: "Construire la file de validation", why: "Le propriétaire doit contrôler rapidement les transmissions sensibles.", steps: ["Afficher destinataire et données.", "Prévisualiser le message.", "Autoriser, refuser ou demander une modification.", "Journaliser la décision."], doneWhen: "Le backend bloque une action sensible jusqu'à l'autorisation et conserve la décision ; il reste à brancher l'écran." },
  { id: "personal-connectors", order: 8, stage: "Connecteurs", title: "Étudier les canaux de publication", why: "Les intégrations doivent être officielles et adaptées au rôle du produit.", steps: ["Créer un job de publication idempotent.", "Relever API, flux et webhooks.", "Vérifier droits de publication et contrat.", "Documenter coûts, limites et révocation."], doneWhen: "Chaque annonce suit un cycle audité et chaque connecteur possède une fiche de décision." },
  { id: "personal-backend", order: 9, stage: "Backend", title: "Faire évoluer l'API vers le workspace", why: "Le backend actuel est une base technique, mais le modèle principal doit devenir propriétaire-first.", steps: ["Ajouter propriétaire et biens.", "Ajouter candidatures, actions et validations.", "Conserver l'isolation et le stockage privé."], doneWhen: "Le premier écran propriétaire lit des données persistées." },
  { id: "personal-legal", order: 10, stage: "Cadre", title: "Faire relire la frontière", why: "Le produit doit rester un éditeur logiciel ou travailler avec un partenaire habilité.", steps: ["Lister les fonctions d'assistance.", "Isoler les actes d'entremise et de gestion.", "Demander une validation CCI ou juridique avant commercialisation."], doneWhen: "Le mode de lancement et le rôle de chaque acteur sont écrits." },
  { id: "personal-launch", order: 11, stage: "Production", title: "Lancer un pilote propriétaire", why: "Il faut tester l'usage réel du dashboard avant d'ajouter toute la gestion locative.", steps: ["Configurer HTTPS et sauvegardes.", "Tester les comptes et permissions.", "Inviter quelques propriétaires avec données maîtrisées.", "Mesurer les actions résolues par les agents."], doneWhen: "Le pilote a un plan de surveillance et de retour arrière." }
];

const calendarRoadmap = [
  { id: "roadmap-1", stage: "Accueil", title: "Promesse propriétaire", description: "Montrer le temps rendu et la présence des agents.", status: "doing", proof: "Un propriétaire comprend le produit sans explication orale." },
  { id: "roadmap-2", stage: "Workspace", title: "Portefeuille de biens", description: "Voir chaque bien, son statut et ses prochaines actions.", status: "doing", proof: "Un bien synthétique s'ouvre sur son activité." },
  { id: "roadmap-3", stage: "Candidatures", title: "Pipeline des dossiers", description: "Recevoir, classer et suivre les candidatures.", status: "done", proof: "Chaque dossier possède un statut et une prochaine action." },
  { id: "roadmap-4", stage: "Dossier", title: "Complétude en boucle", description: "Demander directement au candidat la pièce autorisée manquante.", status: "done", proof: "La réception relance automatiquement la relecture." },
  { id: "roadmap-5", stage: "Agents", title: "Comparaison expliquée", description: "Présenter les faits, preuves, inconnues et alertes.", status: "todo", proof: "Le propriétaire comprend la proposition sans score opaque." },
  { id: "roadmap-6", stage: "Validation", title: "Actions contrôlées", description: "Préparer messages, publications et transmissions selon les paramètres du propriétaire.", status: "doing", proof: "Une action sensible suit le mode choisi : envoi automatique autorisé ou validation obligatoire." },
  { id: "roadmap-7", stage: "Visite", title: "Créneaux compatibles", description: "Proposer, confirmer et historiser les rendez-vous.", status: "doing", proof: "Aucune visite ne crée une acceptation implicite." },
  { id: "roadmap-8", stage: "Production", title: "Partenaires et exploitation", description: "Préparer API, partenaires habilités, sauvegardes et supervision.", status: "todo", proof: "Le rôle juridique et le plan de retour arrière sont explicites." }
];

const ownerProcesses = [
  ["Créer un bien", "L'agent transforme les informations du propriétaire en fiche structurée et relève les champs manquants.", ["agent", "rule", "human"], "MVP"],
  ["Préparer une annonce", "Le texte, les photos et les obligations visibles sont préparés en brouillon.", ["agent", "rule", "human"], "MVP"],
  ["Recevoir une candidature", "Le dossier est rattaché au bon bien, dédoublonné et enregistré avec sa provenance.", ["agent", "rule"], "MVP"],
  ["Contrôler la complétude", "Les pièces reçues, manquantes, illisibles ou incohérentes sont séparées.", ["agent", "rule"], "MVP"],
  ["Demander une pièce", "Une demande ciblée est préparée et envoyée selon les permissions configurées.", ["agent", "human"], "MVP"],
  ["Comparer les dossiers", "Les critères liés au bien sont expliqués avec leurs preuves et leurs limites.", ["agent", "rule", "human"], "MVP"],
  ["Préparer une visite", "Les créneaux compatibles sont proposés sans présenter la visite comme une acceptation.", ["agent", "rule", "human"], "MVP"],
  ["Gérer après le bail", "Loyers, impayés, travaux et actes de gestion sont réservés au périmètre validé ou au partenaire habilité.", ["rule", "human"], "Après validation"]
];
const candidateProcesses = ownerProcesses;

const skillMap = [
  { days: "01 · Produit", name: "Workspace propriétaire", proof: ["Portefeuille lisible", "Pipeline par bien", "Actions prioritaires"], target: 30 },
  { days: "02 · Domaine", name: "Bien et candidature", proof: ["Objets rattachés", "Statuts", "Historique"], target: 10 },
  { days: "03 · Dossier", name: "Complétude et cohérence", proof: ["Pièces isolées", "Demande ciblée", "Relecture"], target: 10 },
  { days: "04 · Agents", name: "Équipe spécialisée", proof: ["Contrats", "Permissions", "Escalade"], target: 10 },
  { days: "05 · Validation", name: "Actions contrôlées", proof: ["Aperçu", "Autorisation", "Audit"], target: 5 },
  { days: "06 · Connecteurs", name: "Canaux officiels", proof: ["API", "Droits", "Révocation"], target: 5 },
  { days: "07 · Production", name: "Fiabilité et coûts", proof: ["HTTPS", "Sauvegardes", "Quotas"], target: 5 }
];

const frenchRules = [
  { id: "PF-SCOPE-001", kind: "Périmètre", verified: "19/10/2026", title: "Le logiciel ne se présente pas comme une agence", statement: "Le propriétaire ou le partenaire habilité reste l'acteur des actes réglementés.", enforcement: "Chaque action affiche l'acteur juridique et les actes hors périmètre sont bloqués.", test: "Une tentative de conclure un bail au nom de Piaule Fiction crée une validation bloquante.", sources: [R.legifrance, R.cci] },
  { id: "PF-DOC-001", kind: "Protection", verified: "19/10/2026", title: "Une pièce demandée doit être autorisée", statement: "L'agent ne demande qu'une pièce nécessaire, expliquée et rattachée au bon dossier.", enforcement: "La plateforme affiche catégorie, motif, destinataire et durée d'accès.", test: "Une pièce interdite ou disproportionnée est refusée avant transmission.", sources: [R.cnilDocs, R.dossierDocs] },
  { id: "PF-AI-001", kind: "Garde-fou", verified: "19/10/2026", title: "L'IA propose, elle ne choisit pas seule", statement: "Une recommandation doit être accompagnée de preuves, limites et possibilités de correction.", enforcement: "Les sorties séparent faits, hypothèses et action proposée.", test: "Un dossier incertain est envoyé en revue plutôt que déclaré fiable.", sources: [R.cnilAuto] },
  { id: "PF-DATA-001", kind: "Confidentialité", verified: "19/10/2026", title: "Les dossiers restent isolés", statement: "Les documents et informations d'un candidat ne sont accessibles qu'aux rôles autorisés.", enforcement: "Chaque lecture, partage, révocation et suppression est journalisé.", test: "Un propriétaire ne peut jamais lire le dossier d'un autre compte.", sources: [R.gdpr] },
  { id: "PF-CONNECTOR-001", kind: "Intégration", verified: "19/10/2026", title: "Un connecteur doit être autorisé", statement: "Aucune source n'est branchée par scraping, contournement ou identifiant de tiers.", enforcement: "Chaque adaptateur possède un contrat de capacités et une preuve d'accès.", test: "Une source sans droit de publication reste en mode préparation ou lecture.", sources: [R.legifrance] }
];

const resourceLibrary = [
  ["Cadre", "Loi Hoguet", "Définir la frontière entre logiciel, transaction et gestion.", R.legifrance],
  ["Cadre", "CCI — carte professionnelle", "Faire relire le montage avant les fonctions d'agence.", R.cci],
  ["Données", "CNIL — justificatifs", "Limiter les pièces demandées et les accès.", R.cnilDocs],
  ["Droits", "CNIL — décisions automatisées", "Préserver l'explicabilité et l'intervention humaine.", R.cnilAuto],
  ["Backend", "FastAPI", "Construire les contrats du workspace propriétaire.", R.fastapi],
  ["Paiement", "Stripe Billing", "Tester les abonnements sans données documentaires monétisées.", R.stripe],
  ["Qualité", "Playwright", "Tester permissions, validations et parcours mobile.", R.playwright],
  ["Déploiement", "Caddy", "Servir l'application en HTTPS sur le VPS.", R.caddy],
  ["Identité", "France Identité — espace pro", "Préparer une future attestation ou authentification officielle après prise de contact partenaire.", R.franceIdentite],
  ["Fiscalité", "DGFiP — Vérif Avis", "Vérifier un avis d'impôt via le parcours officiel avec le consentement du candidat.", R.dgfipVerif],
  ["Fiscalité", "API Particulier", "Comprendre les conditions d'habilitation avant de demander une API restreinte.", R.apiParticulier],
  ["Veille", "Gestion locative", "Observer les outils utilisés par les propriétaires et agences.", R.youtube],
  ["RGPD", "Commission européenne", "Revoir droits, sous-traitance et suppression.", R.gdpr]
];

const sprintDays = [
  { id: "day-1", number: 1, date: "Semaine 1", shortDate: "Vision", title: "Recentrer Piaule Fiction", outcome: "Faire de Piaule Fiction un logiciel propriétaire-first.", deliverable: "Dashboard et documentation de la nouvelle direction.", tasks: [
    task("owner-ui", "Refaire le dashboard propriétaire", "build", "core", 180, "Rendre visible le portefeuille, les agents et la file de validation.", ["Remplacer les textes candidat.", "Afficher les biens et candidatures.", "Créer les états bloqué, à valider et terminé.", "Tester sur mobile."], "Le dashboard raconte le travail du propriétaire.")
  ]},
  { id: "day-2", number: 2, date: "Semaine 1", shortDate: "Domaine", title: "Définir les objets du métier", outcome: "Créer un modèle stable pour le workspace.", deliverable: "Contrat propriétaire–bien–candidature–action.", tasks: [
    task("owner-domain", "Écrire le modèle de domaine", "build", "core", 120, "Donner aux agents une mémoire fiable.", ["Propriétaire et portefeuille.", "Bien et lot.", "Candidature et pièces.", "Action, preuve et validation."], "Chaque objet, rôle et lien est documenté."),
    task("demo-data", "Préparer les données de démonstration", "build", "core", 60, "Visualiser un portefeuille de biens sans utiliser de données réelles.", ["Créer deux biens synthétiques.", "Ajouter candidatures fictives.", "Marquer les actions sensibles."], "La démo peut être parcourue sans secret ni donnée réelle.")
  ]},
  { id: "day-3", number: 3, date: "Semaine 1", shortDate: "Bien", title: "Brancher le portefeuille", outcome: "Faire du bien le point d'entrée du travail.", deliverable: "Fiche bien et activité associée.", tasks: [
    task("property-1", "Créer le premier bien", "build", "core", 150, "Permettre au propriétaire de configurer son bien et ses règles.", ["Créer les champs minimum.", "Ajouter règles de location.", "Afficher l'activité récente."], "Un bien synthétique est persisté et visible dans l'espace propriétaire.")
  ]},
  { id: "day-4", number: 4, date: "Semaine 1", shortDate: "Dossiers", title: "Centraliser les candidatures", outcome: "Relier les candidats, les pièces et le bon bien.", deliverable: "Pipeline de candidatures.", tasks: [
    task("candidate-1", "Créer le pipeline candidat", "build", "core", 150, "Permettre une lecture par statut et par prochaine action.", ["Créer les statuts.", "Rattacher au bien.", "Dédoublonner.", "Afficher la provenance."], "Une candidature se suit de réception à validation.")
  ]},
  { id: "day-5", number: 5, date: "Semaine 2", shortDate: "Pièces", title: "Boucler la complétude", outcome: "Faire demander la bonne pièce au candidat.", deliverable: "Dossier avec statuts et demande ciblée.", tasks: [
    task("document-1", "Construire le coffre et la demande", "build", "core", 180, "Résoudre les dossiers incomplets sans sollicitation inutile.", ["Classer les pièces.", "Calculer les manquants.", "Envoyer la demande depuis la boîte autorisée.", "Rattacher la réponse."], "Une pièce reçue relance la vérification du bon dossier.", [R.cnilDocs, R.dossierDocs])
  ]},
  { id: "day-6", number: 6, date: "Semaine 2", shortDate: "Agents", title: "Donner un rôle à chaque agent", outcome: "Construire une équipe contrôlable.", deliverable: "Contrats et preuves d'agents.", tasks: [
    task("agent-1", "Écrire les contrats d'agents", "build", "core", 150, "Éviter un agent généraliste impossible à auditer.", ["Définir les entrées et sorties.", "Séparer faits et hypothèses.", "Définir les permissions.", "Prévoir l'escalade."], "Chaque agent a une responsabilité et une limite testables.")
  ]},
  { id: "day-7", number: 7, date: "Semaine 2", shortDate: "Validation", title: "Contrôler les actions", outcome: "Rendre rapides les décisions du propriétaire.", deliverable: "File d'actions avec aperçu et audit.", tasks: [
    task("validation-1", "Construire la file de validation", "build", "core", 150, "Empêcher les transmissions et engagements surprises.", ["Afficher acteur et destinataire.", "Prévisualiser les données.", "Autoriser, refuser ou modifier.", "Journaliser."], "Une action sensible reste bloquée tant qu'elle n'est pas autorisée.")
  ]},
  { id: "day-8", number: 8, date: "Semaine 3", shortDate: "Visites", title: "Organiser les rendez-vous", outcome: "Préparer les créneaux sans confondre visite et acceptation.", deliverable: "Calendrier de visites rattaché au bien.", tasks: [
    task("visit-1", "Construire le calendrier interne", "build", "core", 120, "Éviter les échanges dispersés et les doubles réservations.", ["Créer les créneaux du propriétaire.", "Proposer un créneau à une candidature complète.", "Synchroniser les périodes occupées en lecture seule.", "Préparer les futurs connecteurs Google et Outlook."], "Un rendez-vous synthétique est confirmé et historisé sans chevaucher un événement synchronisé.")
  ]},
  { id: "day-9", number: 9, date: "Semaine 3", shortDate: "Sources", title: "Choisir les connecteurs", outcome: "Brancher uniquement des accès autorisés.", deliverable: "Matrice API, flux, permissions et coûts.", tasks: [
    task("source-1", "Étudier les canaux de publication", "research", "core", 150, "Savoir où le logiciel peut agir légalement et techniquement.", ["Données accessibles.", "API, flux et webhooks.", "Droits de publication.", "Coût, limites et révocation."], "Chaque source possède une décision documentée.")
  ]},
  { id: "day-10", number: 10, date: "Semaine 4", shortDate: "Pilote", title: "Préparer le déploiement", outcome: "Tester le logiciel propriétaire avec un cadre clair.", deliverable: "Pilote, sauvegardes, HTTPS et revue de périmètre.", tasks: [
    task("owner-api", "Relier le workspace au backend", "build", "core", 180, "Remplacer progressivement les données de démonstration par des réponses persistées.", ["Brancher l'authentification.", "Relier biens, lots et candidatures.", "Afficher complétude et visites.", "Tester l'isolation."], "Le dashboard lit et écrit le premier workspace propriétaire.", [R.fastapi]),
    task("launch-1", "Préparer le pilote", "proof", "core", 150, "Passer à une version testable sans données réelles.", ["Configurer HTTPS.", "Vérifier sauvegardes et restauration.", "Tester permissions.", "Faire relire la frontière juridique."], "Le pilote possède un plan de surveillance et de retour arrière.", [R.caddy, R.githubActions, R.cci])
  ]}
];
