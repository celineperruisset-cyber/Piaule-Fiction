# Piaule Fiction · code source frontend

Le site présente Piaule Fiction comme un logiciel d’agents IA pour propriétaires bailleurs et professionnels habilités. Le workspace propriétaire est le produit principal ; un espace participant peut ensuite être relié aux demandes de pièces, confirmations et visites.

Le projet utilise HTML, CSS et JavaScript natifs. Les pages servies sont générées depuis `src/` par `build.py`.

```bash
cd frontend/site
npm run dev
```

Pour relayer `/api/*` vers le backend :

```bash
API_MODE=proxy API_TARGET=http://127.0.0.1:8000 npm run dev
```

Les données de démonstration sont synthétiques. Aucun message, document ou publication externe ne doit partir depuis le prototype.
