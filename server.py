"""
Serveur MCP "legimcp" — accès unifié à Légifrance, Judilibre (Cour de
cassation) et BOFiP (doctrine fiscale) depuis Claude.

Sources :
    - Légifrance (PISTE) : lois, codes, jurisprudence, conventions collectives
    - Judilibre (PISTE)  : décisions de la Cour de cassation et des cours d'appel
    - BOFiP (open data DGFiP, sans authentification) : doctrine fiscale

Variables d'environnement requises :
    PISTE_CLIENT_ID       — identifiant de votre application PISTE
    PISTE_CLIENT_SECRET   — secret de votre application PISTE

Variables optionnelles (voir .env.example) :
    PISTE_TOKEN_URL, LEGIFRANCE_BASE_URL, JUDILIBRE_BASE_URL
"""

import os
from typing import Optional
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()  # charge un fichier .env local si présent ; ignoré si absent

import legifrance_client as legifrance
import judilibre_client as judilibre
import bofip_client as bofip
import formatters as fmt

mcp = FastMCP(
    name="legimcp",
    instructions=(
        "Serveur MCP donnant accès à trois sources juridiques françaises : "
        "Légifrance (lois, codes, jurisprudence, conventions collectives), "
        "Judilibre (décisions de la Cour de cassation et cours d'appel), "
        "et le BOFiP (doctrine fiscale de la DGFiP)."
    ),
)


# ═══════════════════════════ LÉGIFRANCE ═══════════════════════════

@mcp.tool()
async def rechercher_legifrance(
    query: str,
    fond: str = "LODA_DATE",
    page: int = 1,
    page_size: int = 10,
) -> str:
    """
    Recherche générale dans un fonds documentaire Légifrance.

    Args:
        query: termes de recherche.
        fond: fonds documentaire à interroger. Valeurs courantes :
            "LODA_DATE" (lois, décrets, arrêtés — défaut), "CODE_DATE"
            (articles de codes), "JORF" (Journal officiel), "JURI"
            (jurisprudence judiciaire), "CETAT" (jurisprudence
            administrative), "KALI" (conventions collectives).
        page: numéro de page (défaut 1).
        page_size: résultats par page (défaut 10, max 50).

    Exemples:
        - rechercher_legifrance("licenciement pour faute grave", fond="CODE_DATE")
        - rechercher_legifrance("RGPD traitement de données", fond="LODA_DATE")
    """
    page_size = max(1, min(page_size, 50))
    try:
        response = await legifrance.search(query, fond=fond, page_number=page, page_size=page_size)
        return fmt.format_legifrance_search_results(response, "rechercher_legifrance")
    except legifrance.LegifranceAPIError as e:
        return f"Erreur : {e}"


@mcp.tool()
async def get_article_legifrance(article_id: str) -> str:
    """
    Récupère le texte intégral d'un article via son identifiant Légifrance.

    Args:
        article_id: identifiant technique de l'article (ex: "LEGIARTI000006302199").
            Ces identifiants s'obtiennent via rechercher_legifrance() ou
            get_article_code().
    """
    try:
        response = await legifrance.consult_article(article_id)
        return fmt.format_legifrance_article(response)
    except legifrance.LegifranceAPIError as e:
        return f"Erreur : {e}"


@mcp.tool()
async def get_article_code(
    code_name: str,
    numero_article: str,
    date: Optional[str] = None,
) -> str:
    """
    Récupère un article de code par son numéro, sans passer par une recherche.

    Args:
        code_name: nom exact du code (ex: "Code civil", "Code du travail",
            "Code général des impôts", "Code pénal").
        numero_article: numéro de l'article (ex: "1240", "L. 1234-1").
        date: date de vigueur souhaitée (YYYY-MM-DD), sinon version actuelle.

    Exemple:
        - get_article_code("Code civil", "1240")
    """
    try:
        response = await legifrance.consult_code_article(code_name, numero_article, date=date)
        return fmt.format_legifrance_article(response)
    except legifrance.LegifranceAPIError as e:
        return f"Erreur : {e}"


# ═══════════════════════════ JUDILIBRE (COUR DE CASSATION) ═══════════════════════════

@mcp.tool()
async def rechercher_jurisprudence_cassation(
    query: str,
    page: int = 0,
    page_size: int = 10,
    juridiction: Optional[str] = None,
) -> str:
    """
    Recherche plein texte dans les décisions de la Cour de cassation
    (et des cours d'appel) via l'API Judilibre.

    Args:
        query: termes de recherche.
        page: numéro de page, base 0 (défaut 0).
        page_size: résultats par page (défaut 10, max 50).
        juridiction: filtre optionnel — "cc" (Cour de cassation),
            "ca" (cours d'appel), "tj" (tribunaux judiciaires).

    Exemples:
        - rechercher_jurisprudence_cassation("abus de droit fiscal")
        - rechercher_jurisprudence_cassation("clause de non-concurrence", juridiction="cc")
    """
    page_size = max(1, min(page_size, 50))
    try:
        response = await judilibre.search_decisions(
            query, page=page, page_size=page_size, jurisdiction=juridiction
        )
        return fmt.format_judilibre_search_results(response)
    except judilibre.JudilibreAPIError as e:
        return f"Erreur : {e}"


@mcp.tool()
async def get_decision_cassation(decision_id: str) -> str:
    """
    Récupère le texte intégral d'une décision via son identifiant Judilibre.

    Args:
        decision_id: identifiant Judilibre de la décision (obtenu via
            rechercher_jurisprudence_cassation()).
    """
    try:
        response = await judilibre.get_decision(decision_id)
        return fmt.format_judilibre_decision(response)
    except judilibre.JudilibreAPIError as e:
        return f"Erreur : {e}"


# ═══════════════════════════ BOFIP (DOCTRINE FISCALE) ═══════════════════════════

@mcp.tool()
async def rechercher_bofip(query: str, page: int = 1, page_size: int = 10) -> str:
    """
    Recherche plein texte dans le BOFiP (doctrine fiscale en vigueur).

    Args:
        query: termes de recherche (ex: "vérification de comptabilité",
            "régime mère-fille", "abus de droit fiscal").
        page: numéro de page (défaut 1).
        page_size: résultats par page (défaut 10, max 100).
    """
    if page < 1:
        return "Erreur : 'page' doit être >= 1."
    page_size = max(1, min(page_size, 100))
    try:
        response = await bofip.search_vigueur(
            where=bofip.build_search_clause(query),
            select="identifiant_juridique,titre,serie,division,debut_de_validite,permalien,contenu",
            limit=page_size,
            offset=(page - 1) * page_size,
            order_by="debut_de_validite DESC",
        )
        return fmt.format_bofip_search_results(response, page, page_size, "rechercher_bofip")
    except bofip.BofipAPIError as e:
        return f"Erreur : {e}"


@mcp.tool()
async def get_boi(identifiant_juridique: str) -> str:
    """
    Récupère le contenu intégral d'un BOI par son identifiant.

    Args:
        identifiant_juridique: identifiant au format BOI-XX-YY[-ZZ...]
            (ex: "BOI-CF-IOR-10").
    """
    try:
        identifiant = bofip.validate_boi_id(identifiant_juridique)
    except ValueError as e:
        return f"Erreur : {e}"

    try:
        response = await bofip.search_vigueur(
            where=f'identifiant_juridique="{identifiant}"',
            limit=1,
        )
        results = response.get("results", [])
        if not results:
            return f"Aucun BOI trouvé avec l'identifiant '{identifiant}'."
        return fmt.format_boi_full(results[0])
    except bofip.BofipAPIError as e:
        return f"Erreur : {e}"


@mcp.tool()
async def explorer_bofip(serie: Optional[str] = None) -> str:
    """
    Liste les séries du BOFiP, ou les BOI d'une série donnée.

    Args:
        serie: si absent, liste toutes les séries (CF, IR, IS, TVA...).
            Si fourni, liste les BOI de cette série (ex: "CF").
    """
    try:
        if not serie:
            response = await bofip.facets_vigueur("serie")
            return fmt.format_facet_results(response, "serie")

        serie_upper = serie.upper()
        response = await bofip.search_vigueur(
            refine=[f"serie:{serie_upper}"],
            select="identifiant_juridique,titre,debut_de_validite",
            limit=50,
            order_by="identifiant_juridique",
        )
        results = response.get("results", [])
        total = response.get("total_count", 0)
        if not results:
            return f"Aucun BOI trouvé pour la série '{serie_upper}'."
        lines = [f"BOI dans la série {serie_upper} — {total} document(s)\n{'=' * 50}"]
        for r in results:
            lines.append(f"\n{r.get('identifiant_juridique', '?')} — {r.get('titre', '')}")
        return "\n".join(lines)
    except bofip.BofipAPIError as e:
        return f"Erreur : {e}"


# ═══════════════════════════ POINT D'ENTRÉE ═══════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="http", host="0.0.0.0", port=port)
