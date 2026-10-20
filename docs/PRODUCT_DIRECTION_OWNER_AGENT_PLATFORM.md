# Direction produit — Piaule Fiction pour propriétaires

## Positionnement

Piaule Fiction devient un logiciel d'agents IA qui aide les propriétaires à piloter leur bien sans devoir surveiller en permanence des annonces, des boîtes de réception, des dossiers et des échéances.

La promesse n'est pas de transformer l'IA en agence immobilière cachée. La promesse est de fournir au propriétaire une équipe logicielle qui observe, prépare, vérifie, explique et demande une validation au bon moment.

> **Le propriétaire garde le mandat, la décision et la relation juridique. Piaule Fiction fait circuler le travail, les preuves et les propositions.**

## Utilisateur principal

Le premier utilisateur est le propriétaire bailleur, particulier ou petit bailleur, qui veut :

- publier une annonce cohérente à partir des informations de son bien ;
- centraliser les candidatures reçues depuis les canaux autorisés ;
- obtenir une lecture structurée des dossiers ;
- demander automatiquement les éléments manquants au candidat, dans un périmètre autorisé ;
- comparer les profils sans classement opaque ni critère discriminatoire ;
- préparer des réponses, des créneaux et des documents ;
- garder une trace de chaque action, de chaque preuve et de chaque validation ;
- continuer à décider lui-même ou travailler avec un professionnel habilité.

Le candidat reste une partie importante du produit : il reçoit les demandes ciblées, dépose ses pièces dans un espace sécurisé et sait ce qui a été transmis. Il n'est plus le centre de navigation principal du tableau de bord.

## Le problème traité

Un propriétaire non professionnel ne veut pas devenir gestionnaire administratif. Il reçoit des demandes dispersées, ne sait pas toujours quelles pièces sont autorisées, perd du temps à relancer et risque de prendre une décision sur un dossier incomplet ou mal compris.

Piaule Fiction transforme ce flux en une file de travail lisible :

```text
Bien et règles du propriétaire
        ↓
Annonces et canaux autorisés
        ↓
Candidatures centralisées
        ↓
Agents de dossier, conformité et cohérence
        ↓
Questions ciblées au candidat
        ↓
Comparaison expliquée
        ↓
Validation du propriétaire ou du partenaire habilité
        ↓
Visite, bail puis suivi du bien
```

## Agents du premier produit

### Agent Bien et annonce

Il transforme les données du bien en annonce, contrôle les champs manquants et prépare les variantes de publication. Il ne publie pas sur un portail sans canal autorisé ni validation définie.

### Agent Diffusion

Il prépare et suit la publication d'une annonce sur les plateformes choisies par le propriétaire. Il utilise un connecteur officiel ou partenaire, ne conserve jamais les mots de passe et demande une première validation manuelle. Après cette première publication exécutée avec succès, le propriétaire peut autoriser les publications automatiques pour ce compte ; cette autorisation reste révocable et auditée. Chaque publication devient un job idempotent, visible dans la file d'actions et dans l'historique du bien.

### Agent Candidatures

Il centralise les dossiers entrants depuis les intégrations autorisées, rattache chaque pièce au bon candidat et dédoublonne les demandes.

### Agent Complétude

Il vérifie quelles pièces sont reçues, manquantes, illisibles ou incohérentes. Il prépare une demande précise au candidat et évite de solliciter le propriétaire pour une simple pièce manquante.

### Agent Cohérence et confiance

Il compare les informations déclarées aux documents, relève les anomalies et sépare les faits des hypothèses. Il ne certifie jamais une identité ou un document à partir d'une seule sortie de modèle.

### Agent Comparaison

Il présente les dossiers selon des critères explicites liés au bien et aux règles configurées par le propriétaire. Il explique les éléments favorables, les inconnues et les points à vérifier.

### Agent Rendez-vous

Il propose des créneaux compatibles avec les disponibilités autorisées, suit les réponses et évite les doubles réservations. La prise de rendez-vous ne vaut pas acceptation d'une candidature.

### Agent Suivi locatif

Il prépare les rappels, les demandes de pièces, les échéances et les tickets d'intervention. Les envois, engagements financiers, décisions juridiques et changements irréversibles restent soumis aux règles du compte.

## Ce que le produit fait et ne fait pas

### Dans le périmètre logiciel initial

- structurer les biens, lots, contacts, candidatures et événements ;
- rédiger des brouillons ;
- classer les pièces et calculer la complétude ;
- détecter les incohérences et les doublons ;
- poser au candidat une question ou demander une pièce autorisée ;
- produire une comparaison explicable ;
- préparer une visite ou une relance ;
- conserver les preuves et l'historique ;
- brancher des canaux et API officiellement accessibles.

### Hors périmètre sans montage juridique validé

- prendre un mandat de gestion au nom de Piaule Fiction ;
- négocier ou conclure une location pour le propriétaire ;
- choisir définitivement le locataire à sa place ;
- recevoir loyers, dépôts ou charges ;
- gérer les impayés ou les travaux comme mandataire ;
- publier des biens de tiers sans autorisation et sans vérifier le rôle juridique de Piaule Fiction.

Ces fonctions peuvent être intégrées dans un second mode avec une agence ou un administrateur de biens titulaire des cartes et assurances nécessaires.

## Modèle de déploiement

Le premier déploiement est un SaaS propriétaire-first :

1. le propriétaire crée son espace et renseigne ses biens ;
2. Piaule Fiction prépare les actions et les demandes ;
3. le propriétaire définit les règles de validation ;
4. l'agent exécute uniquement les actions autorisées par les connecteurs ;
5. les décisions réglementées ou sensibles remontent dans une file de validation ;
6. un partenaire habilité peut prendre le relais pour les activités qu'il porte juridiquement.

Le produit doit rendre visible cette séparation dans l'interface : **préparé par l'agent**, **à valider**, **exécuté par le propriétaire**, **exécuté par le partenaire**, **bloqué par le périmètre**. Le worker d'orchestration ne doit jamais masquer l'étape intermédiaire : il crée des sous-missions, puis chaque agent spécialisé produit ses propres preuves et actions.

## MVP reorienté

Le premier MVP fonctionnel porte sur un propriétaire, un bien et un flux de candidatures synthétiques :

1. compte et espace propriétaire ;
2. création d'un bien et de ses règles ;
3. tableau des candidatures ;
4. coffre documentaire candidat ;
5. complétude et cohérence déterministes ;
6. demande ciblée de pièce manquante ;
7. comparaison explicable ;
8. file de validations ;
9. calendrier de visites ;
10. journal d'audit et suppression des données.

Les intégrations de portails et les paiements viennent après les contrats de domaine et le mode démonstration.
