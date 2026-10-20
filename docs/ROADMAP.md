# Feuille de route — Piaule Fiction Owner Agent Platform

## Maintenant : logiciel propriétaire et démonstration

1. Recentrer le dashboard sur l'espace propriétaire.
2. Construire le workspace visuel : biens, candidatures, agents, validations et visites.
3. Définir le modèle de domaine propriétaire–bien–candidature–pièce–action.
4. Garder les données de démonstration synthétiques et isolées.
5. Formaliser la frontière logiciel / activité réglementée.

## MVP fonctionnel

1. Compte propriétaire et permissions.
2. Création d'un bien avec règles de location.
3. Tableau des candidatures et statuts explicables.
4. Coffre privé et versionné pour les pièces.
5. Complétude, lisibilité et cohérence des dossiers.
6. Agent de demande de pièce manquante au candidat.
7. Comparaison multi-dossiers avec critères visibles.
8. File de validation avant transmission ou engagement.
9. Calendrier de visites et historique.
10. Journal d'audit, export et suppression.

## Connecteurs

Pour chaque source ou outil, documenter avant développement : données accessibles, API ou flux officiels, webhooks, exports, permissions, coût, limites, droits de publication, provenance, suppression et méthode de révocation.

Les connecteurs de portails doivent être officiels ou explicitement autorisés. Aucun scraping, contournement anti-bot ou usage d'identifiants de tiers ne fait partie du produit.

## Après le MVP

- publication assistée avec contrats partenaires ;
- intégration avec agences et administrateurs de biens titulaires des cartes adaptées ;
- bail, signature et état des lieux selon le rôle juridique du partenaire ;
- loyers, charges, impayés et interventions avec un opérateur habilité ;
- multi-biens, équipes et délégation avancée ;
- paiements et abonnements ;
- montée en charge du VPS vers une architecture séparée.

## Prochaine séquence de travail

1. Valider l'interface propriétaire avec données synthétiques.
2. Remplacer le contrat backend candidat-first par un contrat workspace propriétaire.
3. Ajouter les tables biens, candidatures, actions et validations.
4. Brancher le premier écran sur l'API locale.
5. Tester la boucle « dossier incomplet → demande ciblée → nouvelle pièce → relecture ».
6. Faire relire le périmètre commercial par la CCI ou un conseil spécialisé avant tout lancement de gestion locative.
