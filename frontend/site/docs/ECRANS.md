# Écrans et rôle de chacun

Le site compte 4 fichiers HTML. L'accueil est une seule page découpée en « pages » plein
écran que l'on traverse au défilement (pas de routeur : les sections sont des ancres `#id`).

## 1. Accueil · `index.html` (sources `src/body.html`, `src/style.css`, `src/app.js`)

| # | Section (`id`) | Rôle |
|---|---|---|
| 0 | Barre du haut (`header.top`) | Logotype, raccourcis « Comment ça marche » et « Garanties », « Bande-annonce », bouton « Viens essayer » (devient « Mon espace » une fois connecté), menu à trois barres. |
| – | Menu (`#drawer`) | Panneau qui glisse depuis la droite : liste des pages du site, « Lancer ma recherche », « Voir la bande-annonce ». |
| – | Rail (`#rail`) | Points de navigation verticaux, un par page, qui suivent le défilement. |
| 1 | Ouverture (`#ouverture`) | Vidéo d'ouverture en fond (`intro/accueil.mp4`), titre Piaule Fiction, signature « Gérer ses biens, c'est pas de la fiction. », bouton bande-annonce. Au défilement, la vidéo se dissout en poussière de lumière. |
| 2 | Tes biens (`#recherche`) | Le champ principal : on décrit le logement voulu, en texte libre. Guide « Je ne sais pas quoi écrire » (choix Où / Quoi / Budget / Quand qui écrivent la phrase). « Lancer les agents de gestion » garde la phrase et ouvre la création de compte. Début du film de la clé (nuit). |
| 3 | Jour et nuit (`#nuit`) | « Pendant que tu vis ta vie, tes agents cherchent » : une journée défile (Toi · 07:00…) en parallèle des annonces lues, écartées, retenues par les agents. |
| 4 | Dossiers reçus (`#dossier`) | « Dossiers reçus, vérifié et certifié » : les pièces (carte d'identité, contrat, fiches de paie…) arrivent, entrent dans le dossier et sont vérifiées, au rythme du défilement. |
| 5 | Ta participanture (`#participanture`) | « Une notif, un oui, c'est envoyé » : notification d'annonce sur téléphone, message de demande de visite rédigé par l'Agent. |
| 6 | La visite (`#visite`) | « Il ne te reste qu'à décrocher » : appel de la régie, créneau ajouté à l'agenda. |
| 7 | Tes garanties (`#garanties`) | « Tu gardes la main » : cartes en verre qui défilent (accord avant envoi, arnaques détectées, etc.). |
| 8 | Le lendemain matin (`#fin`) | Conversation familiale « Papa et Maman » ; on maintient le bouton pour envoyer « Papa, maman, j'ai le bail. » (confettis), puis « Commencer ma recherche ». |
| 9 | Questions fréquentes (`section.after`) | FAQ en accordéon + « Une autre question ? » (champ libre). |
| 10 | Pied de page (`footer.foot`) | Bande-annonce, mentions légales, confidentialité, mention « Démonstration : annonces et données fictives ». |
| – | Bande-annonce (`#trailer`) | Lecteur plein écran de la bande-annonce (`intro/intro-hd.mp4`), crédits musicaux. |
| – | Compte (`#esp`) | Fenêtre « Ton workspace propriétaire » : création de compte (prénom, e-mail, mot de passe, accord) ou connexion ; rappelle la recherche tapée. |

Le « film de la clé » (`#film`, canvas) est le décor commun : il passe de la nuit à l'aube
au fil des pages, image par image (`film/t1` à `film/t5`).

## 2. Workspace propriétaire · `espace.html` (sources `src/espace/*`)

Sur ordinateur (≥ 901 px), un seul écran sans défilement : un grand cadre de verre posé sur
la vidéo de la journée du personnage. Sur mobile, la page défile et les onglets deviennent
une barre collante.

| Écran | Rôle |
|---|---|
| Garde (`#gate`) | Si aucun compte n'est connu dans ce navigateur : « Ton espace t'attend. Crée ton compte depuis l'accueil ». |
| Fond (`#room`) | Vidéo en boucle de la journée (`journee.*`, ou `journee-m.*` sur mobile) ; horloge LED synchronisée sur l'heure de la vidéo. |
| Barre latérale (`aside.side`) | Marque, avatar et prénom, 6 onglets, widgets « Dossiers traités » et « Tes agents », « Se déconnecter ». |
| Tableau de bord (`#c-home`) | « Bonjour X », champ de recherche, horloge, 4 statistiques, courbe d'activité, « Ta meilleure piste », aperçu du dossier, critères (budget, ville, logement), calendrier et prochaines visites. |
| Ton profil (`#c-pro`) | Formulaire profil participant : prénom, e-mail (lecture seule), téléphone, ville actuelle, situation, revenus ; jauge de complétude ; colonne « Ce qui rassure ». |
| Tes biens (`#c-rech`) | « Tu as écrit » puis « Tes biens, précisée par l'Agent » (mots de l'utilisateur en bleu, ajouts de l'Agent en roux) ; boutons « Précise en un clic » ; annonces qui collent ; jusqu'à 4 recherches (« Tes recherches », « Nouvelle recherche »). |
| Dossiers reçus (`#c-dos`) | Grand dossier de verre « Dossier de X » avec 5 feuilles (identité, activité, revenus, garant, avis d'imposition) que l'on tire une par une ; feuille « + Document complémentaire » (jusqu'à 3) avec vérification en direct. |
| Tes agents (`#c-ag`) | Les trois agents (Lecteur, Vérificateur, Candidat), leur état, exemple de nuit de travail. |
| Tes visites (`#c-vis`) | Prochaine visite (exemple), tableau des visites, calendrier, conseils « Avant la visite ». |
| Barre « Fermer pour le voir vivre » (`#winbar`) | Efface le tableau de bord pour regarder la vidéo en entier ; « Rouvrir mon espace » ou Échap le fait revenir. |
| Menu du compte (`#me`) | Avatar en haut (mobile) : prénom, e-mail, « Se déconnecter ». |

## 3. Pages légales

- `mentions-legales.html` : éditeur, hébergeur, propriété intellectuelle.
- `confidentialite.html` : données collectées et droits.
