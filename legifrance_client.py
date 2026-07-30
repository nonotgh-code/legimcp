"""
Client HTTP pour l'API Légifrance (portail PISTE de la DILA).

Documentation officielle et bac à sable de test :
https://developer.aife.economie.gouv.fr (rubrique "Légifrance")

ATTENTION : les noms exacts de champs JSON de cette API évoluent parfois
et sont assez riches (elle date d'avant les standards REST modernes).
Les fonctions ci-dessous couvrent les usages les plus courants avec une
structure de requête standard, mais si un appel échoue avec une erreur
400, comparez le corps de la requête avec la documentation Swagger
disponible sur votre espace PISTE avant de modifier ce fichier.
"""

import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger("legimcp")

from piste_auth import get_access_token, PisteAuthError

# Production par défaut. Pour tester sur le bac à sable PISTE, définissez
# LEGIFRANCE_BASE_URL=https://sandbox-api.piste.gouv.fr/dila/legifrance/lf-engine-app
LEGIFRANCE_BASE = os.environ.get(
    "LEGIFRANCE_BASE_URL",
    "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app",
)


class LegifranceAPIError(Exception):
    """Erreur lors d'un appel à l'API Légifrance."""
    pass


async def _post(path: str, json_body: dict) -> dict:
    try:
        token = await get_access_token()
    except PisteAuthError as e:
        raise LegifranceAPIError(str(e))

    url = f"{LEGIFRANCE_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    logger.warning("DEBUG legimcp -> POST %s body=%s", url, json_body)
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(url, json=json_body, headers=headers)
            logger.warning(
                "DEBUG legimcp <- status=%s body=%s", resp.status_code, resp.text
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise LegifranceAPIError(
                f"Erreur API Légifrance ({e.response.status_code}) sur {path} : "
                f"{e.response.text[:400]}"
            )
        except httpx.RequestError as e:
            raise LegifranceAPIError(f"Erreur réseau Légifrance : {e}")


async def search(
    query: str,
    fond: str = "LODA_DATE",
    page_number: int = 1,
    page_size: int = 10,
) -> dict:
    """
    Recherche générale dans un fonds documentaire Légifrance.

    Fonds courants :
        LODA_DATE  — lois, ordonnances, décrets, arrêtés
        CODE_DATE  — articles de codes en vigueur
        JORF       — Journal officiel
        JURI       — jurisprudence judiciaire (Cour de cassation, cours d'appel)
        CETAT      — jurisprudence administrative (Conseil d'État)
        KALI       — conventions collectives
        CNIL       — délibérations CNIL
    """
    body = {
        "recherche": {
            "champs": [
                {
                    "typeChamp": "ALL",
                    "criteres": [
                        {"typeRecherche": "UN_DES_MOTS", "valeur": query, "operateur": "ET"}
                    ],
                    "operateur": "ET",
                }
            ],
            "pageNumber": page_number,
            "pageSize": page_size,
            "sort": "PERTINENCE",
            "typePagination": "DEFAUT",
        },
        "fond": fond,
    }
    return await _post("/search", body)


async def consult_article(article_id: str) -> dict:
    """Récupère le texte intégral d'un article via son identifiant Légifrance
    (ex: 'LEGIARTI000006302199')."""
    return await _post("/consult/getArticle", {"id": article_id})


async def consult_code_article(
    code_name: str,
    article_number: str,
    date: Optional[str] = None,
) -> dict:
    """Récupère un article de code par son numéro.

    Args:
        code_name: nom exact du code tel que référencé par Légifrance
            (ex: "Code civil", "Code général des impôts", "Code du travail").
        article_number: numéro de l'article (ex: "1240", "L. 1234-1").
        date: date de vigueur souhaitée (YYYY-MM-DD), sinon version en vigueur.
    """
    body = {"codeName": code_name, "num": article_number}
    if date:
        body["date"] = date
    return await _post("/consult/code", body)
