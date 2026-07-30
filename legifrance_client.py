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
import re
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


# Identifiant technique d'un article dans Légifrance (ex: LEGIARTI000006419282).
_LEGIARTI_PATTERN = re.compile(r"^LEGIARTI\d+$")


def _extract_first_article_id(search_response: dict) -> Optional[str]:
    """Parcourt récursivement une réponse /search (fond CODE_DATE) et renvoie
    le premier identifiant d'article LEGIARTI rencontré.

    Le schéma JSON de /search varie selon les fonds et les versions de l'API :
    l'identifiant de l'article peut se trouver à la racine, dans un tableau
    'sections', 'articles', 'titles', etc. Plutôt que de coder en dur un chemin
    fragile, on parcourt l'arbre JSON et on retient le premier 'id' qui a la
    forme d'un LEGIARTI. C'est robuste aux évolutions de structure.
    """

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if (
                    key in ("id", "cid")
                    and isinstance(value, str)
                    and _LEGIARTI_PATTERN.match(value)
                ):
                    return value
                found = walk(value)
                if found:
                    return found
        elif isinstance(node, list):
            for item in node:
                found = walk(item)
                if found:
                    return found
        return None

    return walk(search_response)


async def consult_code_article(
    code_name: str,
    article_number: str,
    date: Optional[str] = None,
) -> dict:
    """Récupère un article de code par son numéro.

    Approche EN DEUX ÉTAPES, officiellement recommandée par Légifrance et
    identique à celle utilisée par les clients tiers stables (pylegifrance,
    LegalDataHunter) :
        1. POST /search (fond CODE_DATE) pour retrouver l'identifiant technique
           LEGIARTI de l'article, en filtrant sur le nom du code et le numéro
           d'article à la date de vigueur voulue ;
        2. POST /consult/getArticle avec cet identifiant pour récupérer le
           texte intégral.

    Cela remplace l'ancien appel direct à POST /consult/code, un endpoint
    "legacy" qui renvoie une erreur 500 côté serveur PISTE (confirmé via le
    Swagger PISTE, indépendamment de ce code).

    La valeur de retour a exactement la même forme qu'un appel getArticle
    (donc identique à consult_article) : format_legifrance_article dans
    formatters.py la met en forme sans modification.

    Args:
        code_name: nom exact du code tel que référencé par Légifrance
            (ex: "Code civil", "Code général des impôts", "Code du travail").
        article_number: numéro de l'article (ex: "1240", "L. 1234-1").
        date: date de vigueur souhaitée (YYYY-MM-DD), sinon date du jour.
    """
    from datetime import date as date_cls

    version_date = date or date_cls.today().isoformat()

    # ── Étape 1 : retrouver l'identifiant LEGIARTI de l'article ──────────────
    search_body = {
        "recherche": {
            "champs": [
                {
                    "typeChamp": "NUM_ARTICLE",
                    "criteres": [
                        {
                            "typeRecherche": "EXACTE",
                            "valeur": article_number,
                            "operateur": "ET",
                        }
                    ],
                    "operateur": "ET",
                }
            ],
            "filtres": [
                {"facette": "NOM_CODE", "valeurs": [code_name]},
                {"facette": "DATE_VERSION", "singleDate": version_date},
            ],
            "pageNumber": 1,
            "pageSize": 10,
            "operateur": "ET",
            "sort": "PERTINENCE",
            "typePagination": "ARTICLE",
        },
        "fond": "CODE_DATE",
    }
    search_response = await _post("/search", search_body)

    article_id = _extract_first_article_id(search_response)
    if not article_id:
        raise LegifranceAPIError(
            f"Aucun article « {article_number} » trouvé dans « {code_name} » "
            f"à la date {version_date}. Vérifiez le nom exact du code "
            f"(tel qu'il apparaît sur Légifrance) et le numéro d'article."
        )

    # ── Étape 2 : récupérer le texte intégral de l'article ───────────────────
    return await _post("/consult/getArticle", {"id": article_id})
