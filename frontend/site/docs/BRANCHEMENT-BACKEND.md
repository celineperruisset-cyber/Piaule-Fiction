# Où brancher les routes backend

Toutes les URLs d'API sont **relatives** (`api/...`) : le frontend suppose que l'API est
servie sur le même domaine que le site, sous `/api/`. En production, Caddy relaie `/api/*`
vers le service Python. En local, `scripts/serve.mjs` simule ces routes ou les relaie
(`API_MODE=proxy`).

Après toute modification dans `src/`, relancer `python3 build.py`.

## 1. Routes déjà branchées (existent dans `backend/main.py`)

### `POST /api/compte` · création de compte, connexion

- **Appel** : `src/app.js` ligne 402 (`const COMPTE_URL = "api/compte"`), envoi ligne 415,
  traitement de la réponse lignes 416-418.
- **Requête** (JSON) :
  `{ "action": "creer" | "connexion", "prenom": "Léa", "email": "lea@exemple.fr", "mdp": "…", "site": "" }`
  (`site` est un champ piège anti-robots : il doit rester vide.)
- **Réponse 200** : `{ "ok": true, "prenom": "Léa", "email": "lea@exemple.fr" }` + cookie
  `pf_s` (HttpOnly, SameSite=Lax, 30 jours).
- **Erreurs** : `{ "ok": false, "erreur": "message affiché tel quel" }` avec 400, 401
  (identifiants), 409 (compte existant), 429 (trop d'essais). Le message `erreur` est affiché
  directement à l'utilisateur : il doit être en français et tutoyer.
- Après succès, le frontend écrit `localStorage["pf-moi"] = {prenom, email}` (ligne 418) et
  va sur `espace.html`.

### `POST /api/compte` · déconnexion

- **Appel** : `src/espace/app.js` lignes 21-24.
- **Requête** : `{ "action": "deconnexion" }`. **Réponse** : `{ "ok": true }` + cookie
  `pf_s` expiré. Le frontend efface `pf-moi` quoi qu'il arrive.

### `GET /api/moi` · vérifier la session

- **Appel** : au démarrage de `src/espace/app.js`.
- **Réponse 200** : `{ "prenom": "Léa", "email": "lea@exemple.fr" }` si le cookie de session
  `pf_s` est valide.
- **Réponse 401** : la page affiche la porte d'entrée et ne considère pas le cache navigateur
  comme une preuve de connexion.

### `POST /api/inscription` · liste d'attente

- Existe côté serveur (e-mail seul, `{ "email": "…", "site": "" }` → `{ "ok": true }`), mais
  **n'est plus appelée** par la version actuelle du frontend (remplacée par la création de
  compte). Gardée pour compatibilité.

## 2. Routes à créer (le frontend est prêt, les points d'accroche sont marqués)

| Besoin | Route proposée | Où brancher dans le frontend | Aujourd'hui |
|---|---|---|---|
| Vérifier la session à l'ouverture de l'espace | `GET /api/moi` → `{prenom, email}` ou 401 | `src/espace/app.js` au démarrage | Branché sur le cookie serveur ; le cache local ne fait foi que pour l'affichage |
| Envoyer la recherche aux agents | `POST /api/recherches` `{texte}` → critères compris | Accueil : `sendSearch()` `src/app.js` ligne 426 (doit renvoyer une Promise de `{type, city, budget, extras, when}`, même forme que `parse()` ligne 50). Espace : envoi du formulaire `src/espace/app.js` lignes 295-305 | `parse()` local par mots-clés ; stockage `pf-recherche` / `pf-recherches` |
| Lister / supprimer les recherches (max 4) | `GET /api/recherches`, `DELETE /api/recherches/:id` | Objet `R` `src/espace/app.js` lignes 27-30 (`all()`, `save()`) ; liste `rsList()` ligne 45 ; suppression ligne 53 | `localStorage` |
| Recherche « précisée par l'Agent » | renvoyée par `POST /api/recherches` | `better(c)` `src/espace/app.js` ligne 35 : construit le texte enrichi (mots de l'utilisateur dans `<mark class="y">`, ajouts de l'Agent dans `<mark class="a">`) | Texte fabriqué localement |
| Profil candidat | `GET` / `PUT /api/profil` `{prenom, tel, ville, situation, revenus}` | Lecture `fillPro()` ligne 229, enregistrement ligne 235 de `src/espace/app.js` | `localStorage["pf-profil"]` |
| Dépôt des pièces du dossier | `POST /api/dossier/pieces` (multipart), `GET /api/dossier` | Liste `PIECES` ligne 167 ; bouton « Commencer mon dossier » (`src/espace/body.html`, désactivé) | Non construit |
| Documents complémentaires + vérification | `POST /api/dossier/complementaires` (multipart : nom, type, fichier) → résultats de vérification ; `DELETE …/:id` | Formulaire `addForm()` envoi lignes 214-218 ; contrôles `checks()` ligne 179 (le résultat serveur doit garder la forme `[libellé, ok: true/false/null, valeur]`) ; suppression ligne 224 | Vérification simulée, le fichier ne quitte pas l'appareil ; `pf-docs` (max 3) |
| Annonces trouvées | `GET /api/annonces?recherche=id` | Mur d'annonces `wall()` ligne 244 et tuiles / tableau de « Ta recherche » dans `render()` ligne 70 | Annonces fictives (photos `photos/`) |
| Statistiques des agents | `GET /api/agents/stats` | Valeurs écrites dans `src/espace/body.html` (1 284 lues, 86 %, 12 arnaques, 9 h, 312 annonces) ; barres `BARS` ligne 149 | Chiffres fixes marqués « Aperçu » |
| Visites | `GET /api/visites` | Bloc calendrier / visites lignes 150-165 de `src/espace/app.js` | Exemples marqués « Exemple » |
| Question de la FAQ | `POST /api/questions` `{texte}` | `src/app.js` ligne 871 (envoi du formulaire `#fq-f`) | Simulé, rien n'est envoyé |

## 3. Conventions à respecter

- Réponses JSON, champ `ok`, message d'erreur lisible dans `erreur` (français, tutoiement).
- Session par cookie `pf_s` HttpOnly ; les appels utilisent `credentials: "same-origin"`.
- Les clés `localStorage` actuelles (`pf-moi`, `pf-recherche`, `pf-recherches`, `pf-profil`,
  `pf-docs`) peuvent rester comme cache d'affichage, mais la source de vérité doit devenir le
  serveur.
- Aucune clé d'API n'est nécessaire côté navigateur : toute clé (IA, stockage, e-mail) doit
  rester côté serveur.
