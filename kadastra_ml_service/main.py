"""
KADASTRA ML Service — FastAPI
Serves the InvestmentScenarioGenerator via HTTP.
Models are loaded once at startup and cached in memory.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import time

app = FastAPI(
    title="Kadastra ML Service",
    description="Tunisian Real Estate Investment AI Agent — API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
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


# ── Request/Response schemas ──────────────────────────────────────────────
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
    """Natural-language-style input parsed into structured fields."""
    text: Optional[str] = None
    # OR structured:
    type: Optional[str] = None
    location: Optional[str] = None
    price: Optional[float] = None
    surface: Optional[float] = None
    budget: Optional[float] = None
    holding_years: Optional[int] = None
    is_new: Optional[bool] = None
    has_parking: Optional[bool] = None
    has_elevator: Optional[bool] = None


# ── Endpoints ─────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    models_loaded = _generator is not None and _generator.simulator._xgb_trained
    return {"status": "ok" if models_loaded else "loading",
            "models_loaded": models_loaded,
            "xgb_types": list(_generator.simulator._xgb_models.keys()) if _generator else []}


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    if _generator is None:
        raise HTTPException(status_code=503, detail="Models not loaded yet")

    t0 = time.time()
    prop = req.property.dict()
    # Fill None with 0 for optional fields
    for k in ["pieces", "chambres", "sallesdebain"]:
        if prop[k] is None:
            prop[k] = 0

    profile = req.profile.dict() if req.profile else None

    try:
        scenario = _generator.generate_investment_scenario(prop, profile)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    elapsed = time.time() - t0

    # Convert numpy types to native Python for JSON serialization
    scenario = _deep_convert(scenario)

    return {
        "scenario": scenario,
        "elapsed_seconds": round(elapsed, 2),
    }


@app.post("/api/quick-analyze")
async def quick_analyze(req: QuickAnalyzeRequest):
    """Simplified endpoint — accepts partial input, fills defaults."""
    if _generator is None:
        raise HTTPException(status_code=503, detail="Models not loaded yet")

    # Parse natural language if provided
    prop_dict = {}
    if req.text:
        prop_dict = _parse_natural_language(req.text)
    
    # Override with structured fields
    if req.type: prop_dict["Type"] = req.type
    if req.location: prop_dict["Adresse"] = req.location
    if req.price: prop_dict["price_numeric"] = req.price
    if req.surface: prop_dict["surface_numeric"] = req.surface
    if req.is_new: prop_dict["neuf"] = 1
    if req.has_parking: prop_dict["parking"] = 1
    if req.has_elevator: prop_dict["ascenseur"] = 1

    # Defaults
    prop_dict.setdefault("Type", "Appartement a vendre")
    prop_dict.setdefault("Adresse", "Tunis")
    prop_dict.setdefault("price_numeric", 250_000)
    prop_dict.setdefault("surface_numeric", 100)
    for k in ["meuble","neuf","parking","ascenseur","balcon_terrasse",
              "climatisation","chauffage","jardin","piscine"]:
        prop_dict.setdefault(k, 0)
    for k in ["pieces","chambres","sallesdebain"]:
        prop_dict.setdefault(k, 0)

    profile = {
        "budget": req.budget or 300_000,
        "holding_period_years": req.holding_years or 5,
        "rental_income": 0,
        "first_time_buyer": True,
        "is_new_promoter": prop_dict.get("neuf", 0) == 1,
        "risk_tolerance": "medium",
    }

    t0 = time.time()
    try:
        scenario = _generator.generate_investment_scenario(prop_dict, profile)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    scenario = _deep_convert(scenario)
    elapsed = time.time() - t0

    # Return a simplified chat-friendly response
    v = scenario["verdict"]
    s = scenario["simulator"]
    r = scenario["risk"]
    t = scenario["tax"]

    chat_response = {
        "verdict": v["recommendation"],
        "score": v["score"],
        "summary": f"{v['recommendation']} ({v['score']}/100)",
        "financials": {
            "gross_yield": s["rental_yield"]["gross_yield"],
            "net_yield": s["rental_yield"]["net_yield"],
            "irr_percent": s["roi_rental"]["irr_percent"],
            "monthly_rent_estimate": s["rental_yield"]["estimated_monthly_rent"],
            "npv_p50": s["mc_rental"]["npv_p50"],
            "prob_positive_npv": s["mc_rental"]["prob_positive"],
        },
        "risk": {
            "level": r["risk_level"],
            "score": r["overall_risk_score"],
            "flags": r["risk_flags"],
        },
        "tax": {
            "acquisition_fees_pct": t["acquisition_costs"]["fees_pct"],
            "optimal_holding_years": t["optimal_holding_years"],
            "cgt_note": t["cgt_cliff_note"],
        },
        "insights": v["key_insights"],
        "explanations": scenario["explanations"],
        "holding_sweep": t["holding_period_sweep"],
        "elapsed_seconds": round(elapsed, 2),
    }

    return chat_response


@app.get("/api/constants")
async def get_constants():
    """Return current TUNISIA_CONSTANTS for transparency."""
    from kadastra.core import TUNISIA_CONSTANTS
    return _deep_convert(TUNISIA_CONSTANTS)


# ── Helpers ───────────────────────────────────────────────────────────────
def _parse_natural_language(text: str) -> dict:
    """Basic keyword extraction from natural language input."""
    import re
    result = {}
    text_lower = text.lower()

    # Type detection
    if "appartement" in text_lower or "appart" in text_lower:
        if "louer" in text_lower or "location" in text_lower:
            result["Type"] = "Appartement a louer"
        else:
            result["Type"] = "Appartement a vendre"
    elif "maison" in text_lower or "villa" in text_lower:
        if "louer" in text_lower:
            result["Type"] = "Maison a louer"
        else:
            result["Type"] = "Maison a vendre"
    elif "terrain" in text_lower:
        result["Type"] = "Terrain a vendre"
    elif "local" in text_lower or "commercial" in text_lower:
        result["Type"] = "Local commercial a vendre"

    # Price
    price_match = re.search(r'(\d[\d\s,.]*)\s*(?:tnd|dt|dinars?)', text_lower)
    if price_match:
        price_str = price_match.group(1).replace(" ", "").replace(",", "").replace(".", "")
        try:
            result["price_numeric"] = float(price_str)
        except ValueError:
            pass
    if "price_numeric" not in result:
        price_match2 = re.search(r'(?:prix|price|cout)\s*:?\s*(\d[\d\s,.]*)', text_lower)
        if price_match2:
            ps = price_match2.group(1).replace(" ", "").replace(",", "")
            try: result["price_numeric"] = float(ps)
            except: pass

    # Surface
    surf_match = re.search(r'(\d+)\s*m[²2]?', text_lower)
    if surf_match:
        result["surface_numeric"] = float(surf_match.group(1))

    # Location
    cities = ["tunis","ariana","sousse","sfax","nabeul","hammamet","bizerte",
              "monastir","gabes","kairouan","kasserine","lac","manouba","ben arous"]
    for city in cities:
        if city in text_lower:
            result["Adresse"] = city.title()
            break

    # Features
    if "neuf" in text_lower or "new" in text_lower or "neuve" in text_lower:
        result["neuf"] = 1
    if "parking" in text_lower:
        result["parking"] = 1
    if "ascenseur" in text_lower or "elevator" in text_lower:
        result["ascenseur"] = 1
    if "meuble" in text_lower or "furnished" in text_lower:
        result["meuble"] = 1
    if "climatisation" in text_lower or "clim" in text_lower:
        result["climatisation"] = 1
    if "piscine" in text_lower or "pool" in text_lower:
        result["piscine"] = 1
    if "jardin" in text_lower or "garden" in text_lower:
        result["jardin"] = 1

    return result


def _deep_convert(obj):
    """Recursively convert numpy types to native Python for JSON."""
    import numpy as np
    if isinstance(obj, dict):
        return {k: _deep_convert(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_deep_convert(v) for v in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    return obj
