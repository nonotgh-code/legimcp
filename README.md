# legimcp — Légifrance, Cour de cassation et BOFiP pour Claude

Serveur MCP donnant accès à trois sources juridiques françaises :

| Source | API sous-jacente | Authentification |
|---|---|---|
| Légifrance (lois, codes, jurisprudence) | Légifrance / PISTE | OAuth2 (client PISTE) |
| Cour de cassation, cours d'appel | Judilibre / PISTE | OAuth2 (même client PISTE) |
| BOFiP (doctrine fiscale) | Open data DGFiP | Aucune |

## Outils exposés

**Légifrance**
- `rechercher_legifrance(query, fond, page, page_size)`
- `get_article_legifrance(article_id)`
- `get_article_code(code_name, numero_article, date)`

**Judilibre (Cour de cassation)**
- `rechercher_jurisprudence_cassation(query, page, page_size, juridiction)`
- `get_decision_cassation(decision_id)`

**BOFiP**
- `rechercher_bofip(query, page, page_size)`
- `get_boi(identifiant_juridique)`
- `explorer_bofip(serie)`

## Prérequis : obtenir vos identifiants PISTE

1. Créez un compte sur https://developer.aife.economie.gouv.fr
2. Créez une "Application" dans votre espace PISTE
3. Abonnez cette application aux API **Légifrance** et **Judilibre** (recherchez-les dans le catalogue d'API du portail et cliquez "S'abonner")
4. Récupérez le `client_id` et le `client_secret` de votre application — ce sont les deux valeurs à renseigner comme variables d'environnement `PISTE_CLIENT_ID` et `PISTE_CLIENT_SECRET`

**Sandbox vs production :** PISTE propose un environnement de test (sandbox) avec des identifiants et des URLs différents de la production. Si vos clés sont des clés sandbox, décommentez les trois variables `*_URL` dans `.env.example` / dans les variables d'environnement Render.

## Test en local

```bash
pip install -r requirements.txt
cp .env.example .env
# éditez .env avec vos identifiants PISTE
python server.py
```

Le serveur écoute alors sur `http://localhost:8000`.

## Déploiement sur Render

1. Créez un dépôt GitHub et uploadez tous les fichiers de ce projet
2. Sur Render : "New +" → "Web Service" → sélectionnez le dépôt
3. Render détecte `render.yaml`. Comme `PISTE_CLIENT_ID` et `PISTE_CLIENT_SECRET` sont marqués `sync: false`, Render vous demandera de les saisir manuellement au moment du déploiement — c'est volontaire, pour ne jamais avoir de secret en clair sur GitHub
4. Une fois déployé, notez l'URL publique (ex: `https://legimcp.onrender.com`)
5. Sur claude.ai : Paramètres → Connecteurs → "Ajouter un connecteur personnalisé" → URL = `https://legimcp.onrender.com/mcp`

## Limites connues et points à vérifier

- Les schémas de réponse JSON de Légifrance et Judilibre indiqués dans `formatters.py` sont basés sur la documentation publique générale de ces API ; **testez chaque outil après déploiement** et ajustez les noms de champs dans `formatters.py` si un format de réponse a changé (les fonctions affichent le JSON brut en cas de champ manquant, pour faciliter le diagnostic).
- Le jeton PISTE est mis en cache en mémoire du process ; sur le plan gratuit de Render (une seule instance), cela ne pose pas de problème, mais le service se met en veille après 15 min d'inactivité (redémarrage + nouvelle authentification au réveil, ~30 sec).
- `rechercher_legifrance` avec `fond="JURI"` couvre déjà une partie de la jurisprudence judiciaire dans Légifrance ; Judilibre reste néanmoins la source la plus à jour et la plus riche spécifiquement pour la Cour de cassation.

## Licence

Code : MIT. Les données restent soumises aux conditions d'utilisation de chaque source (PISTE / Etalab Licence Ouverte 2.0 pour le BOFiP).
