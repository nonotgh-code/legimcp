# legimcp

Serveur MCP (Model Context Protocol) donnant à Claude un accès direct à six sources juridiques françaises et européennes : lois, codes, jurisprudence judiciaire, doctrine fiscale, législation UE et droits fondamentaux européens.

## Comment ça marche

Ce projet expose 13 **outils** que Claude peut appeler pendant une conversation, un peu comme des fonctions à sa disposition. Chaque outil interroge une API juridique officielle, puis reformate la réponse en texte lisible avant de la renvoyer à Claude.

```
Vous posez une question
        │
        ▼
   Claude choisit l'outil pertinent
        │
        ▼
  legimcp (ce serveur, hébergé sur Render)
        │
        ▼
  API officielle correspondante (PISTE, DGFiP, UE, Conseil de l'Europe)
        │
        ▼
  Réponse reformatée renvoyée à Claude, qui vous répond
```

Le serveur tourne en continu sur [Render](https://render.com), un hébergeur cloud qui le redéploie automatiquement à chaque mise à jour du code sur ce dépôt GitHub.

## Les six sources

| Source | Ce qu'elle couvre | API sous-jacente | Authentification |
|---|---|---|---|
| **Légifrance** | Lois, décrets, articles de codes, délibérations CNIL, jurisprudence | Légifrance (portail PISTE) | OAuth2 (clé PISTE) |
| **Judilibre** | Décisions de la Cour de cassation, cours d'appel, tribunaux judiciaires | Judilibre (portail PISTE) | OAuth2 (même clé PISTE) |
| **BOFiP** | Doctrine fiscale de la DGFiP (impôts) | Open data DGFiP | Aucune (public) |
| **EUR-Lex** | Règlements, directives, décisions de l'Union européenne | SPARQL sur Cellar (Office des publications de l'UE) | Aucune (public) |
| **CJUE** | Arrêts de la Cour de justice de l'Union européenne | SPARQL sur Cellar (même point d'accès qu'EUR-Lex) | Aucune (public) |
| **CEDH** | Arrêts et décisions de la Cour européenne des droits de l'homme | HUDOC (Conseil de l'Europe) | Aucune (public) |

**PISTE** est le portail officiel de l'État français qui centralise l'accès à plusieurs API juridiques (Légifrance, Judilibre). Une seule paire d'identifiants (`Client ID` / `Client Secret`, de type OAuth2) donne accès aux deux.

## Les 13 outils

**Légifrance**
- `rechercher_legifrance(query, fond, page, page_size)` — recherche par mots-clés dans un fonds documentaire (lois, codes, CNIL, jurisprudence administrative...)
- `get_article_legifrance(article_id)` — texte intégral d'un article via son identifiant
- `get_article_code(code_name, numero_article, date)` — un article de code directement par son numéro (ex: "Code civil", "1240")

**Judilibre — Cour de cassation**
- `rechercher_jurisprudence_cassation(query, page, page_size, juridiction)` — recherche plein texte, filtrable par niveau de juridiction (Cour de cassation / cours d'appel / tribunaux judiciaires)
- `get_decision_cassation(decision_id)` — texte intégral d'une décision

**BOFiP — doctrine fiscale**
- `rechercher_bofip(query, page, page_size)` — recherche plein texte
- `get_boi(identifiant_juridique)` — un BOI complet par son identifiant (ex: "BOI-CF-IOR-10")
- `explorer_bofip(serie)` — liste les séries du BOFiP, ou les BOI d'une série donnée

**EUR-Lex — législation UE**
- `rechercher_legislation_ue(query, page_size)` — recherche par mot du titre
- `get_texte_ue(celex)` — titre, date et lien officiel d'un texte via son numéro CELEX

**CJUE — jurisprudence UE**
- `rechercher_jurisprudence_cjue(query, page_size)` — recherche par mot du titre (souvent les noms des parties)
- `get_arret_cjue(celex)` — titre, date et lien officiel d'un arrêt via son numéro CELEX

**CEDH**
- `rechercher_cedh(query, page_size)` — recherche plein texte dans les arrêts et décisions

## Architecture du code

```
legimcp/
├── server.py              → point d'entrée, déclare les 13 outils exposés à Claude
├── piste_auth.py          → authentification OAuth2 partagée (Légifrance + Judilibre)
├── legifrance_client.py   → appels HTTP à l'API Légifrance
├── judilibre_client.py    → appels HTTP à l'API Judilibre
├── bofip_client.py        → appels HTTP à l'open data BOFiP
├── eurlex_client.py       → requêtes SPARQL à Cellar (EUR-Lex + CJUE)
├── hudoc_client.py        → appels HTTP à HUDOC (CEDH)
├── formatters.py          → transforme chaque réponse JSON en texte lisible
├── requirements.txt       → dépendances Python
├── render.yaml            → configuration de déploiement Render
└── .env.example           → modèle de variables d'environnement pour un test en local
```

Chaque source a son propre fichier "client" (les appels HTTP bruts) et partage `formatters.py` pour la mise en forme — ça permet d'ajouter une nouvelle source sans toucher aux autres.

## Prérequis : obtenir des identifiants PISTE

Nécessaire uniquement pour Légifrance et Judilibre (les quatre autres sources sont publiques, sans clé).

1. Créez un compte sur [developer.aife.economie.gouv.fr](https://developer.aife.economie.gouv.fr)
2. Créez une application dans votre espace PISTE
3. Abonnez cette application aux API **Légifrance** et **Judilibre** depuis le catalogue
4. Récupérez le **Client ID** et le **Client Secret OAuth2** de l'application (pas la "clé API" simple, qui est différente)

## Test en local

```bash
pip install -r requirements.txt
cp .env.example .env
# éditez .env avec vos identifiants PISTE
python server.py
```

Le serveur écoute alors sur `http://localhost:8000`.

## Déploiement sur Render

1. Sur Render : **"New +" → "Web Service"**, connectez ce dépôt
2. Renseignez les variables d'environnement `PISTE_CLIENT_ID` et `PISTE_CLIENT_SECRET` (jamais stockées dans le code, pour rester sur GitHub sans risque)
3. Une fois déployé, connectez l'URL obtenue (`https://votre-service.onrender.com/mcp`) comme connecteur personnalisé sur claude.ai

## Limites connues

- **EUR-Lex et CJUE** : la recherche porte sur le **titre** des documents, pas leur texte intégral (le point d'accès public utilisé, SPARQL sur Cellar, ne permet pas la recherche plein texte). Pour une expression précise dans le corps d'un texte, mieux vaut d'abord identifier le document par son titre ou son numéro CELEX.
- **Render (plan gratuit)** : le service se met en veille après 15 minutes d'inactivité ; la première requête après une pause prend jusqu'à ~30 secondes.
- Les schémas de réponse JSON de certaines API (notamment Légifrance selon le fonds interrogé) peuvent varier ; `formatters.py` inclut des diagnostics automatiques qui affichent la structure brute quand un champ attendu est introuvable, pour faciliter les ajustements futurs.

## Licence

Code : MIT. Les données de chaque source restent soumises à ses propres conditions d'utilisation (Etalab Licence Ouverte 2.0 pour le BOFiP et les données publiques françaises, conditions PISTE pour Légifrance/Judilibre, conditions de l'Office des publications de l'UE et du Conseil de l'Europe pour EUR-Lex/CJUE/CEDH).
