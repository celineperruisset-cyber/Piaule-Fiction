# Boutons, formulaires et interactions

« Réel » = appelle le serveur. « Local » = reste dans le navigateur. « Animation » = pur
effet visuel. Les numéros de ligne renvoient aux fichiers de `src/`.

## Accueil (`src/body.html`, `src/app.js`)

### Navigation

| Élément | Sélecteur | Effet | Type |
|---|---|---|---|
| Logotype | `.lockup[data-go="0"]` | Revient à « Tes biens » | Local |
| Comment ça marche / Garanties | `.tnav a[data-go]` | Défile jusqu'à la page (`goTo(i)`) | Local |
| Menu trois barres | `#mbtn` | Ouvre le panneau `#drawer` (Échap ou `#dr-x` ferme) | Local |
| Liens du menu | `#dr-nav a` | Vont à la page choisie | Local |
| « Lancer ma recherche » (menu) | `#dr-go` | Va au champ de recherche | Local |
| Points du rail | `#rail a` | Vont à la page | Local |
| « Glisse pour découvrir », « Défile… » | `.ouv-cue`, `.cue` | Font défiler | Local |
| Molette / glisser | – | Fait avancer le film de la clé et les scènes de chaque page | Animation |

### Bande-annonce

| Élément | Sélecteur | Effet |
|---|---|---|
| Tous les boutons bande-annonce (barre, menu, ouverture, recherche, pied de page) | `.js-trailer`, `#trailer-open` | Ouvrent `#trailer` et lisent `intro/intro-hd.mp4` |
| Fermer | `#trailer-x`, Échap | Ferme le lecteur |

### Tes biens

| Élément | Sélecteur | Effet | Type |
|---|---|---|---|
| Champ « Décris le bien à gérer » | `#ask-in` | Texte libre ; exemples qui s'écrivent seuls tant que le champ est vide ; Entrée envoie | Local |
| « Je ne sais pas quoi écrire » | `#help` | Ouvre le guide `#guide` | Local |
| Puces Où / Quoi / Budget / Quand | `#guide button[aria-pressed]` | Écrivent la phrase dans le champ | Local |
| « C'est bon » | `#g-ok` | Ferme le guide | Local |
| « Lancer les agents de gestion » | `#go` (submit de `#ask`) | Garde la phrase (`localStorage["pf-recherche"]`), la lit avec `parse()` pour personnaliser les pages suivantes (ville, quartier, loyer…), puis ouvre la fenêtre compte | Local (`sendSearch`, app.js:426) |
| « Essayer maintenant » | `#try` | Ouvre la fenêtre compte (ou l'espace si déjà connecté) | Local |

### Fenêtre compte « Ton workspace propriétaire » (`#esp`, formulaire `#cpt-f`)

| Élément | Effet | Type |
|---|---|---|
| « Viens essayer » / « Mon espace » (`#tcta`) | Ouvre la fenêtre, ou va directement sur `espace.html` si `pf-moi` existe | Local |
| Champs prénom, e-mail, mot de passe (8 à 128 caractères), case d'accord, champ piège invisible `site` (anti-robots) | Contrôles côté navigateur avec messages en français | Local |
| Œil `#cpt-eye` | Affiche / masque le mot de passe | Local |
| « Créer mon compte » / « Se connecter » (`#cpt-go`) | `POST api/compte` (`action: "creer"` ou `"connexion"`), puis enregistre `pf-moi` et va sur `espace.html` | **Réel** (app.js:402-423) |
| « Déjà un compte ? Se connecter » (`#cpt-sw`) | Bascule création / connexion | Local |
| « Voir d'abord comment ça marche » (`#esp-go`) | Ferme et va à « Jour et nuit » | Local |
| Fermer `#esp-x`, clic à l'extérieur, Échap | Ferme | Local |

### Scènes au défilement (aucun clic)

Jour et nuit (compteurs lues / écartées / retenues), Dossiers reçus (pièces vérifiées),
Ta participanture (notification, e-mail rédigé), La visite (appel, agenda), Tes garanties
(cartes qui défilent) : animations pilotées par la position de défilement, données fictives.

### Le lendemain matin (`#fin`)

| Élément | Effet | Type |
|---|---|---|
| Bouton maintenu `#send` (souris ou doigt, 0,9 s) | Envoie « Papa, maman, j'ai le bail. », réponses de la famille, confettis | Animation |
| Puce `#morph` | Bascule l'animation du mot « bail » | Animation |
| « Commencer ma recherche » `#m-cta` | Revient au champ de recherche et le sélectionne | Local |
| « Renvoyer le message » `#resend` | Rejoue la scène | Animation |

### Questions fréquentes

| Élément | Effet | Type |
|---|---|---|
| Questions `.fq-q` | Accordéon, une seule ouverte | Local |
| « Une autre question ? » `#fq-f` + `Envoyer` | Affiche « Merci, ta question est bien notée » ; **rien n'est envoyé** | Simulé (app.js:867-871) |

## Workspace propriétaire (`src/espace/body.html`, `src/espace/app.js`)

| Élément | Sélecteur | Effet | Type |
|---|---|---|---|
| Garde | `#gate` | Affichée si `pf-moi` absent ; bouton vers l'accueil | Local |
| Onglets | `#rail [role=tab]` (`t-c-home`, `t-c-pro`, `t-c-rech`, `t-c-dos`, `t-c-ag`, `t-c-vis`) | Changent de page ; point vert = étape faite | Local |
| Cartes du tableau de bord | `[data-go]` | Ouvrent l'onglet correspondant | Local |
| Champ de recherche | `#ask`, `#ask-in` | Recherche de 6 caractères minimum ; remplace la recherche active ou en ajoute une (max 4) ; la phrase venue de l'accueil se retape lettre par lettre | Local (`pf-recherche`, `pf-recherches`) |
| Idées | `#ideas button` | Remplissent le champ | Local |
| « + Meublé », « + Calme »… | `#pr-adds [data-add]` | Ajoutent un critère à la recherche | Local |
| « Nouvelle recherche » | `#rs-new` | Prépare une recherche supplémentaire | Local |
| Liste « Tes recherches » | `#rs-l` | Passe d'une recherche à l'autre | Local |
| « Modifier » | `#edit` | Remet la recherche dans le champ | Local |
| Formulaire profil | `#pro` + « Enregistrer » | Enregistre prénom, téléphone, ville, situation, revenus | Local (`pf-profil`, app.js:235) |
| Feuilles du dossier | `#papers [data-p]` | Tirent une pièce et affichent ce que l'Agent vérifie | Local |
| « + Document complémentaire » | `.paper.add` → `#df` | Nom, type, fichier (PDF ou photo) ; vérification affichée en direct ; « Ajouter au dossier » ; suppression `[data-del]` | Simulé : seul le nom, le type, le nom et la taille du fichier sont gardés (`pf-docs`), le fichier n'est pas envoyé (app.js:176-224) |
| « Commencer mon dossier » | – | Désactivé : « Le dépôt ouvre bientôt » | À construire |
| « Ajouter à mon agenda », « Itinéraire » | – | Désactivés (exemple) | À construire |
| « Fermer pour le voir vivre » | `#cine`, Échap | Masque / réaffiche le tableau de bord | Local |
| Menu compte, « Se déconnecter » | `#me-b`, `#me-out`, `#sd-out` | `POST api/compte` `{action: "deconnexion"}`, efface `pf-moi`, retour à l'accueil | **Réel** (app.js:21-24) |
