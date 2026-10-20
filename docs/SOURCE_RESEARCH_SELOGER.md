# Étude connecteur SeLoger

Date de vérification : 16 octobre 2026  
Statut : **connecteur planifié, autorisation partenaire requise**

## Ce que SeLoger met à disposition de son utilisateur

Les pages officielles décrivent une recherche par critères, des favoris, une messagerie avec l'annonceur et des alertes e-mail lorsqu'un bien correspondant est publié. Les annonces affichent notamment le prix, la surface et des caractéristiques principales. SeLoger indique aussi utiliser des outils d'intelligence artificielle pour identifier certains critères dans le texte des annonces.

Sources : [aide et contact SeLoger](https://www.seloger.com/contact.html), [téléchargement de l'application](https://www.seloger.com/telecharger-app), [fonctionnement du classement](https://www.seloger.com/classement_referencement.htm).

## Ce qui est accessible pour Piaule Fiction

| Élément | État | Décision |
| --- | --- | --- |
| Consultation manuelle par le candidat | Oui | Peut rester une action utilisateur, sans extraction automatique |
| Alertes e-mail | Oui | À étudier uniquement avec autorisation et consentement adaptés |
| API publique développeur | Non identifiée dans les pages officielles consultées | Ne pas inventer d'API à partir du HTML |
| Flux ou partenariat professionnel | À clarifier avec Digital Classifieds France / AVIV | Voie prioritaire |
| Envoi automatique de candidature | Non autorisé par défaut | Bloqué tant qu'aucun accord ne le prévoit |
| Scraping, robot ou navigateur automatisé | Interdit par les CGU consultées | Ne pas développer |
| Framing ou affichage dans une autre interface | Interdit sans autorisation expresse | Ne pas développer |

## Limite contractuelle déterminante

Les CGU SeLoger applicables au 26 février 2026 interdisent notamment l'extraction automatisée, le scraping, la fouille de textes et de données, la constitution d'une base concurrente, la visualisation par un autre procédé et le framing sans autorisation. Elles indiquent également que l'utilisation des services est réservée à un usage privé et personnel dans les limites prévues.

Source : [CGU SeLoger](https://www.seloger.com/Conditions_Generales_d_Utilisation.html).

La conséquence produit est claire : un connecteur commercial Piaule Fiction ne doit pas se connecter au site avec les identifiants d'un candidat, aspirer les résultats, contourner une interface ou reproduire une base d'annonces sans accord écrit.

## Architecture retenue

Le backend contient déjà la frontière générique `source → normalisation → dédoublonnage → filtrage candidat`. SeLoger est déclaré comme source planifiée avec la capacité `OFFICIAL_ACCESS_REQUIRED`, mais aucun appel réel n'est effectué.

Si SeLoger accorde un accès officiel, l'adaptateur devra recevoir au minimum :

- un identifiant d'annonce et une URL canonique ;
- le titre, la ville, le loyer, la surface et le type de logement ;
- la date de récupération et la provenance ;
- les limites de réutilisation, de conservation et de fréquence ;
- les droits exacts : lecture, favoris, contact, candidature ou seulement redirection.

## Prochaine action

Préparer une demande de partenariat à Digital Classifieds France / AVIV en décrivant Piaule Fiction, les champs nécessaires, le nombre de candidats prévu, la conservation minimale, la suppression sur demande et les actions que le candidat validerait. Aucun mot de passe ni compte candidat ne doit être transmis au backend en attendant leur réponse.

En parallèle, nous pouvons étudier une source disposant déjà d'une API ou d'un flux explicitement exploitable afin de poursuivre le développement sans dépendre de la réponse de SeLoger.
