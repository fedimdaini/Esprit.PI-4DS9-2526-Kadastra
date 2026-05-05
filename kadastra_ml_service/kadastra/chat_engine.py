"""
KADASTRA — Chat Engine
Intent detection + conversational responses.

Supported intents:
  deal_search      — "meilleures affaires à Sousse sous 300k TND"
  market_analysis  — "analyse le marché de Tunis"
  portfolio_advice — "comment diversifier mon portefeuille?"
  general          — fallback (Groq LLM or template)
"""
import re
import math
import numpy as np
import pandas as pd
from typing import Optional


def _safe_int(val, default=0) -> int:
    """Convert any value (including NaN) to int safely."""
    if val is None:
        return default
    try:
        f = float(val)
        return default if (math.isnan(f) or math.isinf(f)) else int(f)
    except (ValueError, TypeError):
        return default


def _safe_float(val, default=0.0) -> float:
    """Convert any value (including NaN) to float safely."""
    if val is None:
        return default
    try:
        f = float(val)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (ValueError, TypeError):
        return default

# ── City / keyword tables ─────────────────────────────────────────────────
CITIES = [
    "tunis","ariana","sousse","sfax","nabeul","hammamet","bizerte",
    "monastir","gabes","kairouan","kasserine","lac","manouba","ben arous",
    "menzah","mutuelleville","carthage","sidi bou said","marsa","ennasr",
    "megrine","rades","hammam lif","soliman","zaghouan","mahdia","tozeur",
]

PROP_TYPES_MAP = {
    "appartement": ["Appartement a vendre","Appartement a louer"],
    "appart":      ["Appartement a vendre","Appartement a louer"],
    "maison":      ["Maison a vendre","Maison a louer"],
    "villa":       ["Villa a vendre","Villa a louer"],
    "studio":      ["Studio a vendre","Studio a louer"],
    "terrain":     ["Terrain a vendre"],
    "bureau":      ["Bureau a vendre","Bureau a louer"],
    "commercial":  ["Local commercial a vendre","Local commercial a louer"],
    "local":       ["Local commercial a vendre","Local commercial a louer"],
}

# Narrow to sale-only or rental-only when explicitly mentioned
_SALE_KWS   = ["vendre","vente","achat","acheter","acqui"]
_RENTAL_KWS = ["louer","location","locatif","locat"]

DEAL_KWS    = ["meilleur","meilleures","bon plan","bons plans","deal","affaire",
               "opportunit","moins cher","pas cher","annonce","cherche","trouve",
               "liste","liste moi","top","bonne affaire"]
MARKET_KWS  = ["marché","market","analyse de marché","statistique","stat",
               "prix moyen","tendance","evolution","croissance","rendement moyen"]
PORTFOLIO_KWS = ["portfolio","portefeuille","diversif","recommand","conseil",
                 "investir comment","que faire","quoi acheter"]


# ── Intent detection ──────────────────────────────────────────────────────
def detect_intent(text: str) -> dict:
    """Detect intent and extract parameters from free text."""
    t = text.lower().strip()
    params: dict = {}

    # Location
    for city in CITIES:
        if city in t:
            params["location"] = city.title()
            break

    # Budget
    bm = re.search(r'(\d[\d\s]*)\s*(?:tnd|dt|k(?:\s|$))', t)
    if bm:
        raw = bm.group(1).replace(" ", "")
        try:
            val = float(raw)
            if val < 2_000:       # "300k" → 300 000
                val *= 1_000
            params["budget"] = val
        except ValueError:
            pass

    # Property type — narrow to sale or rental if explicitly stated
    _is_sale   = any(kw in t for kw in _SALE_KWS)
    _is_rental = any(kw in t for kw in _RENTAL_KWS)
    for kw, types in PROP_TYPES_MAP.items():
        if kw in t:
            if _is_sale and not _is_rental:
                params["prop_types"] = [tp for tp in types if "vendre" in tp]
            elif _is_rental and not _is_sale:
                params["prop_types"] = [tp for tp in types if "louer" in tp]
            else:
                params["prop_types"] = types
            break
    # If no type keyword but sale/rental specified, store the filter
    if "prop_types" not in params:
        if _is_sale and not _is_rental:
            params["sale_only"] = True
        elif _is_rental and not _is_sale:
            params["rental_only"] = True

    # Top-N
    nm = re.search(r'top\s*(\d+)|(\d+)\s*(?:meilleures?|bons?\s*plans?|deals?|annonces?)', t)
    params["top_n"] = int(nm.group(1) or nm.group(2)) if nm else 5

    # Intent
    if any(kw in t for kw in DEAL_KWS):
        return {"intent": "deal_search", "params": params}
    elif any(kw in t for kw in MARKET_KWS):
        return {"intent": "market_analysis", "params": params}
    elif any(kw in t for kw in PORTFOLIO_KWS):
        return {"intent": "portfolio_advice", "params": params}
    else:
        return {"intent": "general", "params": params}


# ── Deal search ───────────────────────────────────────────────────────────
def search_deals(df: pd.DataFrame, params: dict) -> dict:
    """
    Score and return top-N listings that match params.
    Value score = how far below the type-median price/m² the listing is.
    """
    mask = df["price_numeric"].notna() & (df["price_numeric"] > 0)

    if params.get("location"):
        loc = params["location"].lower()
        mask &= df["Adresse"].fillna("").str.lower().str.contains(loc, na=False)

    if params.get("prop_types"):
        mask &= df["Type"].isin(params["prop_types"])
    elif params.get("rental_only"):
        mask &= df["Type"].fillna("").str.contains("louer", na=False)
    else:
        # Default: for-sale only
        mask &= df["Type"].fillna("").str.contains("vendre", na=False)

    if params.get("budget"):
        mask &= df["price_numeric"] <= params["budget"]

    subset = df[mask].copy()
    if subset.empty:
        return {
            "deals": [], "total_found": 0,
            "message": "Aucune annonce trouvée avec ces critères. Essayez d'élargir la zone ou le budget.",
        }

    # Price per m² — guard against zeros/NaN
    with np.errstate(divide='ignore', invalid='ignore'):
        subset["_ppm2"] = np.where(
            subset["surface_numeric"].fillna(0) > 0,
            subset["price_numeric"] / subset["surface_numeric"],
            np.nan
        )
    subset["_ppm2"] = pd.to_numeric(subset["_ppm2"], errors='coerce').fillna(0.0)

    # Value score: below-median price/m² = positive, above = negative
    type_med = subset.groupby("Type")["_ppm2"].transform("median").fillna(0.0)
    denom    = type_med.clip(lower=1.0) + 1e-9
    subset["_val"] = ((type_med - subset["_ppm2"]) / denom).fillna(0.0)

    # Bonus for amenities
    for feat in ["parking","ascenseur","balcon_terrasse","jardin","neuf"]:
        if feat in subset.columns:
            subset["_val"] += pd.to_numeric(subset[feat], errors='coerce').fillna(0) * 0.02

    subset["_val"] = subset["_val"].fillna(0.0)
    subset = subset.sort_values("_val", ascending=False, na_position='last')
    top_n = min(params.get("top_n", 5), 20)
    top   = subset.head(top_n)

    deals = []
    for _, row in top.iterrows():
        price   = _safe_float(row.get("price_numeric", 0))
        surface = _safe_float(row.get("surface_numeric", 0))
        ppm2    = price / surface if surface > 0 else 0
        deals.append({
            "titre":       str(row.get("titre", row.get("Type", "—")))[:80],
            "type":        str(row.get("Type", "")),
            "adresse":     str(row.get("Adresse", "")),
            "prix":        round(price),
            "surface":     round(surface, 1),
            "prix_m2":     round(ppm2),
            "value_score": round(_safe_float(row.get("_val", 0)) * 100, 1),
            "pieces":      _safe_int(row.get("pieces", 0)),
            "chambres":    _safe_int(row.get("chambres", 0)),
            "features":    [
                k.replace("_", " ")
                for k in ["parking","ascenseur","balcon_terrasse","jardin","piscine","neuf","meuble"]
                if _safe_int(row.get(k, 0)) == 1
            ],
        })

    return {
        "deals":       deals,
        "total_found": int(len(subset)),
        "top_n":       top_n,
        "filters":     {k: v for k, v in params.items() if v is not None},
    }


# ── Market analysis ───────────────────────────────────────────────────────
def analyze_market(df: pd.DataFrame, params: dict) -> dict:
    """Return market statistics for a given location/type from the dataset + constants."""
    from kadastra.core import TUNISIA_CONSTANTS as C

    location = params.get("location", "Tunisie")
    mask = df["price_numeric"].notna() & (df["price_numeric"] > 0)

    if params.get("location"):
        loc = params["location"].lower()
        mask &= df["Adresse"].fillna("").str.lower().str.contains(loc, na=False)

    if params.get("prop_types"):
        mask &= df["Type"].isin(params["prop_types"])
    elif params.get("sale_only"):
        mask &= df["Type"].fillna("").str.contains("vendre", na=False)
    elif params.get("rental_only"):
        mask &= df["Type"].fillna("").str.contains("louer", na=False)
    # else: analyse all listings for that location

    subset = df[mask].copy()
    if subset.empty:
        return {"error": f"Aucune donnée pour {location} dans la base."}

    subset["_ppm2"] = (
        subset["price_numeric"] / subset["surface_numeric"].replace(0, np.nan)
    )

    # Pick location-aware constants
    loc_l = location.lower()
    if "tunis" in loc_l:
        appr, yld = C["appreciation_tunis"], C["gross_yield_tunis"]
    elif "sousse" in loc_l:
        appr, yld = C["appreciation_sousse"], C["gross_yield_national"]
    elif "sfax" in loc_l:
        appr, yld = C["appreciation_sfax"], C["gross_yield_sfax"]
    elif "nabeul" in loc_l or "hammamet" in loc_l:
        appr, yld = C["appreciation_nabeul"], C["gross_yield_national"]
    else:
        appr, yld = C["appreciation_national"], C["gross_yield_national"]

    # Per-type breakdown
    type_stats = {}
    for t, grp in subset.groupby("Type"):
        ppm2_s = (grp["price_numeric"] / grp["surface_numeric"].replace(0, np.nan))
        type_stats[t] = {
            "count":        int(len(grp)),
            "median_price": int(grp["price_numeric"].median()),
            "median_ppm2":  int(ppm2_s.median()) if not ppm2_s.isna().all() else 0,
        }

    return {
        "location":              location,
        "total_listings":        int(len(subset)),
        "median_price":          int(subset["price_numeric"].median()),
        "mean_price":            int(subset["price_numeric"].mean()),
        "median_price_per_m2":   int(subset["_ppm2"].median()),
        "appreciation_rate_pct": round(appr * 100, 2),
        "gross_yield_pct":       round(yld  * 100, 2),
        "bct_tmm_pct":           round(C["bcт_tmm"] * 100, 2),
        "mortgage_rate_pct":     round(C["mortgage_rate_mid"] * 100, 2),
        "type_breakdown":        type_stats,
    }


# ── Portfolio advice ──────────────────────────────────────────────────────
def portfolio_advice(df: pd.DataFrame, params: dict, portfolio_advisor) -> dict:
    """Use C4 PortfolioDiversificationAdvisor to recommend diversification."""
    budget     = params.get("budget", 300_000)
    prop_types = params.get("prop_types", ["Appartement a vendre"])

    mask = df["price_numeric"].notna() & (df["price_numeric"] > 0)
    if params.get("location"):
        mask &= df["Adresse"].fillna("").str.lower().str.contains(
            params["location"].lower(), na=False)
    if prop_types:
        mask &= df["Type"].isin(prop_types)

    subset = df[mask]
    if not subset.empty:
        sample = subset.sample(1, random_state=42).iloc[0].to_dict()
    else:
        sample = {
            "Type": prop_types[0], "Adresse": params.get("location", "Tunis"),
            "price_numeric": budget * 0.7, "surface_numeric": 100,
        }

    recs = portfolio_advisor.recommend_diversification([sample], budget=budget)
    port = portfolio_advisor.analyze_current_portfolio([sample])

    return {
        "reference_asset":    {"type": sample.get("Type",""), "location": sample.get("Adresse","")},
        "portfolio_analysis": port,
        "recommendations":    recs.get("candidates", [])[:5],
        "budget":             budget,
    }


# ── Groq LLM helper ──────────────────────────────────────────────────────
def _try_groq(prompt: str, groq_key: str) -> Optional[str]:
    try:
        from groq import Groq
        client = Groq(api_key=groq_key)
        resp = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": (
                    "Tu es Kadastra, un expert en immobilier tunisien. "
                    "Réponds toujours en français, de façon concise et professionnelle. "
                    "Maximum 200 mots. Utilise des données chiffrées quand disponibles."
                )},
                {"role": "user", "content": prompt},
            ],
            max_tokens=400, temperature=0.35,
        )
        return resp.choices[0].message.content
    except Exception:
        return None


_HELP_TEXT = (
    "Je peux vous aider avec:\n"
    "• **Analyse d'un bien** — attachez une propriété avec le bouton +\n"
    "• **Meilleures affaires** — *\"Quels bons plans à Sousse sous 200 000 TND?\"*\n"
    "• **Analyse de marché** — *\"Analyse le marché immobilier de Tunis\"*\n"
    "• **Conseil portefeuille** — *\"Comment diversifier mon portefeuille?\"*"
)


# ── Main entry point ──────────────────────────────────────────────────────
def handle_chat(
    text: str,
    df: pd.DataFrame,
    portfolio_advisor,
    groq_key: str = None,
) -> dict:
    """
    Route a text query to the correct handler and return a structured response.
    """
    result = detect_intent(text)
    intent, params = result["intent"], result["params"]

    if intent == "deal_search":
        data = search_deals(df, params)
        llm_comment = None
        if groq_key and data.get("deals"):
            loc = params.get("location", "Tunisie")
            prompt = (
                f"L'utilisateur cherche des bons plans immobiliers à {loc}. "
                f"J'ai trouvé {data['total_found']} annonces correspondantes. "
                "Donne un commentaire de marché général en 2-3 phrases, "
                "avec les opportunités et risques clés."
            )
            llm_comment = _try_groq(prompt, groq_key)
        return {"type": "deal_search",  "data": data, "llm_comment": llm_comment,
                "intent": intent, "params": params}

    elif intent == "market_analysis":
        data = analyze_market(df, params)
        llm_comment = None
        if groq_key and "error" not in data:
            loc = params.get("location", "Tunisie")
            prompt = (
                f"Analyse du marché immobilier à {loc}: "
                f"prix médian {data.get('median_price',0):,} TND, "
                f"rendement locatif brut {data.get('gross_yield_pct',0)}%/an, "
                f"appréciation {data.get('appreciation_rate_pct',0)}%/an, "
                f"TMM BCT {data.get('bct_tmm_pct',0)}%. "
                "Donne une analyse de 3-4 phrases pour un investisseur tunisien."
            )
            llm_comment = _try_groq(prompt, groq_key)
        return {"type": "market_analysis", "data": data, "llm_comment": llm_comment,
                "intent": intent, "params": params}

    elif intent == "portfolio_advice":
        data = portfolio_advice(df, params, portfolio_advisor)
        return {"type": "portfolio_advice", "data": data,
                "intent": intent, "params": params}

    else:
        # General — try Groq, fall back to help text
        llm_response = _try_groq(
            f"Question immobilier Tunisie: {text}", groq_key
        ) if groq_key else None

        return {
            "type": "general",
            "data": {"message": llm_response or _HELP_TEXT},
            "intent": intent, "params": params,
        }
