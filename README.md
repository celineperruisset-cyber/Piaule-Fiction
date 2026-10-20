# Piaule Fiction

> Le logiciel d’agents IA qui aide les propriétaires à gérer leurs biens, leurs dossiers et leurs actions sensibles.

Piaule Fiction est un workspace propriétaire-first. Le propriétaire renseigne ses biens et ses règles ; des agents spécialisés préparent les annonces, structurent les candidatures, contrôlent la complétude, signalent les incohérences, proposent des visites et organisent les prochaines actions. Le propriétaire reste l’acteur de ses décisions et de ses transmissions.

Le candidat est une partie du dossier, pas l’utilisateur principal du produit.

## Parcours central

```
propriétaire + bien + règles
    -> annonce et canaux autorisés
    -> candidatures rattachées au bon bien
    -> complétude, cohérence et preuves
    -> comparaison expliquée
    -> validation propriétaire ou partenaire habilité
    -> visite, bail et suivi autorisé
```

## MVP propriétaire

- créer un workspace et un portefeuille de biens ;
- configurer les règles et les canaux autorisés ;
- recevoir et rattacher les candidatures à un bien ;
- suivre les pièces, manquants, incohérences et demandes ciblées ;
- comparer des dossiers avec des critères visibles et des preuves ;
- préparer les messages et les créneaux de visite ;
- valider rapidement chaque action externe ;
- conserver un journal d’audit et un contrôle des accès.

## Rôle des agents

Les agents sont spécialisés : Bien/Annonce, Dossier, Complétude, Cohérence, Comparaison, Visites et Suivi. Ils proposent, expliquent et journalisent. Ils ne prennent pas de décision opaque, ne demandent pas de pièce interdite et ne déclenchent pas d’action sensible sans autorisation.

## Cadre produit

Le dépôt construit un logiciel d’aide et d’orchestration. Il ne doit pas masquer une activité d’agence immobilière : mandat, négociation, conclusion d’un bail, encaissement de fonds ou gestion réglementée doivent rester portés par le propriétaire ou par un partenaire habilité selon le montage retenu. Voir [`docs/REGULATORY_BOUNDARY.md`](docs/REGULATORY_BOUNDARY.md).

## Structure

```
backend/            API et contrats du workspace propriétaire
frontend/           prototypes du workspace et parcours participant
frontend/site/      site Piaule Fiction exporté
fixtures/           données synthétiques pour biens, dossiers et candidats
docs/               produit, architecture, sécurité, intégrations et recherche
sprint-dashboard/   feuille de route propriétaire-first
```

## Lancer les prévisualisations

```bash
python3 -m http.server 8000 --directory sprint-dashboard
# ouvrir http://localhost:8000

python3 -m http.server 3000 --directory frontend
# ouvrir http://localhost:3000/owner-agent-preview.html
```

Pour l’API locale :

```bash
python3 -m pip install -r backend/requirements.txt
PIAULE_STATE_DIRECTORY=.local-state uvicorn backend.main:app --reload --port 8000
```

Le site marketing et le futur workspace candidat/participant resteront séparés du cockpit propriétaire. Les sources externes ne sont utilisées que derrière des adaptateurs autorisés et documentés.

## Documentation

- [Direction produit propriétaire](docs/PRODUCT_DIRECTION_OWNER_AGENT_PLATFORM.md) ;
- [Architecture du workspace](docs/PRODUCT_ARCHITECTURE_AND_TRUST.md) ;
- [Frontière réglementaire](docs/REGULATORY_BOUNDARY.md) ;
- [Feuille de route](docs/ROADMAP.md) ;
- [Backlog propriétaire](docs/PRODUCT_BACKLOG_DIFFERENTIATION.md) ;
- [Sécurité et confidentialité](docs/SECURITY_AND_PRIVACY.md) ;
- [Contrats de sources](docs/LISTING_SOURCE_CONTRACT.md).
