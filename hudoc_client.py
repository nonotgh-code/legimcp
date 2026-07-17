"""
Client pour HUDOC, la base de jurisprudence publique de la Cour européenne
des droits de l'homme (CEDH — Conseil de l'Europe, distinct de l'UE).

Ce point d'accès est plus proche d'une vraie recherche plein texte que
celui d'EUR-Lex/Cellar, et ne nécessite pas d'authentification. Il n'est
cependant pas officiellement documenté comme une API publique stable (il
sert avant tout l'interface web hudoc.echr.coe.int elle-même) : son
comportement exact n'a pas pu être vérifié en conditions réelles dans cet
environnement. Si le format de réponse a changé, `formatters.py` affichera
le JSON brut pour faciliter le diagnostic plutôt que d'échouer silencieusement.
"""

import httpx
from typing import Optional

HUDOC_SEARCH_URL = "https://hudoc.echr.coe.int/app/query/results"


class HudocAPIError(Exception):
    """Erreur lors d'un appel à HUDOC."""
    pass


async def search_decisions(
    query: str,
    start: int = 0,
    length: int = 10,
) -> dict:
    """
    Recherche plein texte dans les décisions et arrêts CEDH.

    Args:
        query: termes de recherche.
        start: index de départ (pagination, base 0).
        length: nombre de résultats à retourner.
    """
    params = {
        "query": f'contentsitename=ECHR AND (FullText="{query}")',
        "select": "itemid,docname,appno,doctype,importance,languageisocode,respondent,decisiondate,kpdate",
        "sort": "",
        "start": start,
        "length": length,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(HUDOC_SEARCH_URL, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise HudocAPIError(f"Erreur HUDOC ({e.response.status_code}) : {e.response.text[:400]}")
        except httpx.RequestError as e:
            raise HudocAPIError(f"Erreur réseau HUDOC : {e}")
