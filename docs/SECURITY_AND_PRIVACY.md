# Sécurité et confidentialité

Piaule Fiction manipule des données de propriétaires, candidats, documents et échanges. La confiance est une fonctionnalité principale du workspace.

## Principes

- minimisation et finalité explicite ;
- séparation stricte des workspaces ;
- chiffrement en transit et au repos ;
- documents privés, accès temporaires et journaux ;
- aucune décision défavorable fondée sur une inférence ou un score opaque ;
- aucune pièce interdite ou disproportionnée demandée par l’agent ;
- consentement et validation avant transmission ;
- suppression et export compréhensibles ;
- secrets hors Git, rotation et révocation des connecteurs ;
- sauvegardes testées et restauration documentée.

Le candidat doit savoir quelle pièce est demandée, pour quelle raison, à qui elle serait transmise et pendant combien de temps. Le propriétaire doit savoir ce que l’agent a lu, proposé, envoyé et bloqué.

## Preuve documentaire

Piaule Fiction sépare quatre niveaux qui ne doivent pas être confondus :

- `non_verifie` : la pièce a été reçue, mais aucune vérification n'est encore établie ;
- `controles_techniques` : le stockage, le format, la signature de fichier, l'expiration et les doublons ont été contrôlés ;
- `revue_humaine` : une personne autorisée a examiné la pièce et a enregistré sa décision ;
- `source_officielle` : une source partenaire reconnue, comme un dossier DossierFacile effectivement vérifié, a fourni la preuve correspondante.

Un contrôle de format ou une sortie de modèle ne certifie pas l'identité du candidat, l'origine administrative d'un document, l'absence de retouche ou la réalité des revenus. Ces éléments doivent rester `non_verifiable_localement` tant qu'ils ne sont pas confirmés par une source officielle, un contrôle spécialisé documenté ou une revue humaine. L'interface et les messages commerciaux doivent employer « contrôle technique », « anomalie détectée » ou « dossier vérifié par DossierFacile » selon la preuve disponible, et ne jamais transformer une simple analyse en certification générale.

Les demandes de vérification externe sont créées au niveau du bien selon la politique choisie par le propriétaire (`standard`, `renforcee` ou `officielle`). Elles ne peuvent pas être exécutées silencieusement : le candidat doit consentir depuis son lien sécurisé, puis le connecteur doit retourner une preuve signée ou documentée. Piaule Fiction ne stocke pas les identifiants du candidat pour impots.gouv.fr et ne considère pas une réponse d'IA comme une source officielle. Les références externes sont hachées lorsqu'elles doivent seulement servir à l'audit.
