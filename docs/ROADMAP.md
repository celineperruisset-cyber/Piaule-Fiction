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
5. Contrôle antivirus des fichiers reçus avec ClamAV, avant conservation ou analyse.
6. Complétude, lisibilité et cohérence des dossiers.
7. Agent de demande de pièce manquante au candidat.
8. Comparaison multi-dossiers avec critères visibles.
9. File de validation avant transmission ou engagement.
10. Calendrier de visites et historique.
11. Journal d'audit, export et suppression.

Le centre d'actions, de validations et d'audit est maintenant persistant côté backend. Les agents peuvent enregistrer une mission et proposer une action avec une empreinte et une clé d'idempotence. Le propriétaire peut autoriser ou refuser la proposition, et une exécution prématurée est bloquée. L'exécution actuelle ne fait qu'enregistrer le résultat de test ; elle ne déclenche encore aucun connecteur externe.

## Connecteurs

Pour chaque source ou outil, documenter avant développement : données accessibles, API ou flux officiels, webhooks, exports, permissions, coût, limites, droits de publication, provenance, suppression et méthode de révocation.

Les connecteurs de portails doivent être officiels ou explicitement autorisés. Aucun scraping, contournement anti-bot ou usage d'identifiants de tiers ne fait partie du produit.

Le socle de visites est maintenant disponible sans connecteur externe : le propriétaire crée ses créneaux, l’agent propose un horaire à une candidature complète, puis le candidat accepte ou refuse depuis son lien sécurisé. La synchronisation Google/Outlook et les notifications seront ajoutées comme actions séparées après validation des permissions.

## Après le MVP

- récupération de compte par SMS sur numéro vérifié, avec code à usage unique et limites d’envoi ;
- publication assistée avec contrats partenaires ;
- intégration avec agences et administrateurs de biens titulaires des cartes adaptées ;
- bail, signature et état des lieux selon le rôle juridique du partenaire ;
- loyers, charges, impayés et interventions avec un opérateur habilité ;
- multi-biens, équipes et délégation avancée ;
- paiements et abonnements ;
- montée en charge du VPS vers une architecture séparée.

## Prochaine séquence de travail

1. Brancher la file d'actions et le journal d'audit au frontend propriétaire.
2. Définir les contrats d'entrée, de sortie et de permission de chaque agent.
3. Tester la boucle « dossier incomplet → demande ciblée → nouvelle pièce → relecture » avec une action validée.
4. Ajouter les connecteurs un par un derrière la file de validation.
5. Faire relire le périmètre commercial par la CCI ou un conseil spécialisé avant tout lancement de gestion locative.
