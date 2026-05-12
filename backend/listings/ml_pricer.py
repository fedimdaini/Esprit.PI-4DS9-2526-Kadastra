"""
ml_pricer.py  —  Kadastra listing-level price analyser
=======================================================
Wraps 6 trained models (LightGBM / RandomForest) that compare a listing's
listed price against a market-estimated price and return a human-readable label.

Model files live in  listings/pricer_models/  and are volume-mounted so no
Docker rebuild is needed after dropping new .pkl files.

Each .pkl is a joblib-serialised dict with keys:
    model     — fitted estimator
    features  — list[str] of column names used at training time
    y_low     — float, minimum plausible predicted price (sanity bound)
    y_high    — float, maximum plausible predicted price (sanity bound)
    mape      — float (optional), model MAPE on hold-out set (default 0.25)

Models were trained on log-transformed prices, so raw predictions < 25 need
np.expm1() to convert back to TND.
"""

import os
import re
import threading
import logging
import numpy as np

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
_MODEL_DIR = os.path.join(os.path.dirname(__file__), "pricer_models")

_MODEL_FILES = {
    "appt_vente":     "model2_lgbm_appt_vente.pkl",
    "appt_location":  "model2_lgbm_appt_location.pkl",
    "local_vente":    "model3_rf_local_vente.pkl",
    "maison_vente":   "model2_lgbm_maison_vente.pkl",
    "terrain_vente":  "model2_lgbm_terrain_vente.pkl",
    "maison_location":"model2_lgbm_maison_location.pkl",
}

# ── Type → model key ──────────────────────────────────────────────────────────
def _type_to_model_key(type_str: str):
    t = (type_str or "").lower()
    if "appartement" in t and "vendre" in t:  return "appt_vente"
    if "appartement" in t and "louer"  in t:  return "appt_location"
    if "studio"      in t and "vendre" in t:  return "appt_vente"
    if "studio"      in t and "louer"  in t:  return "appt_location"
    if "maison"      in t and "vendre" in t:  return "maison_vente"
    if "maison"      in t and "louer"  in t:  return "maison_location"
    if "villa"       in t and "vendre" in t:  return "maison_vente"
    if "villa"       in t and "louer"  in t:  return "maison_location"
    if "terrain"     in t:                    return "terrain_vente"
    if "local"       in t and "vendre" in t:  return "local_vente"
    if "bureau"      in t and "vendre" in t:  return "local_vente"
    return None

# ── Lazy singleton ─────────────────────────────────────────────────────────────
_models: dict = {}
_loaded = False
_lock   = threading.Lock()

def _ensure_loaded():
    global _loaded
    if _loaded:
        return
    with _lock:
        if _loaded:
            return
        try:
            import joblib
        except ImportError:
            logger.warning("joblib not available — price analysis disabled")
            _loaded = True
            return
        try:
            import lightgbm  # noqa: F401  — ensures lgbm models deserialise correctly
        except ImportError:
            logger.warning("lightgbm not installed — LightGBM models may fail to load")

        for key, fname in _MODEL_FILES.items():
            path = os.path.join(_MODEL_DIR, fname)
            if not os.path.exists(path):
                logger.warning("Pricer model not found: %s", path)
                continue
            try:
                _models[key] = joblib.load(path)
                logger.info("Loaded pricer model: %s", key)
            except Exception as exc:
                logger.warning("Failed to load %s: %s", key, exc)
        _loaded = True

# ── Data-quality helpers ───────────────────────────────────────────────────────
def _parse_price(prix_text) -> float | None:
    """'325\xa0000 TND' → 325000.0   |  None if not parseable."""
    if not prix_text:
        return None
    s = str(prix_text)
    # strip non-breaking spaces, thin spaces, etc.
    s = s.replace("\xa0", "").replace(" ", "").replace(" ", "").replace(" ", "")
    s = re.sub(r"(?i)(tnd|dt|eur|€|dinar)", "", s)
    nums = re.findall(r"\d[\d,.]*", s)
    if not nums:
        return None
    n = nums[0]
    if "," in n and "." in n:
        n = n.replace(".", "").replace(",", ".")
    elif "," in n:
        parts = n.split(",")
        n = n.replace(",", "") if len(parts[-1]) > 2 else n.replace(",", ".")
    elif "." in n:
        parts = n.split(".")
        if len(parts[-1]) != 2:
            n = n.replace(".", "")
    try:
        v = float(n)
        return v if v > 0 else None
    except ValueError:
        return None


def _parse_surface(surface_text) -> float:
    """'120²' | '120 m²' → 120.0   |  0 if N/A."""
    if not surface_text or str(surface_text).strip() in ("N/A", "", "None"):
        return 0.0
    cleaned = re.sub(r"[m²²\s²]+", "", str(surface_text))
    nums = re.findall(r"\d+", cleaned)
    return float(nums[0]) if nums else 0.0


def _parse_int(text) -> int:
    """'3 chambres' | 'N/A' → 3 | 0."""
    if not text or str(text).strip() in ("N/A", "", "None"):
        return 0
    nums = re.findall(r"\d+", str(text))
    return int(nums[0]) if nums else 0


# ── Label thresholds ───────────────────────────────────────────────────────────
_DEFAULT_MAPE = 0.25   # 25% tolerance when model doesn't store its own MAPE

_LABELS_FR = {
    "great":     "Bonne affaire",
    "fair":      "Prix du marché",
    "high":      "Prix élevé",
    "very_high": "Très surévalué",
}

_MESSAGES = {
    "great":
        "Ce bien est proposé en dessous du prix du marché. C'est une opportunité à saisir.",
    "fair":
        "Ce bien est proposé à un prix cohérent avec le marché. La valeur est équilibrée.",
    "high":
        "Ce bien est proposé au-dessus du prix du marché. Une négociation est envisageable.",
    "very_high":
        ("Le prix de ce bien est significativement au-dessus du marché. "
         "Nous vous recommandons de comparer avec d'autres annonces similaires "
         "avant de vous engager."),
}

# Pill CSS colours per label  (background, text, border)
LABEL_COLORS = {
    "great":     ("#d1fae5", "#065f46", "#6ee7b7"),
    "fair":      ("#eff6ff", "#1d4ed8", "#bfdbfe"),
    "high":      ("#fff7ed", "#c2410c", "#fed7aa"),
    "very_high": ("#fff1f2", "#be123c", "#fecdd3"),
}


def _classify(listed: float, predicted: float, mape: float):
    """Returns (label, delta_pct_int)."""
    delta = (listed - predicted) / predicted
    if delta < -mape:
        return "great",     round(delta * 100)
    if delta <=  mape:
        return "fair",      round(delta * 100)
    if delta <= 2 * mape:
        return "high",      round(delta * 100)
    return "very_high", round(delta * 100)


# ── Public API ────────────────────────────────────────────────────────────────
def analyze_price(listing: dict) -> dict | None:
    """
    Given a serialised listing dict (as returned by DataSerializer), return a
    price_analysis dict or None if the model can't score this listing.

    Return shape:
        {
            label           : 'great' | 'fair' | 'high' | 'very_high',
            label_fr        : str,
            predicted_price : int,
            delta_pct       : int,      # positive = over market
            message         : str,
        }
    """
    _ensure_loaded()

    prop_type = listing.get("type") or listing.get("Type") or ""
    key = _type_to_model_key(prop_type)
    if not key or key not in _models:
        return None

    m_dict   = _models[key]
    model    = m_dict.get("model")
    features = m_dict.get("features", [])
    y_low    = float(m_dict.get("y_low",  0))
    y_high   = float(m_dict.get("y_high",  float("inf")))
    mape     = float(m_dict.get("mape",   _DEFAULT_MAPE))

    # Require a real listed price to compare against
    listed = listing.get("price_numeric")
    if not listed:
        listed = _parse_price(listing.get("prix") or "")
    if not listed or listed <= 0:
        return None

    surface  = _parse_surface(listing.get("surface"))
    chambres = _parse_int(listing.get("chambres"))
    pieces   = _parse_int(listing.get("pieces"))
    sdb      = _parse_int(listing.get("salles_de_bain"))

    # log_surface — matches the training feature used by all models
    log_surface = float(np.log(surface + 1)) if surface > 0 else 0.0

    # Build a feature row covering all common aliases; filter to model.features below.
    # Features not available from the listing query default to 0.
    row = {
        # Core numeric — both spellings the models use
        "surface":          surface,
        "surface_numeric":  surface,
        "log_surface":      log_surface,
        "pieces":           pieces,
        "chambres":         chambres,
        "sallesdebain":     sdb,       # friend's models use this spelling (no underscores)
        "salles_de_bain":   sdb,
        "nb_pieces":        pieces or chambres,
        "nb_chambres":      chambres,
        "nb_sdb":           sdb,
        # Features that require geocoding / enrichment — unknown → median proxy (0)
        "floor_number":     0,
        "sn_level":         0,
        "has_outdoor":      0,
        "has_coords":       0,
        "gouvernorat_cat":  0,
        "dist_tunis_centre": 0,
        "dist_to_coast":    0,
        "dist_lac":         0,
        "dist_la_marsa":    0,
        "premium_score":    0,
        # Binary amenities — not exposed at list-endpoint level; default neutral
        "neuf": 0, "parking": 0, "ascenseur": 0, "meuble": 0,
        "balcon_terrasse": 0, "climatisation": 0, "chauffage": 0,
        "jardin": 0, "piscine": 0,
    }

    try:
        import pandas as pd

        feat_row = {f: row.get(f, 0) for f in features}
        df       = pd.DataFrame([feat_row])

        raw = float(model.predict(df)[0])

        # All models output log-transformed prices (raw << 25 → expm1 needed)
        is_log_scale = raw < 25
        if is_log_scale:
            # Sanity-check raw prediction against log-scale bounds before converting
            if y_low and y_high and not (y_low * 0.8 <= raw <= y_high * 1.2):
                return None
            predicted = float(np.expm1(raw))
        else:
            predicted = raw
            # Sanity-check converted price
            if y_low and y_high:
                y_low_tnd  = float(np.expm1(y_low))
                y_high_tnd = float(np.expm1(y_high))
                if not (y_low_tnd * 0.5 <= predicted <= y_high_tnd * 3):
                    return None

        # Reject implausible predictions — bounds differ for sale vs rental
        is_rental_model = key.endswith("_location")
        min_price = 100 if is_rental_model else 10_000       # 100 TND/mo vs 10 k TND
        max_price = 50_000 if is_rental_model else 50_000_000
        if predicted < min_price or predicted > max_price:
            return None

        label, delta_pct = _classify(listed, predicted, mape)

        return {
            "label":           label,
            "label_fr":        _LABELS_FR[label],
            "predicted_price": round(predicted),
            "delta_pct":       delta_pct,
            "message":         _MESSAGES[label],
        }

    except Exception as exc:
        logger.warning("Price analysis failed: %s", exc)
        return None
