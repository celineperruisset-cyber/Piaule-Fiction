# Dépendances externes

## Au fonctionnement du site

**Aucune.** Pas de framework, pas de bibliothèque JavaScript, pas de CDN, pas de Google Fonts,
pas d'outil d'analyse ni de traceur. Toutes les ressources sont dans le projet :

| Ressource | Emplacement | Origine / licence |
|---|---|---|
| Police Instrument Sans | `fonts/*.woff2` | Google Fonts, licence SIL Open Font License 1.1 (auto-hébergée) |
| Icônes | SVG écrits directement dans le HTML et le JS | maison |
| Images du film, photos, visuels | `film/`, `photos/`, `hirondelle-*.jpg`, `journee.*` | générées pour le projet (Higgsfield) |
| Musiques de la bande-annonce | intégrées dans `intro/intro-hd.mp4` | Kevin MacLeod (incompetech.com), CC BY 4.0 ; sons Wikimedia Commons (CC BY 4.0, CC BY-SA 4.0, CC0) ; crédits affichés dans le lecteur et le pied de page |

Seuls liens sortants : `cnil.fr` et `hostinger.fr` dans les pages légales.

## APIs du navigateur utilisées

`fetch`, `localStorage`, `IntersectionObserver`/`requestAnimationFrame`, `<canvas>` 2D,
`<video>` (WebM VP9 sinon MP4 H.264), `matchMedia("(prefers-reduced-motion: reduce)")`
(les animations sont réduites si l'utilisateur le demande), `Intl.NumberFormat("fr-FR")`.

## Outils de développement

| Outil | Usage | Obligatoire ? |
|---|---|---|
| Node.js ≥ 18 | `scripts/serve.mjs` (serveur local + API simulée), modules intégrés uniquement | oui pour `npm run dev` |
| Python 3 | `build.py` (assemblage des pages), `../../backend/main.py` | seulement pour reconstruire / lancer le backend |

## Côté serveur en production (pour information)

Le site en ligne est servi par Caddy (fichiers statiques + `/api/*` relayé vers
`backend.main:app` sur le port 8000, service systemd). Aucun service tiers (paiement, e-mail,
stockage) n'est branché aujourd'hui.
