"""
Client HTTP pour l'API Opendatasoft du BOFiP (doctrine fiscale, DGFiP).

Contrairement à Légifrance et Judilibre, cette API est un open data public
sans authentification (Licence Ouverte 2.0), publiée sur data.economie.gouv.fr.
"""

import httpx
from typing import Optional, Any
import re

ODS_BASE = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets"
DATASET_VIGUEUR = "bofip-vigueur"

DEFAULT_TIMEOUT = 30.0


class BofipAPIError(Exception):
    """Erreur lors d'un appel à l'API BOFiP."""
    pass


async def _request(path: str, params: Optional[dict] = None) -> dict:
    url = f"{ODS_BASE}/{path}"
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise BofipAPIError(
                f"Erreur API BOFiP ({e.response.status_code}) : {e.response.text[:300]}"
            )
        except httpx.RequestError as e:
            raise BofipAPIError(f"Erreur réseau : {e}")


async def search_vigueur(
    where: Optional[str] = None,
    select: Optional[str] = None,
    order_by: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    refine: Optional[list] = None,
) -> dict:
    """Recherche dans le dataset bofip-vigueur (doctrine en vigueur)."""
    params: dict[str, Any] = {"limit": min(limit, 100), "offset": offset}
    if where:
        params["where"] = where
    if select:
        params["select"] = select
    if order_by:
        params["order_by"] = order_by
    if refine:
        params["refine"] = refine
    return await _request(f"{DATASET_VIGUEUR}/records", params=params)


async def facets_vigueur(facet: str) -> dict:
    """Récupère les valeurs distinctes (et leur count) pour une facette (ex: 'serie')."""
    return await _request(f"{DATASET_VIGUEUR}/facets", params={"facet": facet})


def escape_ods_string(s: str) -> str:
    return s.replace('"', '\\"')


def build_search_clause(query: str) -> str:
    return f'search("{escape_ods_string(query)}")'


BOI_ID_PATTERN = re.compile(r'^BOI(?:-[A-Z0-9]+)+$', re.IGNORECASE)


def validate_boi_id(identifiant: str) -> str:
    identifiant = identifiant.strip().upper()
    if not BOI_ID_PATTERN.match(identifiant):
        raise ValueError(
            f"Identifiant BOI invalide : '{identifiant}'. "
            f"Format attendu : BOI-XX-YY[-ZZ...] (ex: BOI-CF-IOR-10-20)"
        )
    return identifiant
