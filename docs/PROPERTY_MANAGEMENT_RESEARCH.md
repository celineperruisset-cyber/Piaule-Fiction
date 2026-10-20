# Recherche — fiche bien et gestion du portefeuille

Date de recherche : 20 octobre 2026

## Ce que montrent les outils observés

Rentila sépare les **lots** individuels des **immeubles** qui regroupent plusieurs lots. Sa fiche de bien comprend l’adresse, la description, les équipements, les informations financières et administratives, les contrats, certificats et diagnostics, les informations de fiche publique, les photos et les documents. Le produit prévoit aussi l’import CSV/Excel, l’archivage, l’export et le transfert d’un bien. [Rentila — créer un bien ou un lot](https://rentila.fr/support/create-edit-delete-property)

Pour les immeubles, Rentila ajoute les lots liés, les tantièmes et les clés de répartition des charges. Les dépenses communes peuvent être réparties selon des règles générales ou particulières. [Rentila — immeubles et clés de répartition](https://rentila.fr/support/create-edit-delete-building)

Rentila rattache aux biens les assurances, fournisseurs, diagnostics et certificats avec une date d’établissement, une date d’échéance et des rappels avant expiration. [Rentila — certificats et contrats](https://rentila.fr/support/certificates-insurance-and-contracts)

Smovin insiste sur la centralisation des baux et informations locatives par logement, les conditions de révision, les charges récupérables, les échéances, la vue consolidée multi-biens et les rapports de portefeuille. [Smovin — gestion locative résidentielle](https://www.smovin.app/fr-fr/residentiel/)

BailFacile organise le produit autour des différents types de locations, de la gestion financière, des documents conformes, des états des lieux, de la colocation à la chambre, de la SCI et des alertes d’échéances. [BailFacile](https://www.bailfacile.fr/)

Qalimo ajoute le suivi des loyers, charges et travaux, l’aide fiscale, la gestion en nom propre, LMNP et SCI, les différents types de baux et la migration de biens existants. [Qalimo](https://www.qalimo.fr/)

## Ce que notre première API couvre déjà

La tranche actuelle permet de créer un bien et ses lots avec :

- nom, type et adresse ;
- description ;
- identifiant du lot ;
- type de logement, étage, surface, pièces et chambres ;
- loyer, charges et dépôt de garantie ;
- statut du lot ;
- modification et lecture isolées par workspace.

Cela suffit pour brancher un premier bouton « Ajouter un bien », mais ne suffit pas encore pour gérer un portefeuille locatif réel.

## Ce qui manque dans la fiche bien

### Priorité 1 — structure et cycle de vie

- distinguer un bien individuel d’un immeuble regroupant plusieurs lots ;
- ajouter un statut du bien : préparation, vacant, partiellement occupé, occupé, archivé ;
- ajouter une date de disponibilité et une date de mise en location ;
- prévoir archivage et restauration avec conservation de l’historique ;
- ajouter tags, notes privées et personne responsable.

### Priorité 1 — données utiles aux agents

- type de location : vide, meublée, étudiant, mobilité, colocation, parking ou local ;
- équipements et dépendances : parking, cave, balcon, jardin, ascenseur, local vélo ;
- chauffage, eau chaude, énergie et informations DPE ;
- surface habitable, nombre de pièces, chambres, étage et accessibilité ;
- règles de loyer : loyer hors charges, provisions ou forfait de charges, dépôt, révision et date de référence ;
- visibilité de l’adresse exacte et version publique partageable.

### Priorité 1 — documents et échéances

- diagnostics, assurance propriétaire non occupant, contrats fournisseurs et documents de copropriété ;
- date d’émission, date d’expiration, source et fichier associé ;
- rappels configurables avant échéance ;
- état de vérification du document et personne qui l’a validé.

### Priorité 2 — immeuble et copropriété

- lots rattachés à un immeuble ;
- tantièmes généraux ;
- clés de répartition par type de dépense ;
- syndic, coordonnées et documents d’assemblée générale ;
- charges de copropriété et travaux votés.

### Priorité 2 — patrimoine et rentabilité

- mode de détention : nom propre, indivision, SCI, LMNP ;
- prix d’acquisition, frais, date d’achat et financement ;
- taxe foncière, assurance, charges non récupérables et travaux ;
- rendement, trésorerie et valeur estimée dans une vue de portefeuille.

## Ce que je recommande pour Piaule Fiction

Il ne faut pas transformer le premier écran en formulaire de cinquante champs. La meilleure structure est progressive :

1. **Créer rapidement** : nom, adresse, type et statut.
2. **Décrire le lot** : surface, pièces, équipements et paramètres de loyer.
3. **Sécuriser** : diagnostics, assurances, contrats et dates d’échéance.
4. **Préparer la mise en location** : photos, description publique, disponibilité et règles de candidature.
5. **Piloter** : locataire, documents, loyers, interventions et agents.

L’agent Bien peut demander les champs manquants au bon moment, signaler une incohérence et préparer une fiche complète. Il ne doit pas inventer une donnée absente. Le propriétaire garde la validation des informations et des actions externes.

## Décision de conception

Le modèle actuel `property -> lots` est une bonne base. Il faut le conserver, mais ajouter progressivement :

```text
workspace
  └── property / immeuble
        ├── lots
        ├── documents et diagnostics
        ├── contrats fournisseurs et assurances
        ├── règles financières
        ├── candidatures et locations
        └── échéances, tâches et agents
```

La prochaine extension backend devrait enrichir les lots avec le type de location, les équipements, la disponibilité et les échéances principales. La copropriété, la rentabilité et la comptabilité détaillée viendront après la boucle bien → candidature → validation → visite.
