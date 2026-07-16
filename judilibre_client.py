"""
Client HTTP pour l'API Judilibre (jurisprudence de la Cour de cassation,
des cours d'appel et de certains tribunaux judiciaires), également
disponible via le portail PISTE.

Documentation : https://developer.aife.economie.gouv.fr (rubrique "Judilibre")

Comme pour legifrance_client.py, vérifiez les noms exacts de paramètres
dans le Swagger de votre espace PISTE si un appel échoue : cette API est
plus jeune que Légifrance mais évolue encore.
"""

import os
import httpx
from typing import Optional

from piste_auth import get_access_token, PisteAuthError

JUDILIBRE_BASE = os.environ.get(
    "JUDILIBRE_BASE_URL",
    "https://api.piste.gouv.fr/cassation/judilibre/v1.0",
)


class JudilibreAPIError(Exception):
    """Erreur lors d'un appel à l'API Judilibre."""
    pass


async def _get(path: str, params: dict) -> dict:
    try:
        token = await get_access_token()
    except PisteAuthError as e:
        raise JudilibreAPIError(str(e))

    url = f"{JUDILIBRE_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        # Certaines API PISTE demandent aussi la clé d'application en en-tête.
        "KeyId": os.environ.get("PISTE_CLIENT_ID", ""),
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise JudilibreAPIError(
                f"Erreur API Judilibre ({e.response.status_code}) sur {path} : "
                f"{e.response.text[:400]}"
            )
        except httpx.RequestError as e:
            raise JudilibreAPIError(f"Erreur réseau Judilibre : {e}")


async def search_decisions(
    query: str,
    page: int = 0,
    page_size: int = 10,
    jurisdiction: Optional[str] = None,
) -> dict:
    """Recherche plein texte dans les décisions Judilibre.

    Args:
        query: termes de recherche.
        page: numéro de page, base 0.
        page_size: nombre de résultats par page.
        jurisdiction: filtre optionnel ("cc" = Cour de cassation,
            "ca" = cours d'appel, "tj" = tribunaux judiciaires).
    """
    params: dict = {"query": query, "page": page, "page_size": page_size}
    if jurisdiction:
        params["jurisdiction"] = jurisdiction
    return await _get("/search", params)


async def get_decision(decision_id: str) -> dict:
    """Récupère le texte intégral d'une décision par son identifiant Judilibre."""
    return await _get("/decision", {"id": decision_id})
