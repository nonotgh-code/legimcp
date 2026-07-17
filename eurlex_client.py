"""
Client pour EUR-Lex et la jurisprudence de la CJUE, via le point d'accès
public SPARQL de Cellar (le référentiel de l'Office des publications de l'UE).

IMPORTANT — limite à connaître :
Contrairement à BOFiP ou Judilibre, ce point d'accès ne fait PAS de
recherche plein texte dans le contenu des documents. SPARQL interroge des
MÉTADONNÉES (titre, date, numéro CELEX, type de document...), pas le texte
intégral. Concrètement :
    - rechercher par mots-clés du TITRE : ça fonctionne
    - rechercher un texte par son numéro CELEX : ça fonctionne bien
    - rechercher une expression precise dans le corps d'un règlement : NON,
      pas avec cette méthode (il faudrait la recherche EUR-Lex officielle,
      qui nécessite un compte ECAS et un protocole SOAP plus complexe)

Ce module est donc utile pour identifier et citer un texte ou un arrêt
(numéro CELEX, titre, date, lien officiel), pas pour une recherche plein
texte fine dans le contenu. Documentation du modèle de données (ontologie
CDM) : https://op.europa.eu/en/web/eu-vocabularies/cdm

Ce point d'accès n'a jamais été testé en conditions réelles dans cet
environnement (le domaine publications.europa.eu n'est pas accessible
depuis l'outil de développement) : si un appel échoue une fois déployé,
comparez le message d'erreur avec la documentation SPARQL de Cellar avant
de modifier ce fichier à l'aveugle.
"""

import httpx
from typing import Optional

SPARQL_ENDPOINT = "http://publications.europa.eu/webapi/rdf/sparql"

# Codes de langue Cellar (pas des codes ISO classiques)
LANG_URIS = {
    "fr": "http://publications.europa.eu/resource/authority/language/FRA",
    "en": "http://publications.europa.eu/resource/authority/language/ENG",
}


class EurlexAPIError(Exception):
    """Erreur lors d'un appel au point d'accès SPARQL de Cellar."""
    pass


async def _sparql_query(query: str) -> dict:
    headers = {"Accept": "application/sparql-results+json"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(SPARQL_ENDPOINT, params={"query": query}, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise EurlexAPIError(
                f"Erreur SPARQL Cellar ({e.response.status_code}) : {e.response.text[:400]}"
            )
        except httpx.RequestError as e:
            raise EurlexAPIError(f"Erreur réseau Cellar : {e}")


def _build_title_search_query(keyword: str, celex_prefix: str, limit: int, lang: str) -> str:
    """
    Construit une requête SPARQL cherchant `keyword` dans le titre des
    documents dont le numéro CELEX commence par `celex_prefix` :
        "3" = législation (règlements, directives, décisions...)
        "6" = jurisprudence (arrêts CJUE)
    """
    keyword_escaped = keyword.replace('"', '\\"')
    lang_uri = LANG_URIS.get(lang, LANG_URIS["fr"])
    return f"""
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT DISTINCT ?celex ?title ?date WHERE {{
  ?work cdm:resource_legal_id_celex ?celex .
  OPTIONAL {{ ?work cdm:work_date_document ?date . }}
  ?exp cdm:expression_belongs_to_work ?work .
  ?exp cdm:expression_uses_language <{lang_uri}> .
  ?exp cdm:expression_title ?title .
  FILTER(CONTAINS(LCASE(STR(?title)), LCASE("{keyword_escaped}")))
  FILTER(STRSTARTS(STR(?celex), "{celex_prefix}"))
}}
ORDER BY DESC(?date)
LIMIT {int(limit)}
"""


async def search_legislation_by_title(keyword: str, limit: int = 10, lang: str = "fr") -> dict:
    """Recherche des actes législatifs UE (règlements, directives...) par mot du titre."""
    query = _build_title_search_query(keyword, "3", limit, lang)
    return await _sparql_query(query)


async def search_case_law_by_title(keyword: str, limit: int = 10, lang: str = "fr") -> dict:
    """Recherche des arrêts CJUE par mot du titre (souvent les parties au litige)."""
    query = _build_title_search_query(keyword, "6", limit, lang)
    return await _sparql_query(query)


async def get_by_celex(celex: str, lang: str = "fr") -> dict:
    """Récupère titre, date et lien officiel d'un texte ou arrêt via son numéro CELEX."""
    celex_escaped = celex.replace('"', '\\"')
    lang_uri = LANG_URIS.get(lang, LANG_URIS["fr"])
    query = f"""
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT DISTINCT ?title ?date WHERE {{
  ?work cdm:resource_legal_id_celex "{celex_escaped}" .
  OPTIONAL {{ ?work cdm:work_date_document ?date . }}
  ?exp cdm:expression_belongs_to_work ?work .
  ?exp cdm:expression_uses_language <{lang_uri}> .
  ?exp cdm:expression_title ?title .
}}
LIMIT 5
"""
    return await _sparql_query(query)
