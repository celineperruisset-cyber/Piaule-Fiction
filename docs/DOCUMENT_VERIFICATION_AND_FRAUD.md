# Vérification documentaire et détection des anomalies

La confiance documentaire est un axe central de Piaule Fiction. Le produit doit
aider un propriétaire à comprendre ce qui a été contrôlé, par quelle source et
avec quelle limite. Il ne doit jamais présenter une analyse de fichier comme une
certification générale de l'identité, des revenus ou de l'absence de fraude.

## Le modèle de preuve

Chaque pièce possède un état et une preuve associée. Les états sont séparés afin
que l'interface ne confonde pas un dossier complet avec un dossier authentifié :

1. **Reçue** : le fichier est arrivé et a été rattaché à une candidature.
2. **Contrôlée techniquement** : le stockage, le format, la signature de fichier,
   la taille, l'expiration et les doublons ont été examinés.
3. **Cohérente sous réserve** : les informations extraites de plusieurs pièces
   concordent suffisamment pour ne pas déclencher d'alerte, avec une confiance
   affichée.
4. **Source officielle confirmée** : une source reconnue a confirmé la donnée.
5. **Revue humaine** : une personne autorisée a examiné la pièce et a enregistré
   sa décision.

Un modèle, un OCR ou une comparaison de pixels ne peut pas à lui seul produire
le quatrième niveau. L'interface doit employer des libellés précis :
`contrôles techniques passés`, `preuve officielle confirmée`, `anomalie à
éclaircir` ou `revue humaine effectuée`.

## Les contrôles automatiques

Le premier passage, déjà présent dans le backend, vérifie :

- présence du fichier et cohérence de sa taille ;
- extension, type MIME et signature réelle du PDF, JPG ou PNG ;
- date d'expiration lorsqu'elle est connue ;
- doublon dans la même candidature ;
- incompatibilité probable entre le type déclaré et le nom du fichier.

Le deuxième passage devra extraire les champs utiles avec une confiance par
champ, sans conserver plus de données que nécessaire : identité, adresse, période,
employeur, dates, montants, numéro de document et type de pièce. Les contrôles
porteront ensuite sur les relations entre les pièces :

- nom et prénom cohérents entre identité, avis fiscal et justificatifs ;
- adresse cohérente entre justificatif de domicile et autres pièces ;
- continuité des périodes sur les bulletins de salaire ;
- employeur et dates cohérents entre contrat et bulletins ;
- montants et période compatibles avec le type de ressource déclaré ;
- avis fiscal correspondant à l'année annoncée ;
- identité et validité du garant séparées de celles du candidat.

Une anomalie doit produire une explication et une action proposée. Exemple :
« Le bulletin de février indique un employeur différent de celui du contrat.
Demander une clarification ou une pièce plus récente. » L'agent peut poser cette
question au candidat, mais ne doit pas conclure automatiquement à une fraude.

Les métadonnées, polices, couches PDF, zones superposées, incohérences de rendu
et modifications d'image peuvent constituer des signaux de retouche. Ils ne sont
jamais une preuve suffisante : un PDF réenregistré ou numérisé peut présenter ces
signaux sans être frauduleux.

## Vérifications par source

### DossierFacile

Un dossier DossierFacile ne doit être marqué comme vérifié que si le statut
officiel reçu indique qu'il a été vérifié par DossierFacile. Le statut « complet »
signifie seulement que les pièces demandées sont présentes. Les pièces peuvent
être filigranées et le propriétaire peut contrôler le statut avant d'obtenir les
documents.

Piaule Fiction doit donc conserver le résumé du statut, la date, l'identifiant de
la connexion et l'événement reçu. Les documents originaux restent chez
DossierFacile lorsque le parcours partenaire le permet.

### Avis d'impôt

Le candidat dépose son avis ou son ASDIR. Piaule Fiction peut :

1. lire le code 2D-Doc et comparer les informations restituées au document ; ou
2. demander le numéro fiscal et la référence de l'avis, avec consentement
   explicite, afin d'utiliser le service officiel de vérification de la DGFiP si
   le parcours automatisé est autorisé et techniquement stable.

Le résultat à enregistrer est limité à la preuve utile : avis conforme ou non,
année, date du contrôle, identifiant de référence haché et éventuelle différence
entre les champs affichés et les champs vérifiés. Le numéro fiscal et la référence
ne doivent pas être conservés en clair après le contrôle sans nécessité démontrée.

L'API Particulier ne doit pas être considérée comme disponible par défaut. Elle
est soumise à habilitation et à des critères d'éligibilité ; le produit doit
prévoir le service public de vérification de l'avis et le 2D-Doc comme parcours
principal, puis demander une validation spécifique avant tout dossier API.

### Autres pièces

Pour une carte d'identité, un titre de séjour, un contrat de travail ou un
bulletin de salaire, Piaule Fiction peut contrôler la structure, la lisibilité,
les dates, la cohérence et les duplications. Une authentification forte exige une
source qui accepte de vérifier la pièce ou une revue humaine compétente. Le
produit ne doit pas inventer une API officielle lorsque le document n'en propose
pas.

## Score de risque et décisions

Le produit ne doit pas afficher un score unique qui déciderait à la place du
propriétaire. Il doit afficher une liste de signaux classés :

- **information manquante** : le dossier ne peut pas encore être examiné ;
- **à corriger** : format, expiration, lisibilité ou pièce probablement mal
  classée ;
- **à éclaircir** : contradiction entre pièces ou extraction peu fiable ;
- **preuve officielle disponible** : une source a confirmé une donnée précise ;
- **suspicion technique** : plusieurs signaux de retouche ou d'identité
  incohérente, à revoir humainement.

Une candidature ne doit pas être refusée uniquement sur la base d'une inférence
automatique. L'agent demande la pièce autorisée ou la clarification, conserve la
réponse, relance les contrôles et escalade au propriétaire uniquement lorsqu'une
contradiction demeure ou qu'une preuve officielle est indisponible.

## Ce que le propriétaire verra

Pour chaque candidature :

- une barre de complétude séparée de la barre de confiance ;
- la liste des pièces avec leur statut et leur source ;
- les contrôles réussis et les anomalies expliquées ;
- la date du dernier contrôle et la version du moteur ;
- la demande que l'agent peut envoyer au candidat ;
- la décision qui reste à prendre par le propriétaire.

Exemple de restitution :

> Dossier complet à 100 %. Avis d'impôt confirmé par le service officiel pour
> l'année 2025. Identité lisible et non expirée. Contradiction à éclaircir : le
> contrat mentionne un employeur différent des deux derniers bulletins. Aucun
> refus automatique ; demande de clarification prête.

## Protections de données

- ne demander que les pièces autorisées et nécessaires à la location ;
- ne jamais demander les identifiants du compte impots.gouv.fr du candidat ;
- recueillir un consentement séparé pour chaque vérification externe ;
- chiffrer les fichiers et limiter les accès par candidature ;
- conserver les preuves et les journaux sans conserver inutilement les secrets ;
- permettre la révocation, l'export et la suppression ;
- ne pas comparer les empreintes de documents entre candidats ou entre clients
  sans base légale et finalité explicite ;
- journaliser la source, la date, le résultat, la version du moteur et la personne
  ayant validé une décision.

## Sources de référence

- [DGFiP — précisions sur le service de vérification des avis](https://www.impots.gouv.fr/precisions-sur-le-service-de-verification-en-ligne)
- [DGFiP — avis d'impôt et code 2D-Doc](https://www.impots.gouv.fr/particulier/avis-dimpot-sur-le-revenu)
- [API Particulier — conditions d'accès et habilitation](https://production.particulier.api.gouv.fr/developpeurs)
- [DossierFacile — différence entre dossier complet et dossier vérifié](https://aide.dossierfacile.logement.gouv.fr/fr/article/demander-une-verification-de-mon-dossier-dbodju/)
- [DossierFacile — accès propriétaire aux dossiers vérifiés](https://aide.dossierfacile.logement.gouv.fr/fr/article/quelle-est-la-procedure-pour-quun-proprietaire-telecharge-les-pieces-fournies-par-un-candidat-dans-son-espace-proprietaire-frb2fs/)
- [Service-Public — justificatifs pouvant être demandés au candidat](https://www.service-public.fr/particuliers/vosdroits/F1169)
