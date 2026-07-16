"""
Formatage des réponses JSON brutes des trois API en texte structuré,
lisible par un LLM.

Pour Légifrance et Judilibre, les schémas de réponse exacts peuvent varier
selon les versions de l'API. Ces fonctions extraient les champs les plus
courants de façon défensive (avec des valeurs par défaut) et retombent sur
un affichage JSON brut si la structure attendue n'est pas trouvée — pour
que l'outil reste utile même si un champ a changé de nom.
"""

import json


def _safe_get(d: dict, *keys, default=None):
    """Essaie plusieurs chemins de clés possibles et retourne le premier trouvé."""
    for key in keys:
        if key in d and d[key] is not None:
            return d[key]
    return default


# ─────────────────────────── BOFiP ───────────────────────────

def format_boi_summary(record: dict, include_extrait: bool = False) -> str:
    identifiant = record.get("identifiant_juridique", "N/A")
    titre = record.get("titre", "Sans titre")
    serie = record.get("serie", "?")
    division = record.get("division", "?")
    date_validite = record.get("debut_de_validite", "?")
    permalien = record.get("permalien", "")

    parts = [
        f"BOI {identifiant}",
        f"  Titre : {titre}",
        f"  Série : {serie} | Division : {division}",
        f"  Début de validité : {date_validite}",
    ]
    if permalien:
        parts.append(f"  Permalien : {permalien}")

    if include_extrait:
        contenu = record.get("contenu", "")
        if contenu:
            premier = next(
                (p.strip() for p in contenu.split("\n") if p.strip() and len(p.strip()) > 20),
                "",
            )
            if premier:
                extrait = premier[:300] + ("…" if len(premier) > 300 else "")
                parts.append(f"  Extrait : {extrait}")
    return "\n".join(parts)


def format_bofip_search_results(response: dict, page: int, page_size: int, tool_name: str) -> str:
    total = response.get("total_count", 0)
    results = response.get("results", [])
    if total == 0:
        return "Aucun résultat trouvé pour cette recherche dans le BOFiP."

    total_pages = (total + page_size - 1) // page_size
    header = f"Résultats BOFiP — page {page}/{total_pages} ({total} document(s) au total)\n{'=' * 60}\n"
    body = "\n\n".join(format_boi_summary(r, include_extrait=True) for r in results)
    footer = ""
    if page < total_pages:
        footer = f"\n\nPage suivante : {tool_name}(..., page={page + 1})"
    return header + body + footer


def format_boi_full(record: dict) -> str:
    identifiant = record.get("identifiant_juridique", "N/A")
    titre = record.get("titre", "Sans titre")
    permalien = record.get("permalien", "")
    contenu = record.get("contenu", "[Contenu non disponible]")
    header = (
        f"BOI : {identifiant}\n{'=' * 60}\n"
        f"Titre : {titre}\nPermalien : {permalien}\n{'=' * 60}\n\n"
    )
    return header + contenu


def format_facet_results(response: dict, facet_name: str) -> str:
    facets = response.get("facets", [])
    facet_data = next((f for f in facets if f.get("name") == facet_name), None)
    if not facet_data:
        return f"Aucune donnée pour la facette '{facet_name}'."
    values = facet_data.get("facets", [])
    lines = [f"Facette '{facet_name}' — {len(values)} valeur(s)\n{'=' * 40}"]
    for v in sorted(values, key=lambda x: -x.get("count", 0)):
        lines.append(f"  {v.get('name', '?'):<12} ({v.get('count', 0)} documents)")
    return "\n".join(lines)


# ─────────────────────────── Légifrance ───────────────────────────

def format_legifrance_search_results(response: dict, tool_name: str) -> str:
    results = _safe_get(response, "results", "resultats", default=[])
    total = _safe_get(response, "totalResultNumber", "total", default=len(results))

    if not results:
        return (
            "Aucun résultat Légifrance trouvé (ou structure de réponse inattendue).\n\n"
            "Réponse brute (pour diagnostic) :\n" + json.dumps(response, ensure_ascii=False, indent=2)[:1500]
        )

    lines = [f"Résultats Légifrance — {total} document(s) au total\n{'=' * 60}"]
    for r in results:
        titre = _safe_get(r, "titre", "title", default="Sans titre")
        nature = _safe_get(r, "nature", default="")
        text_id = _safe_get(r, "id", "textId", "titleId", default="")
        date = _safe_get(r, "dateDebut", "dateVersion", default="")
        lines.append(f"\n- {titre}")
        if nature:
            lines.append(f"  Nature : {nature}")
        if text_id:
            lines.append(f"  Identifiant : {text_id}")
        if date:
            lines.append(f"  Date : {date}")
    lines.append(f"\n\nPour lire un texte : utilisez son identifiant avec l'outil de consultation adapté.")
    return "\n".join(lines)


def format_legifrance_article(response: dict) -> str:
    article = _safe_get(response, "article", default=response)
    titre = _safe_get(article, "title", "titre", default="")
    texte = _safe_get(article, "texte", "content", "textHtml", default="")
    identifiant = _safe_get(article, "id", default="")

    if not texte:
        return (
            "Structure de réponse inattendue pour cet article.\n\n"
            "Réponse brute (pour diagnostic) :\n" + json.dumps(response, ensure_ascii=False, indent=2)[:2000]
        )

    header = f"Article Légifrance {identifiant}\n{'=' * 60}\n"
    if titre:
        header += f"Titre du texte : {titre}\n{'=' * 60}\n\n"
    return header + texte


# ─────────────────────────── Judilibre (Cour de cassation) ───────────────────────────

def format_judilibre_search_results(response: dict) -> str:
    results = _safe_get(response, "results", default=[])
    total = _safe_get(response, "total", default=len(results))

    if not results:
        return (
            "Aucune décision trouvée (ou structure de réponse inattendue).\n\n"
            "Réponse brute (pour diagnostic) :\n" + json.dumps(response, ensure_ascii=False, indent=2)[:1500]
        )

    lines = [f"Décisions Judilibre (Cour de cassation) — {total} résultat(s)\n{'=' * 60}"]
    for r in results:
        decision_id = _safe_get(r, "id", default="")
        numero = _safe_get(r, "number", "numero", default="")
        juridiction = _safe_get(r, "jurisdiction", default="")
        chambre = _safe_get(r, "chamber", "formation", default="")
        date = _safe_get(r, "decision_date", "date", default="")
        solution = _safe_get(r, "solution", default="")
        summary = _safe_get(r, "summary", "sommaire", default="")

        lines.append(f"\n- Décision {decision_id}")
        lines.append(f"  Juridiction : {juridiction} {chambre}".strip())
        if numero:
            lines.append(f"  N° de pourvoi : {numero}")
        if date:
            lines.append(f"  Date : {date}")
        if solution:
            lines.append(f"  Solution : {solution}")
        if summary:
            extrait = summary[:250] + ("…" if len(summary) > 250 else "")
            lines.append(f"  Résumé : {extrait}")
    return "\n".join(lines)


def format_judilibre_decision(response: dict) -> str:
    decision_id = _safe_get(response, "id", default="")
    texte = _safe_get(response, "text", "texteIntegral", default="")
    numero = _safe_get(response, "number", "numero", default="")
    date = _safe_get(response, "decision_date", "date", default="")

    if not texte:
        return (
            "Structure de réponse inattendue pour cette décision.\n\n"
            "Réponse brute (pour diagnostic) :\n" + json.dumps(response, ensure_ascii=False, indent=2)[:2000]
        )

    header = f"Décision Judilibre {decision_id}\n{'=' * 60}\n"
    if numero:
        header += f"N° de pourvoi : {numero}\n"
    if date:
        header += f"Date : {date}\n"
    header += f"{'=' * 60}\n\n"
    return header + texte
