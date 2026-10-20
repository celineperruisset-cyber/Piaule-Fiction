# Limite produit — logiciel IA ou activité immobilière

Ce document fixe la frontière de conception de Piaule Fiction. Il ne remplace pas une consultation de la CCI ou d'un avocat avant une commercialisation de services de mise en location ou de gestion.

## Principe

Le fait d'être un logiciel, d'utiliser une IA, de ne pas encaisser d'argent ou de laisser un clic final au propriétaire ne suffit pas à écarter la réglementation. La loi Hoguet vise notamment les personnes qui prêtent habituellement leur concours à la recherche ou à la location d'un bien appartenant à autrui.

Références à maintenir :

- [Article 1 de la loi n° 70-9 du 2 janvier 1970](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006902223) ;
- [Article 6 sur le mandat et la rémunération](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000032043077/) ;
- [CCI France — carte professionnelle](https://www.cci.fr/offre/obtenir-carte-agent-immobilier).

## Matrice de risque produit

| Fonction | Position initiale | Traitement dans Piaule Fiction |
|---|---|---|
| Stocker biens, contacts et dossiers | Logiciel | Autorisé sous RGPD et permissions strictes |
| Rédiger une annonce | Logiciel | Brouillon, vérification des champs et validation |
| Classer les pièces | Logiciel | Règles déterministes, preuve et incertitude |
| Demander au candidat une pièce autorisée | Assistance | Canal, texte et périmètre documentés |
| Comparer les dossiers | Assistance | Critères liés au bien, sans décision automatisée opaque |
| Suggérer un candidat | Assistance sensible | Proposition explicable ; décision du propriétaire ou du professionnel |
| Contacter et rapprocher activement les parties | Zone réglementée | À faire porter par le propriétaire ou un partenaire habilité |
| Organiser une visite | Zone grise à valider | Préparation possible ; ne pas présenter la visite comme acceptation |
| Négocier, accepter ou conclure le bail | Activité réglementée | Bloqué sans opérateur habilité et mandat adapté |
| Encaisser loyers, dépôts ou charges | Gestion | Hors MVP ; nécessite un montage G et financier adapté |
| Suivre impayés, travaux et relation locataire | Gestion | Partenaire habilité ou validation juridique préalable |

## Règles d'interface

Chaque action externe possède :

- son acteur juridique : propriétaire, candidat, agence partenaire ou Piaule Fiction ;
- son statut : brouillon, à valider, autorisée, exécutée, refusée ou bloquée ;
- son destinataire et les données transmises ;
- sa preuve et sa source ;
- sa possibilité de révocation ou de suppression.

L'interface ne doit pas dire « l'agent a choisi le locataire ». Elle doit dire « l'agent a comparé les dossiers selon ces critères et propose une vérification ».

## Architecture commerciale recommandée

### Mode éditeur logiciel

Piaule Fiction vend un abonnement logiciel. Le propriétaire reste responsable de son annonce et de ses décisions. Les actions de rapprochement, de négociation, de conclusion et de gestion financière sont réalisées directement par le propriétaire ou par un professionnel habilité.

### Mode partenaire professionnel

Une agence ou un administrateur de biens signe le mandat, porte les actes réglementés et utilise Piaule Fiction comme outil et équipe IA. Le compte doit afficher l'identité du partenaire et les actions qu'il assume.

### Mode opérateur Piaule Fiction

Si Piaule Fiction veut prendre les mandats et remplacer juridiquement l'agence, il faudra étudier la carte professionnelle adaptée, la RCP, la garantie financière lorsqu'elle est requise, les mandats, la comptabilité et les obligations de formation. Ce mode ne doit pas être activé par une simple option technique.

## Critères de blocage avant production

- Pas de mandat ou d'autorisation de publication identifiable ;
- pas de règle de validation pour une action sensible ;
- paiement ou dépôt de garantie transitant par Piaule Fiction sans montage validé ;
- demande de pièce non autorisée ;
- classement fondé sur une donnée sensible ou une inférence non documentée ;
- message qui engage le propriétaire ou accepte une candidature sans validation ;
- connecteur de portail non autorisé ou contraire à ses conditions.
