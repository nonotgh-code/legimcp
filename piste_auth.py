"""
Authentification PISTE (portail des API juridiques de l'État français).

PISTE utilise OAuth2 en mode "client_credentials" : on échange un
PISTE_CLIENT_ID + PISTE_CLIENT_SECRET contre un jeton d'accès temporaire
(généralement valable 1h), qui doit être joint à chaque appel API sous
forme d'en-tête "Authorization: Bearer <token>".

Ce module met le jeton en cache en mémoire et ne le renouvelle que
lorsqu'il est expiré (ou proche de l'être), pour éviter une authentification
à chaque appel d'outil.

IMPORTANT : PISTE distingue un environnement "sandbox" (bac à sable, pour
tester) et un environnement de production. Les URLs, ainsi que les clés
d'application, diffèrent entre les deux. Vérifiez sur votre espace
PISTE (developer.aife.economie.gouv.fr) laquelle correspond à vos clés.
"""

import os
import time
import httpx

TOKEN_URL = os.environ.get(
    "PISTE_TOKEN_URL",
    "https://oauth.piste.gouv.fr/api/oauth/token",
)


class PisteAuthError(Exception):
    """Erreur lors de l'authentification auprès de PISTE."""
    pass


_token_cache: dict = {"access_token": None, "expires_at": 0.0}


async def get_access_token() -> str:
    """Retourne un jeton d'accès PISTE valide, en le renouvelant si besoin."""
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 30:
        return _token_cache["access_token"]

    client_id = os.environ.get("PISTE_CLIENT_ID")
    client_secret = os.environ.get("PISTE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise PisteAuthError(
            "Variables d'environnement PISTE_CLIENT_ID et PISTE_CLIENT_SECRET "
            "manquantes. Définissez-les localement (fichier .env) ou dans les "
            "'Environment Variables' de votre service Render."
        )

    # PISTE attend l'authentification du client via HTTP Basic Auth (standard
    # OAuth2), pas via client_id/client_secret dans le corps de la requête.
    data = {
        "grant_type": "client_credentials",
        "scope": "openid",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                auth=(client_id, client_secret),
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise PisteAuthError(
                f"Échec d'authentification PISTE ({e.response.status_code}) : "
                f"{e.response.text[:300]}"
            )
        except httpx.RequestError as e:
            raise PisteAuthError(f"Erreur réseau lors de l'authentification PISTE : {e}")

    payload = resp.json()
    access_token = payload.get("access_token")
    expires_in = payload.get("expires_in", 3600)
    if not access_token:
        raise PisteAuthError(f"Réponse PISTE inattendue (pas de access_token) : {payload}")

    _token_cache["access_token"] = access_token
    _token_cache["expires_at"] = now + float(expires_in)
    return access_token
