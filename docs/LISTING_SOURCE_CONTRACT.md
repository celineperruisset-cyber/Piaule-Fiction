# Contrat des sources et connecteurs

Piaule Fiction travaille depuis le workspace propriétaire. Une source peut alimenter un brouillon d’annonce ou renvoyer des candidatures uniquement si le fournisseur autorise cette intégration.

Pour chaque source, conserver :

- type d’accès : API, webhook, export ou import manuel ;
- données reçues et données envoyées ;
- permission accordée, propriétaire du compte et date d’expiration ;
- limites, coût, quotas et conditions ;
- identifiant externe et idempotence ;
- méthode de révocation ;
- statut `non configuré`, `connecté`, `expiré`, `révoqué` ou `bloqué`.

Un connecteur ne doit pas simuler un compte tiers, contourner une authentification, masquer l’identité du propriétaire ou publier sans droit explicite. Si une source n’offre pas d’intégration autorisée, le produit reste sur un brouillon exportable ou un import manuel validé.
