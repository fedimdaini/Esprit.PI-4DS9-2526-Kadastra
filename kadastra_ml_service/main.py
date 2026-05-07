"""
KADASTRA ML Service — FastAPI
Serves the InvestmentScenarioGenerator via HTTP.
Models are loaded once at startup and cached in memory.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import os, time
from apscheduler.schedulers.background import BackgroundScheduler

_scheduler = BackgroundScheduler()

app = FastAPI(
    title="Kadastra ML Service",
    description="Tunisian Real Estate Investment AI Agent — API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Load models at startup ────────────────────────────────────────────────
_generator = None

@app.on_event("startup")
async def startup_load_models():
    global _generator
    from kadastra.loader import get_generator
    _generator = get_generator()
    print(f"Kadastra agent loaded. XGBoost models: {len(_generator.simulator._xgb_models)}")
    from kadastra.constants_updater import run_weekly_update
    _scheduler.add_job(run_weekly_update, "interval", weeks=1, id="constants_weekly")
    _scheduler.start()
    print("Constants scheduler started (weekly BCT TMM update).")


@app.on_event("shutdown")
async def shutdown_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


# ── Request / Response schemas ────────────────────────────────────────────
class PropertyInput(BaseModel):
    Type: str = "Appartement a vendre"
    Adresse: str = "Tunis"
    price_numeric: float = 250_000
    surface_numeric: float = 120
    pieces: Optional[float] = None
    chambres: Optional[float] = None
    sallesdebain: Optional[float] = None
    meuble: int = 0
    neuf: int = 0
    parking: int = 0
    ascenseur: int = 0
    balcon_terrasse: int = 0
    climatisation: int = 0
    chauffage: int = 0
    jardin: int = 0
    piscine: int = 0
    # Cross-reference data from friend's LightGBM listing-level models (optional)
    market_price_estimate: Optional[float] = None   # predicted fair market price (TND)
    market_price_label:    Optional[str]   = None   # 'great'|'fair'|'high'|'very_high'
    market_price_delta_pct: Optional[float] = None  # (listed - estimated) / estimated × 100

class InvestmentProfile(BaseModel):
    budget: float = 300_000
    holding_period_years: int = 5
    rental_income: float = 0
    first_time_buyer: bool = True
    is_new_promoter: bool = False
    risk_tolerance: str = "medium"

class AnalyzeRequest(BaseModel):
    property: PropertyInput
    profile: Optional[InvestmentProfile] = None

class QuickAnalyzeRequest(BaseModel):
    text: Optional[str] = None
    type: Optional[str] = None
    location: Optional[str] = None
    price: Optional[float] = None
    surface: Optional[float] = None
    budget: Optional[float] = None
    holding_years: Optional[int] = None
    is_new: Optional[bool] = None
    has_parking: Optional[bool] = None
    has_elevator: Optional[bool] = None

class ChatRequest(BaseModel):
    text: str
    groq_key: Optional[str] = None   # client may pass own key; fallback to env

class PredictPricesRequest(BaseModel):
    properties: List[PropertyInput]


# ── Helpers ───────────────────────────────────────────────────────────────
def _check_loaded():
    if _generator is None:
        raise HTTPException(status_code=503, detail="Models not loaded yet")

# Rental type → nearest sale equivalent for XGBoost lookup
_SALE_EQUIV = {
    "Appartement a louer":      "Appartement a vendre",
    "Maison a louer":           "Maison a vendre",
    "Villa a louer":            "Villa a vendre",
    "Studio a louer":           "Studio a vendre",
    "Bureau a louer":           "Bureau a vendre",
    "Local commercial a louer": "Local commercial a vendre",
}
# National gross yield used to back-calculate purchase price from monthly rent
_NATIONAL_YIELD = 0.0543

def _normalize_missing_price(prop: dict, profile: dict | None) -> tuple[dict, list[str]]:
    """
    Resolve price issues before validation so analysis is always meaningful.

    Three cases handled in order:

    A. ANY type — price == 0 (listing had no price / "Prix à consulter"):
       → Use XGBoost to estimate market value.
       → Add a prominent warning so the chatbot explicitly tells the user.

    B. RENTAL type — 0 < price < 20 000 TND (clearly a monthly rent, not a purchase price):
       → Convert: estimated_purchase = monthly_rent × 12 / national_gross_yield (5.43%)
       → Store the annual rent in profile["rental_income"] so yield calculations are accurate.
       → Add a warning explaining the conversion.

    C. Everything else — price is already a valid purchase price → pass through unchanged.
    """
    extra_warnings: list[str] = []
    price     = float(prop.get("price_numeric", 0) or 0)
    is_rental = "louer" in str(prop.get("Type", "")).lower()

    # ── Case A: no price at all (Prix à consulter or missing field) ───────
    if price <= 0:
        proxy_type = _SALE_EQUIV.get(prop.get("Type", ""), prop.get("Type", "Appartement a vendre"))
        proxy = {**prop, "Type": proxy_type, "price_numeric": 0}
        try:
            estimated = float(_generator.simulator.predict_exit_price(proxy, years=0))
            if estimated > 0:
                prop = {**prop, "price_numeric": round(estimated)}
                extra_warnings.append(
                    f"Prix à consulter — aucun prix original disponible. "
                    f"L'analyse utilise une estimation marché: "
                    f"{round(estimated):,} TND. Les résultats sont indicatifs."
                )
        except Exception:
            pass  # price stays 0; validate_property_input will add a soft warning for rentals
        return prop, extra_warnings

    # ── Case B: rental with a monthly rent instead of a purchase price ────
    if is_rental and price < 20_000:
        estimated_purchase = round(price * 12 / _NATIONAL_YIELD)
        prop = {**prop, "price_numeric": estimated_purchase}
        if profile is not None:
            profile["rental_income"] = price * 12
        extra_warnings.append(
            f"Prix interprété comme loyer mensuel ({price:,.0f} TND/mois) — "
            f"valeur vénale estimée: {estimated_purchase:,} TND"
        )

    return prop, extra_warnings


def _run_validation(prop: dict):
    """Run validation and raise 422 if there are hard errors."""
    from kadastra.core import validate_property_input
    v = validate_property_input(prop)
    if not v["valid"]:
        raise HTTPException(status_code=422, detail={
            "type":     "validation_error",
            "errors":   v["errors"],
            "warnings": v["warnings"],
        })
    return v["warnings"]   # pass back to caller so they can include in response

def _deep_convert(obj):
    import numpy as np
    if isinstance(obj, dict):
        return {k: _deep_convert(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_deep_convert(v) for v in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def _cross_reference_market_price(prop: dict) -> list[str]:
    """
    If the listing was annotated by the Django-side LightGBM price analyser,
    cross-reference its estimate with the listed price and add contextual
    warnings so the chatbot can surface them in its verdict.
    """
    warnings: list[str] = []
    estimate = prop.get("market_price_estimate")
    label    = prop.get("market_price_label")
    delta    = prop.get("market_price_delta_pct")

    if not estimate or not label:
        return warnings

    label_fr = {
        "great":     "Bonne affaire",
        "fair":      "Prix du marché",
        "high":      "Prix élevé",
        "very_high": "Très surévalué",
    }.get(label, label)

    listed = float(prop.get("price_numeric", 0) or 0)
    delta_str = f"{'+' if delta and delta > 0 else ''}{round(delta or 0)}%"

    if label == "very_high":
        warnings.append(
            f"⚠️ Analyse comparative (modèles LightGBM) : ce bien est classé « {label_fr} » "
            f"— prix listé {delta_str} au-dessus du prix estimé par le marché "
            f"(~{round(estimate):,} TND). Tenez-en compte dans votre négociation."
        )
    elif label == "high":
        warnings.append(
            f"Analyse comparative : bien classé « {label_fr} » "
            f"({delta_str} vs estimation marché ~{round(estimate):,} TND). "
            f"Une négociation est recommandée."
        )
    elif label == "great":
        warnings.append(
            f"✅ Opportunité de marché confirmée : ce bien est classé « {label_fr} » "
            f"({delta_str} vs estimation marché ~{round(estimate):,} TND). "
            f"Le prix listé est inférieur à la valeur marché estimée."
        )
    # 'fair' → no warning needed, price is aligned

    return warnings


# ── Endpoints ─────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    models_loaded = _generator is not None and _generator.simulator._xgb_trained
    return {
        "status": "ok" if models_loaded else "loading",
        "models_loaded": models_loaded,
        "xgb_types": list(_generator.simulator._xgb_models.keys()) if _generator else [],
    }


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    _check_loaded()
    t0 = time.time()

    prop = req.property.dict()
    for k in ["pieces", "chambres", "sallesdebain"]:
        if prop[k] is None:
            prop[k] = 0

    profile = req.profile.dict() if req.profile else None

    # ── Rental price normalisation (must run BEFORE validation) ──
    prop, extra_warnings = _normalize_missing_price(prop, profile)

    # ── Sanity check ──
    warnings = extra_warnings + _run_validation(prop)

    # ── Cross-reference with listing-level price analysis ────────────────
    warnings += _cross_reference_market_price(prop)

    try:
        scenario = _generator.generate_investment_scenario(prop, profile)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    elapsed  = time.time() - t0
    scenario = _deep_convert(scenario)

    return {
        "scenario":        scenario,
        "warnings":        warnings,
        "elapsed_seconds": round(elapsed, 2),
    }


@app.post("/api/quick-analyze")
async def quick_analyze(req: QuickAnalyzeRequest):
    _check_loaded()

    prop_dict: dict = {}
    if req.text:
        prop_dict = _parse_natural_language(req.text)

    if req.type:         prop_dict["Type"]            = req.type
    if req.location:     prop_dict["Adresse"]          = req.location
    if req.price:        prop_dict["price_numeric"]    = req.price
    if req.surface:      prop_dict["surface_numeric"]  = req.surface
    if req.is_new:       prop_dict["neuf"]             = 1
    if req.has_parking:  prop_dict["parking"]          = 1
    if req.has_elevator: prop_dict["ascenseur"]        = 1

    prop_dict.setdefault("Type",           "Appartement a vendre")
    prop_dict.setdefault("Adresse",        "Tunis")
    prop_dict.setdefault("price_numeric",  250_000)
    prop_dict.setdefault("surface_numeric", 100)
    for k in ["meuble","neuf","parking","ascenseur","balcon_terrasse",
              "climatisation","chauffage","jardin","piscine"]:
        prop_dict.setdefault(k, 0)
    for k in ["pieces","chambres","sallesdebain"]:
        prop_dict.setdefault(k, 0)

    profile = {
        "budget":               req.budget or 300_000,
        "holding_period_years": req.holding_years or 5,
        "rental_income":        0,
        "first_time_buyer":     True,
        "is_new_promoter":      prop_dict.get("neuf", 0) == 1,
        "risk_tolerance":       "medium",
    }

    # ── Rental price normalisation (must run BEFORE validation) ──
    prop_dict, extra_warnings = _normalize_missing_price(prop_dict, profile)

    # ── Sanity check ──
    warnings = extra_warnings + _run_validation(prop_dict)

    t0 = time.time()
    try:
        scenario = _generator.generate_investment_scenario(prop_dict, profile)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    scenario = _deep_convert(scenario)
    elapsed  = time.time() - t0

    v = scenario["verdict"]
    s = scenario["simulator"]
    r = scenario["risk"]
    t = scenario["tax"]

    mc_primary = s.get("mc_primary", s["mc_rental"])   # honour scenario selection
    return {
        "verdict":   v["recommendation"],
        "score":     v["score"],
        "summary":   f"{v['recommendation']} ({v['score']}/100)",
        "primary_scenario": s.get("primary_scenario", "locatif"),
        "financials": {
            "gross_yield":            s["rental_yield"]["gross_yield"],
            "net_yield":              s["rental_yield"]["net_yield"],
            "irr_percent":            s["roi_rental"]["irr_percent"],
            "monthly_rent_estimate":  s["rental_yield"]["estimated_monthly_rent"],
            "npv_p5":                 mc_primary["npv_p5"],
            "npv_p50":                mc_primary["npv_p50"],
            "npv_p95":                mc_primary["npv_p95"],
            "prob_positive_npv":      mc_primary["prob_positive"],
            "initial_investment":     s["roi_rental"]["initial_investment"],
            "monthly_mortgage":       s["roi_rental"]["monthly_mortgage"],
        },
        "risk": {
            "level":      r["risk_level"],
            "score":      r["overall_risk_score"],
            "flags":      r["risk_flags"],
            "components": r["component_scores"],
            "mitigation": r["mitigation"],
        },
        "tax": {
            "acquisition_fees_pct": t["acquisition_costs"]["fees_pct"],
            "acquisition_fees_tnd": t["acquisition_costs"]["total_fees"],
            "optimal_holding_years": t["optimal_holding_years"],
            "cgt_note":             t["cgt_cliff_note"],
            "annual_taxes":         t["annual_tax_burden"],
        },
        "insights":         v["key_insights"],
        "explanations":     scenario["explanations"],
        "holding_sweep":    t["holding_period_sweep"],
        "warnings":         warnings,
        "elapsed_seconds":  round(elapsed, 2),
    }


@app.post("/api/predict-prices")
async def predict_prices(req: PredictPricesRequest):
    """
    Batch XGBoost price prediction for listings that have no listed price.
    Called by the Django backend when serving listings with 'Prix à consulter'.
    Returns current market value estimates (years=0 appreciation).
    """
    _check_loaded()
    predictions = []
    _SALE_EQUIV = {  # map rental types to nearest sale type for XGBoost lookup
        "Appartement a louer": "Appartement a vendre",
        "Maison a louer":      "Maison a vendre",
        "Villa a louer":       "Villa a vendre",
        "Studio a louer":      "Studio a vendre",
        "Bureau a louer":      "Bureau a vendre",
        "Local commercial a louer": "Local commercial a vendre",
    }
    for prop_input in req.properties:
        prop = prop_input.dict()
        for k in ["pieces", "chambres", "sallesdebain"]:
            if prop[k] is None:
                prop[k] = 0
        # If type not in models, try sale equivalent
        sim = _generator.simulator
        if prop["Type"] not in sim._xgb_models:
            prop["Type"] = _SALE_EQUIV.get(prop["Type"], prop["Type"])
        try:
            predicted = sim.predict_exit_price(prop, years=0)
            val = float(predicted)
            predictions.append(round(val) if val > 0 else None)
        except Exception:
            predictions.append(None)
    return {"predictions": predictions}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    LLM-like conversational endpoint.
    Routes to deal_search / market_analysis / portfolio_advice / general.
    """
    _check_loaded()

    from kadastra.chat_engine import handle_chat

    groq_key = (
        req.groq_key
        or os.environ.get("GROQ_API_KEY")
        or None
    )

    try:
        result = handle_chat(
            text=req.text,
            df=_generator.df,
            portfolio_advisor=_generator.portfolio_advisor,
            groq_key=groq_key,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return _deep_convert(result)


@app.get("/api/constants")
async def get_constants():
    from kadastra.core import TUNISIA_CONSTANTS
    return _deep_convert(TUNISIA_CONSTANTS)


@app.post("/api/update-constants")
async def update_constants(overrides: Dict[str, Any] = {}):
    from kadastra.constants_updater import apply_manual_overrides
    from kadastra.core import TUNISIA_CONSTANTS
    accepted = apply_manual_overrides(overrides)
    return {
        "accepted":          accepted,
        "rejected":          [k for k in overrides if k not in accepted],
        "current_constants": _deep_convert(TUNISIA_CONSTANTS),
    }


@app.post("/api/trigger-update")
async def trigger_update():
    from kadastra.constants_updater import run_weekly_update
    updated = run_weekly_update()
    from kadastra.core import TUNISIA_CONSTANTS
    return {"updated_keys": updated, "current_constants": _deep_convert(TUNISIA_CONSTANTS)}


# ── Natural-language parser ───────────────────────────────────────────────
def _parse_natural_language(text: str) -> dict:
    import re
    result = {}
    text_lower = text.lower()

    if "appartement" in text_lower or "appart" in text_lower:
        result["Type"] = "Appartement a louer" if "louer" in text_lower or "location" in text_lower \
                         else "Appartement a vendre"
    elif "maison" in text_lower or "villa" in text_lower:
        result["Type"] = "Maison a louer" if "louer" in text_lower else "Maison a vendre"
    elif "terrain" in text_lower:
        result["Type"] = "Terrain a vendre"
    elif "local" in text_lower or "commercial" in text_lower:
        result["Type"] = "Local commercial a vendre"

    price_match = re.search(r'(\d[\d\s,.]*)\s*(?:tnd|dt|dinars?)', text_lower)
    if price_match:
        price_str = price_match.group(1).replace(" ","").replace(",","").replace(".","")
        try:    result["price_numeric"] = float(price_str)
        except: pass
    if "price_numeric" not in result:
        pm2 = re.search(r'(?:prix|price|cout)\s*:?\s*(\d[\d\s,.]*)', text_lower)
        if pm2:
            ps = pm2.group(1).replace(" ","").replace(",","")
            try: result["price_numeric"] = float(ps)
            except: pass

    sm = re.search(r'(\d+)\s*m[²2]?', text_lower)
    if sm:
        result["surface_numeric"] = float(sm.group(1))

    cities = ["tunis","ariana","sousse","sfax","nabeul","hammamet","bizerte",
              "monastir","gabes","kairouan","kasserine","lac","manouba","ben arous"]
    for city in cities:
        if city in text_lower:
            result["Adresse"] = city.title()
            break

    for kw, key in [
        (["neuf","neuve","new"], "neuf"),
        (["parking"],            "parking"),
        (["ascenseur","elevator"],"ascenseur"),
        (["meuble","furnished"], "meuble"),
        (["climatisation","clim"],"climatisation"),
        (["piscine","pool"],     "piscine"),
        (["jardin","garden"],    "jardin"),
    ]:
        if any(k in text_lower for k in kw):
            result[key] = 1

    return result
