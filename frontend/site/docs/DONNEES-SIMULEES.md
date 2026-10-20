# Données fictives ou simulées

Tout ce qui suit est inventé pour la démonstration. Le pied de page l'indique
(« Démonstration : annonces et données fictives ») et l'workspace propriétaire marque ces blocs
« Aperçu » ou « Exemple ».

## Accueil (`src/app.js`, `src/body.html`)

| Donnée | Emplacement | Détail |
|---|---|---|
| Lecture de la phrase de recherche | `parse()` ligne 50, `CITIES` ligne 33, `QUART` ligne 34, `GENERIC` ligne 47 | Analyse par mots-clés (ville, type, budget, quand, critères). Recherche par défaut : `CRIT` ligne 49 (studio, Lyon, 600 €, près d'un métro). |
| 8 annonces de la nuit | `BASE` ligne 70, `buildList()` ligne 81 | Surfaces, écarts de loyer, notes de l'Agent ; loyers recalculés selon le budget tapé ; une annonce est une arnaque écartée. Photos `photos/annonce-1..8.jpg`. |
| Compteur « 14 agents cherchent un logement en ce moment » | `src/body.html` ligne 56 (`#live-n`), `src/app.js` ligne 1048 | Nombre aléatoire entre 12 et 17, changé toutes les 4,2 s. |
| Journée « Toi · 07:00 » et compteurs lues / écartées / retenues | `DAY` ligne 697, `buildEvents()` ligne 716 | Calculés, pas mesurés. |
| Pièces du dossier (carte d'identité de « Léa Camille Martin », contrat, fiches de paie…) | `src/body.html` section `#dossier`, `CHK` ligne 445, `CAP` ligne 452 | Personne fictive, numéros de document inventés. |
| Candidature, e-mail à « Madame Durand », « Régie Durand », adresse `location@regie-durand.example` | `src/app.js` lignes 905-915, `src/body.html` sections `#participanture`, `#visite` | Fictifs (domaine `.example` réservé). |
| Conversation « Papa et Maman » | `src/body.html` section `#fin`, `send()` ligne 988 | Scène écrite. |
| Question FAQ envoyée | ligne 871 | Rien n'est envoyé. |

## Workspace propriétaire (`src/espace/app.js`, `src/espace/body.html`)

| Donnée | Emplacement | Détail |
|---|---|---|
| Statistiques (1 284 annonces lues, 86 %, 12 arnaques, 9 h gagnées, 312 annonces) | `body.html` tableau de bord ; barres `BARS` ligne 149 | Chiffres fixes, étiquetés « Aperçu ». |
| « Ta meilleure piste » (690 €, T2 42 m², 94 %) | `body.html` | Fixe. |
| Recherche « précisée par l'Agent » | `better()` ligne 35, `ADDS` ligne 34 | Texte enrichi construit localement. |
| Nombre d'annonces qui collent | `count()` ligne 32 | Formule à partir du budget. |
| Mur d'annonces, tuiles, « déjà vues » | `wall()` ligne 244 | Annonces fictives qui suivent la recherche ; l'une est écartée. |
| Calendrier et visites (« T2 lumineux », « Studio rénové », « Chambre en coloc ») | lignes 150-165 | Exemples placés autour de la date du jour. |
| Exemple de nuit des agents (02:14, 03:40, 06:55, 07:02) | `body.html` onglet `#c-ag` | Fixe, étiqueté « Aperçu ». |
| Vérification des documents complémentaires | `checks()` ligne 179 | Contrôles locaux (longueur du nom, type, extension, taille ≤ 10 Mo) ; « Nom sur le document » reste « À l'ouverture ». Le fichier n'est jamais lu ni envoyé. |
| Heure de l'horloge LED | `DAY` ligne 316 | Heure de la vidéo, pas l'heure réelle. |
| Prénom « Léa » dans le HTML | `body.html` | Valeur de repli, remplacée par le prénom du compte. |

## Données stockées dans le navigateur (`localStorage`)

| Clé | Contenu | Écrite par |
|---|---|---|
| `pf-moi` | `{prenom, email}` du compte connecté | `src/app.js` ligne 418 |
| `pf-recherche` | Phrase de la recherche active | accueil ligne 432, espace |
| `pf-recherches` | Jusqu'à 4 phrases | espace |
| `pf-profil` | `{prenom, tel, ville, situation, revenus}` | espace ligne 238 |
| `pf-docs` | Documents complémentaires `{id, nom, type, file, size}` (sans le contenu du fichier) | espace ligne 217 |

Aucune donnée personnelle réelle n'est incluse dans ce projet.
