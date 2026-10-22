# Consolidation backend — Piaule Fiction

Cette étape consolide le backend propriétaire sans activer artificiellement de fournisseur externe.

## Pièces de candidature

Les fichiers restent dans `PIAULE_UPLOAD_DIRECTORY`, hors du répertoire public du frontend. Le nom de stockage est généré par Piaule et n'est jamais renvoyé au navigateur.

- `GET /api/biens/{bien}/candidatures/{candidature}/pieces/{piece}/telecharger` : téléchargement réservé au propriétaire authentifié, avec `Cache-Control: private, no-store`.
- `DELETE /api/biens/{bien}/candidatures/{candidature}/pieces/{piece}` : suppression permanente d'une pièce et de ses contrôles associés.
- `GET /api/biens/{bien}/candidatures/{candidature}/verification-summary` : synthèse explicable pour l'espace propriétaire.
- Chaque lecture et suppression crée un événement dans `/api/audit`. Le contenu des documents n'est jamais copié dans le journal.

La vérification locale distingue désormais clairement :

- contrôle technique : fichier présent, taille, MIME, signature PDF/JPG/PNG, doublon, expiration et cohérence indicative du nom ;
- preuve externe : DossierFacile, France Identité, DGFiP, employeur ou revue humaine ;
- limite : un contrôle technique ne prouve pas qu'une pièce est authentique.

Les demandes de preuve externe restent soumises au consentement du candidat et au branchement réel du fournisseur.

## Rétention des candidatures

Le statut `refusee` programme déjà une purge après `PIAULE_APPLICATION_REJECTED_RETENTION_DAYS` jours, 90 par défaut. Le worker interne :

```text
POST /api/internal/candidatures/purger
X-Piaule-Agent-Token: ...
```

supprime les pièces, messages et liens temporaires puis anonymise la trace minimale de la candidature. Une candidature convertie en locataire n'est pas purgée.

## Missions d'agents

Les missions exposent maintenant `tentatives`, `tentatives_max` et `prochaine_tentative_le`. Une mission en échec peut être remise en file dans sa limite :

```text
POST /api/internal/agent-runs/{run_id}/retry
X-Piaule-Agent-Token: ...
```

Le runtime IA n'appelle pas encore un modèle simplement parce qu'une clé est présente. `GET /api/parametres/agents/runtime` indique séparément la configuration et l'exécution réelle. Les rôles et leurs actions autorisées restent contrôlés par le contrat backend.

## Production et sauvegardes

- `GET /health` vérifie la disponibilité de la base et du stockage.
- `GET /api/parametres/production` donne au propriétaire une checklist sans révéler les secrets.
- `POST /api/internal/maintenance/backup` crée une copie SQLite cohérente dans `PIAULE_BACKUP_DIRECTORY`.

Variables utiles :

```bash
PIAULE_UPLOAD_DIRECTORY=/var/lib/piaule/uploads
PIAULE_BACKUP_DIRECTORY=/var/backups/piaule
PIAULE_APPLICATION_REJECTED_RETENTION_DAYS=90
PIAULE_AI_PROVIDER=...
PIAULE_AI_MODEL=...
PIAULE_AI_API_KEY=...
PIAULE_AI_MAX_REQUESTS_PER_DAY=1000
```

La copie locale n'est pas une stratégie de sauvegarde complète : le VPS doit ensuite transférer les sauvegardes vers un stockage séparé, chiffré et testé en restauration.
