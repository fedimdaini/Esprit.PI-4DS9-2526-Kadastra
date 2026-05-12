"""
normal_mode.py — Kadastra Normal Mode Analysis
================================================
Designed for regular users: renters, students, first-time home buyers.
NO investment jargon (no IRR, BCT, NPV, Monte Carlo, holding period).

Output focuses on three questions every normal user asks:
  1. Is the price fair?  (price comparison: listed vs estimated)
  2. Is it a good place to live?  (neighbourhood, services, safety)
  3. What does the property offer?  (amenities, features)
"""

import os, json, logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Esprit LLM ────────────────────────────────────────────────────────────────
_LLM_KEY   = os.environ.get("ESPRIT_API_KEY", "sk-e8d1f52f7bce4a349af80b4080b24205")
_LLM_BASE  = "https://tokenfactory.esprit.tn/api"
_LLM_MODEL = "hosted_vllm/Llama-3.1-70B-Instruct"


def _call_llm(system_prompt: str, user_content: str, max_tokens: int = 420) -> Optional[str]:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=_LLM_KEY, base_url=_LLM_BASE)
        resp = client.chat.completions.create(
            model=_LLM_MODEL,
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user",   "content": user_content}],
            max_tokens=max_tokens,
            temperature=0.25,
        )
        content = resp.choices[0].message.content.strip()
        try:
            content = content.encode('latin-1').decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
        return content
    except Exception as exc:
        logger.warning("Esprit LLM call failed: %s", exc)
        return None


# ── Governorate inference ─────────────────────────────────────────────────────
_GOV_PATTERNS = {
    "Tunis":       ["tunis","lac","belvédère","belvedere","centre ville","bab","menzah",
                    "montplaisir","ennasr","menzil bourguiba","les berges","lafayette"],
    "Ariana":      ["ariana","borj louzir","soukra","raoued","la marsa","sidi thabet","ain drahem"],
    "Ben Arous":   ["ben arous","rades","hammam lif","mourouj","megrine","ezzahra","bou mhel"],
    "Manouba":     ["manouba","denden","oued ellil","tebourba","el battane"],
    "Nabeul":      ["nabeul","hammamet","kelibia","cap bon","menzel temime","grombalia"],
    "Sousse":      ["sousse","el kantaoui","port el kantaoui","kalaa kebira","m'saken"],
    "Monastir":    ["monastir","skanes","moknine","zeramdine","ksar hellal"],
    "Sfax":        ["sfax","sakiet ezzit","thyna","agareb","el ain"],
    "Bizerte":     ["bizerte","menzel bourguiba","mateur","zarzouna"],
    "Mahdia":      ["mahdia","el jem","chebba"],
    "Gabes":       ["gabes","el hamma","mareth"],
    "Mednine":     ["mednine","médenine","djerba","houmt souk","midoun","zarzis","ben gardane"],
    "Kairouan":    ["kairouan","sbeitla"],
    "Zaghouan":    ["zaghouan","el fahs"],
    "Beja":        ["beja","béja","nefza"],
    "Jendouba":    ["jendouba","tabarka","ain draham"],
    "Kef":         ["kef","le kef","siliana","dahmani"],
    "Gafsa":       ["gafsa","metlaoui","redeyef"],
    "Tozeur":      ["tozeur","nefta"],
    "Kebili":      ["kebili","douz"],
    "Kasserine":   ["kasserine","sbeitla","feriana"],
    "Sidi Bouzid": ["sidi bouzid","regueb"],
    "Tataouine":   ["tataouine","remada","ghomrassen"],
}

# Urban governorates — better services, higher baseline prices
_URBAN_GOVS      = {"Tunis","Ariana","Ben Arous","Manouba","Sousse","Sfax","Monastir","Nabeul","Bizerte"}
# Coastal/tourist governorates — premium for location
_COASTAL_GOVS    = {"Nabeul","Sousse","Monastir","Mahdia","Bizerte","Sfax","Mednine"}

# Rent benchmarks TND/month for a standard 80 m² apartment
_RENT_BENCH = {
    "Tunis":900,"Ariana":750,"Ben Arous":650,"Manouba":550,
    "Sousse":700,"Sfax":600,"Monastir":600,"Nabeul":600,
    "Bizerte":500,"Mahdia":450,"Gabes":450,"Mednine":400,
    "Kairouan":380,"Beja":350,"Jendouba":320,"Kef":320,
    "Gafsa":370,"Tozeur":350,"Kebili":300,"Kasserine":320,
    "Sidi Bouzid":300,"Tataouine":280,"Zaghouan":350,
}


def _extract_governorate(adresse: str) -> Optional[str]:
    addr = (adresse or "").lower()
    for gov, patterns in _GOV_PATTERNS.items():
        if any(p in addr for p in patterns):
            return gov
    return None


# ── Price comparison ──────────────────────────────────────────────────────────

def _build_price_comparison(prop: dict, xgb_estimate: Optional[float]) -> dict:
    """
    Returns a dict describing the price comparison for the USER (no financial jargon).

    For rentals with a monthly rent: compare against local rent benchmark.
    For sales: compare against LightGBM / XGBoost estimate.

    Returns:
        listed        — what the listing shows
        estimated     — our market estimate
        unit          — "TND/mois" or "TND"
        diff_pct      — (listed − estimated) / estimated × 100  (negative = cheaper)
        verdict       — human label
        verdict_color — hex colour
        source        — short explanation of where the estimate comes from
        factors       — list[str] explaining why this is the estimated price
    """
    is_rental       = "louer" in str(prop.get("Type","")).lower()
    monthly_rent    = prop.get("_original_monthly_rent")     # set by normaliser
    label           = prop.get("market_price_label")         # LightGBM
    delta_pct       = float(prop.get("market_price_delta_pct") or 0)
    lgbm_estimate   = prop.get("market_price_estimate")
    listed_price    = float(prop.get("price_numeric", 0) or 0)
    surface         = float(prop.get("surface_numeric", 0) or 0)
    gov             = _extract_governorate(prop.get("Adresse",""))

    factors = []  # will explain WHY the estimated price is what it is

    # ── Case 1: Rental with a monthly rent ────────────────────────────────────
    if monthly_rent:
        listed    = float(monthly_rent)
        bench     = _RENT_BENCH.get(gov, 500)
        # Adjust bench for surface: bench is for ~80 m², scale proportionally (soft)
        if surface > 0:
            bench = bench * (0.6 + 0.4 * min(surface / 80, 2.0))
        # Adjust for amenities
        extras = 0
        if prop.get("meuble"):    extras += 0.10
        if prop.get("parking"):   extras += 0.06
        if prop.get("ascenseur"): extras += 0.03
        if prop.get("piscine"):   extras += 0.12
        if prop.get("jardin"):    extras += 0.08
        bench = bench * (1 + extras)
        estimated = round(bench)
        unit      = "TND/mois"
        # Factors
        if gov in _URBAN_GOVS:
            factors.append(f"📍 Quartier urbain ({gov}) — zone bien desservie, loyers typiquement entre {round(bench*0.8):,}–{round(bench*1.2):,} TND/mois")
        elif gov:
            factors.append(f"📍 Gouvernorat {gov} — loyers de référence autour de {estimated:,} TND/mois pour ce type de bien")
        else:
            factors.append("📍 Localisation non identifiée — estimation basée sur la moyenne nationale")
        if prop.get("meuble"):    factors.append("🛋️ Appartement meublé — majoration de ~10% par rapport au non-meublé")
        if prop.get("parking"):   factors.append("🚗 Place de parking incluse — valeur ajoutée significative")
        if prop.get("piscine"):   factors.append("🏊 Piscine — fort premium sur le prix")
        if surface > 100:         factors.append(f"📐 Grande surface ({round(surface)} m²) — loyer ajusté en conséquence")
        elif surface > 0:         factors.append(f"📐 Surface de {round(surface)} m² prise en compte dans l'estimation")

    # ── Case 2: LightGBM label available (from Django) ────────────────────────
    elif label and lgbm_estimate:
        listed    = listed_price
        estimated = round(float(lgbm_estimate))
        unit      = "TND"
        factors.append(f"📊 Estimation calculée par notre modèle d'analyse sur des milliers d'annonces similaires")
        if gov in _URBAN_GOVS:
            factors.append(f"📍 Zone {gov} — l'emplacement représente une part importante du prix")
        if surface > 0:
            factors.append(f"📐 Surface de {round(surface)} m² — critère principal dans l'évaluation")
        for key, lbl in [("neuf","✨ Bien neuf — majoration par rapport à l'ancien"),
                         ("parking","🚗 Parking inclus — valeur supplémentaire"),
                         ("piscine","🏊 Piscine — fort premium"),
                         ("ascenseur","🛗 Ascenseur — critère recherché en immeuble")]:
            if prop.get(key): factors.append(lbl)

    # ── Case 3: XGBoost estimate (sale, no LightGBM) ──────────────────────────
    elif xgb_estimate and xgb_estimate > 10_000:
        listed    = listed_price
        estimated = round(float(xgb_estimate))
        unit      = "TND"
        factors.append("📊 Estimation issue de notre modèle IA entraîné sur le marché tunisien")
        if gov:
            factors.append(f"📍 Localisation {gov} — l'emplacement influence fortement la valeur")
        if surface > 0:
            factors.append(f"📐 Surface de {round(surface)} m² — principal déterminant du prix")
        for key, lbl in [("neuf","✨ Bien neuf — prime de ~15–20% sur l'ancien"),
                         ("parking","🚗 Parking — valeur ajoutée ~15 000–30 000 TND"),
                         ("piscine","🏊 Piscine — premium important"),
                         ("jardin","🌿 Jardin privatif — valeur ajoutée notable")]:
            if prop.get(key): factors.append(lbl)

    # ── Case 4: No reliable estimate ──────────────────────────────────────────
    else:
        listed    = listed_price
        estimated = None
        unit      = "TND/mois" if is_rental else "TND"
        factors.append("ℹ️ Données de référence insuffisantes pour une comparaison précise dans ce secteur")

    # Compute diff
    diff_pct = 0.0
    if estimated and estimated > 0:
        diff_pct = round((listed - estimated) / estimated * 100, 1)

    # Verdict label
    if estimated is None:
        verdict, color = "Prix non évalué", "#64748B"
    elif diff_pct <= -15:
        verdict, color = "Très bon prix 🎉", "#059669"
    elif diff_pct <= -5:
        verdict, color = "Bon prix ✅", "#16a34a"
    elif diff_pct <= 5:
        verdict, color = "Prix correct", "#ca8a04"
    elif diff_pct <= 20:
        verdict, color = "Prix un peu élevé ⚠️", "#ea580c"
    else:
        verdict, color = "Prix excessif ❌", "#dc2626"

    return {
        "listed":        listed,
        "estimated":     estimated,
        "unit":          unit,
        "diff_pct":      diff_pct,
        "verdict":       verdict,
        "verdict_color": color,
        "factors":       factors,
        "label_used":    label or ("benchmark" if monthly_rent else ("xgboost" if xgb_estimate else "none")),
    }


# ── Neighbourhood ─────────────────────────────────────────────────────────────

def _build_neighbourhood(prop: dict, risk_result: dict) -> dict:
    """Builds a simple neighbourhood summary for the consumer card."""
    gov      = _extract_governorate(prop.get("Adresse",""))
    is_urban = gov in _URBAN_GOVS if gov else False

    # Services
    n_schools   = int(prop.get("n_schools",   0) or 0)
    n_hospitals = int(prop.get("n_hospitals", 0) or 0)
    n_transit   = int(prop.get("n_transit",   0) or 0)
    n_retail    = int(prop.get("n_retail",    0) or 0)
    dist_hosp   = float(prop.get("dist_hospital_km", 99) or 99)
    dist_trans  = float(prop.get("dist_transit_km",  99) or 99)

    has_poi = (n_schools + n_hospitals + n_transit) > 0
    services = []

    if has_poi:
        # Schools
        if n_schools >= 5:   services.append(f"🏫 {n_schools} écoles et établissements scolaires à proximité — idéal pour les familles")
        elif n_schools >= 2: services.append(f"🏫 {n_schools} écoles accessibles dans le quartier")
        elif n_schools == 1: services.append("🏫 1 école à proximité")
        else:                services.append("🏫 Aucune école identifiée directement dans la zone — à vérifier")

        # Health
        if dist_hosp < 1.0:        services.append("🏥 Hôpital à moins d'1 km — excellente couverture santé")
        elif n_hospitals >= 2:     services.append(f"🏥 {n_hospitals} établissements de santé proches")
        elif n_hospitals == 1:     services.append("🏥 Établissement de santé accessible")
        elif dist_hosp < 5:        services.append(f"🏥 Hôpital à {dist_hosp:.1f} km")
        else:                      services.append("🏥 Santé : prévoir un moyen de déplacement")

        # Transit
        if dist_trans < 0.3:       services.append(f"🚌 Transport en commun à {round(dist_trans*1000)} m — très pratique")
        elif dist_trans < 1.0:     services.append(f"🚌 Arrêt de bus / transport à {dist_trans:.1f} km")
        elif n_transit >= 3:       services.append(f"🚌 {n_transit} points de transport accessibles dans le quartier")
        elif n_transit >= 1:       services.append("🚌 Transport en commun disponible dans la zone")
        else:                      services.append("🚌 Transport en commun limité — voiture recommandée")

        # Retail
        if n_retail >= 6:          services.append(f"🛒 {n_retail} commerces et services quotidiens à portée")
        elif n_retail >= 2:        services.append("🛒 Commerces disponibles dans la zone")
    else:
        # Heuristic fallback
        if is_urban:
            services.append(f"🏙️ Zone urbaine ({gov}) — commerces, transports et services accessibles")
            services.append("🏥 Accès aux soins de santé dans la zone urbaine")
            services.append("🚌 Transports en commun généralement bien présents")
        elif gov:
            services.append(f"📍 Gouvernorat {gov} — services variables selon le quartier exact")
            services.append("🏥 Vérifiez la proximité des établissements de santé")
            services.append("🚌 Transport : renseignez-vous sur les lignes disponibles")
        else:
            services.append("📍 Localisation non précisément identifiée")
            services.append("🏥 Vérifiez la proximité des services essentiels")

    # Safety (from risk engine)
    rl = risk_result.get("risk_level", "Medium")
    rs = float(risk_result.get("overall_risk_score", 0.5))

    if rs < 0.25 or rl == "Low":
        safety      = "Très sûr ✅"
        safety_desc = "Le quartier présente un niveau de risque très faible — environnement stable et tranquille."
        safety_color= "#059669"
        safety_icon = "🟢"
    elif rs < 0.50:
        safety      = "Quartier correct 🟡"
        safety_desc = "Quartier globalement calme, quelques points de vigilance habituels en zone urbaine."
        safety_color= "#ca8a04"
        safety_icon = "🟡"
    elif rs < 0.70:
        safety      = "Vigilance recommandée ⚠️"
        safety_desc = "Le secteur présente quelques facteurs de risque — renseignez-vous auprès des habitants."
        safety_color= "#ea580c"
        safety_icon = "🟠"
    else:
        safety      = "Quartier risqué ❌"
        safety_desc = "Plusieurs indicateurs de risque identifiés — visitez le quartier à différentes heures."
        safety_color= "#dc2626"
        safety_icon = "🔴"

    return {
        "governorate":   gov or "Non identifiée",
        "zone_type":     "Urbaine" if is_urban else ("Semi-urbaine" if gov else "Rurale / Non identifiée"),
        "services":      services,
        "safety":        safety,
        "safety_desc":   safety_desc,
        "safety_color":  safety_color,
        "safety_icon":   safety_icon,
    }


# ── Amenities ─────────────────────────────────────────────────────────────────

def _build_amenities(prop: dict) -> list:
    is_rental = "louer" in str(prop.get("Type","")).lower()
    items = []
    checks = [
        ("parking",         "🚗 Parking"),
        ("ascenseur",       "🛗 Ascenseur"),
        ("balcon_terrasse", "🏞️ Balcon / Terrasse"),
        ("climatisation",   "❄️ Climatisation"),
        ("chauffage",       "🔥 Chauffage central"),
        ("jardin",          "🌿 Jardin privatif"),
        ("piscine",         "🏊 Piscine"),
        ("neuf",            "✨ Bien neuf / récent"),
    ]
    if is_rental:
        checks.insert(0, ("meuble", "🛋️ Meublé"))
    for key, label in checks:
        if prop.get(key):
            items.append(label)
    return items


# ── Recommendation ────────────────────────────────────────────────────────────

def _recommendation(price_cmp: dict, neighbourhood: dict) -> tuple:
    """Returns (key, fr_label, color)."""
    price_ok  = price_cmp["diff_pct"] <= 10 if price_cmp["estimated"] else True
    safety_ok = "🔴" not in neighbourhood["safety_icon"]
    price_bad = price_cmp["diff_pct"] > 25  if price_cmp["estimated"] else False
    safety_bad= "🔴" in neighbourhood["safety_icon"]

    if price_bad or safety_bad:
        return "NON",          "❌ Non recommandé",    "#dc2626"
    elif price_ok and safety_ok:
        if price_cmp.get("diff_pct", 0) <= -5:
            return "OUI_FORT", "✅ Fortement recommandé", "#059669"
        return "OUI",          "✅ Recommandé",          "#16a34a"
    else:
        return "RESERVES",    "⚠️ Avec réserves",       "#ea580c"


# ── LLM narrative ─────────────────────────────────────────────────────────────

def _generate_narrative(prop: dict, price_cmp: dict, neighbourhood: dict,
                        amenities: list, rec_key: str) -> Optional[str]:
    is_rental = "louer" in str(prop.get("Type","")).lower()
    prop_type = prop.get("Type","Bien immobilier")
    location  = prop.get("Adresse","Tunisie")
    surface   = float(prop.get("surface_numeric",0) or 0)
    gov       = neighbourhood["governorate"]

    # Build price context for LLM
    if price_cmp["estimated"]:
        diff = price_cmp["diff_pct"]
        unit = price_cmp["unit"]
        price_ctx = (
            f"Prix affiché : {price_cmp['listed']:,.0f} {unit}. "
            f"Notre estimation de marché : {price_cmp['estimated']:,.0f} {unit}. "
            f"Écart : {'+' if diff>0 else ''}{diff}% par rapport à l'estimation "
            f"({price_cmp['verdict']})."
        )
    else:
        price_ctx = f"Prix affiché : {price_cmp['listed']:,.0f} {price_cmp['unit']} — pas de référence de comparaison disponible."

    safety_ctx = f"Niveau de sécurité du quartier : {neighbourhood['safety']}. {neighbourhood['safety_desc']}"
    services_ctx = "; ".join(s.replace("✅","").replace("⚠️","") for s in neighbourhood["services"][:3])

    sys_prompt = (
        "Tu es Kadastra, un assistant immobilier tunisien bienveillant et accessible. "
        "Tu t'adresses à un particulier — pas un investisseur — qui cherche un logement "
        f"({'à louer' if is_rental else 'à acheter'}) pour y vivre. "
        "RÈGLES ABSOLUES :\n"
        "  • NE JAMAIS mentionner : IRR, NPV, Monte Carlo, taux de capitalisation, rendement locatif, BCT, TMM, "
        "    taux d'intérêt, valeur vénale, plan de détention, retour sur investissement, horizon d'investissement\n"
        "  • Pour une location : parle uniquement du LOYER MENSUEL (jamais du prix d'achat estimé)\n"
        "  • Pour un achat : parle du prix de vente (jamais de rendement ou de plus-value)\n"
        "  • Sois chaleureux, concis (3 paragraphes max), et pratique\n"
        "Structure :\n"
        "  1. Le bien et son prix : est-ce un bon rapport qualité/prix ?\n"
        "  2. Le quartier et ses services : bonnes ou mauvaises surprises ?\n"
        "  3. Conseil pratique : point d'attention ou atout décisif avant de décider"
    )

    user_payload = json.dumps({
        "type_bien":    prop_type,
        "localisation": location,
        "gouvernorat":  gov,
        "surface_m2":   round(surface) if surface else None,
        "prix":         price_ctx,
        "securite":     safety_ctx,
        "services":     services_ctx,
        "equipements":  amenities[:6] if amenities else [],
        "recommandation": rec_key,
    }, ensure_ascii=False)

    return _call_llm(sys_prompt, user_payload, max_tokens=400)


# ── Fallback narrative ────────────────────────────────────────────────────────

def _fallback_narrative(prop: dict, price_cmp: dict, neighbourhood: dict,
                        amenities: list, rec_key: str) -> str:
    is_rental = "louer" in str(prop.get("Type","")).lower()
    loc = prop.get("Adresse","Tunisie")
    gov = neighbourhood["governorate"]

    # Price sentence
    if price_cmp["estimated"]:
        diff = price_cmp["diff_pct"]
        unit = price_cmp["unit"]
        if diff < 0:
            price_sent = (f"Le {'loyer' if is_rental else 'prix'} affiché de {price_cmp['listed']:,.0f} {unit} "
                          f"est {abs(diff):.0f}% en dessous de notre estimation ({price_cmp['estimated']:,.0f} {unit}) — "
                          f"c'est une bonne affaire dans ce secteur.")
        elif diff <= 5:
            price_sent = (f"Le {'loyer' if is_rental else 'prix'} de {price_cmp['listed']:,.0f} {unit} "
                          f"correspond bien à l'estimation du marché (~{price_cmp['estimated']:,.0f} {unit}).")
        else:
            price_sent = (f"Le {'loyer' if is_rental else 'prix'} de {price_cmp['listed']:,.0f} {unit} "
                          f"est {diff:.0f}% au-dessus de notre estimation (~{price_cmp['estimated']:,.0f} {unit}) — "
                          f"une négociation est conseillée.")
    else:
        price_sent = f"Pas de référence de comparaison disponible pour ce secteur."

    # Services sentence
    svcs = neighbourhood["services"]
    if svcs:
        svc_sent = svcs[0].split("—")[0].strip() + (". " + svcs[1].split("—")[0].strip() if len(svcs) > 1 else ".")
    else:
        svc_sent = f"Services à vérifier sur place à {loc}."

    # Safety
    safety_sent = neighbourhood["safety_desc"]

    # Amenities
    if amenities:
        amen_sent = "Le bien est équipé de : " + ", ".join(a.split()[-1] for a in amenities[:5]) + "."
    else:
        amen_sent = "Aucun équipement particulier signalé dans l'annonce."

    if rec_key in ("OUI","OUI_FORT"):
        conclusion = "Dans l'ensemble, ce bien correspond à une bonne opportunité pour se loger confortablement."
    elif rec_key == "RESERVES":
        conclusion = "Ce bien peut convenir sous réserve de vérifier les points mentionnés ci-dessus."
    else:
        conclusion = "Nous vous conseillons de continuer vos recherches ou de négocier fortement le prix avant de vous engager."

    return f"{price_sent}\n\n{svc_sent} {safety_sent}\n\n{amen_sent} {conclusion}"


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_normal(prop: dict, risk_result: dict,
                   xgb_estimate: Optional[float] = None) -> dict:
    """
    Consumer-mode analysis.
    Returns a flat dict ready for JSON serialisation — no investment jargon.
    """
    price_cmp    = _build_price_comparison(prop, xgb_estimate)
    neighbourhood= _build_neighbourhood(prop, risk_result)
    amenities    = _build_amenities(prop)
    rec_key, rec_fr, rec_color = _recommendation(price_cmp, neighbourhood)

    narrative = _generate_narrative(prop, price_cmp, neighbourhood, amenities, rec_key)
    if not narrative:
        narrative = _fallback_narrative(prop, price_cmp, neighbourhood, amenities, rec_key)

    return {
        # Recommendation
        "recommendation":       rec_key,
        "recommendation_fr":    rec_fr,
        "recommendation_color": rec_color,

        # Price comparison — the CORE of the normal mode card
        "price_listed":        price_cmp["listed"],
        "price_estimated":     price_cmp["estimated"],
        "price_unit":          price_cmp["unit"],
        "price_diff_pct":      price_cmp["diff_pct"],
        "price_verdict":       price_cmp["verdict"],
        "price_verdict_color": price_cmp["verdict_color"],
        "price_factors":       price_cmp["factors"],   # WHY the estimated price

        # Neighbourhood
        "neighborhood_name":        neighbourhood["governorate"],
        "neighborhood_type":        neighbourhood["zone_type"],
        "neighborhood_services":    neighbourhood["services"],
        "neighborhood_safety":      neighbourhood["safety"],
        "neighborhood_safety_desc": neighbourhood["safety_desc"],
        "neighborhood_safety_color":neighbourhood["safety_color"],
        "neighborhood_safety_icon": neighbourhood["safety_icon"],

        # Amenities
        "amenities":      amenities,

        # LLM narrative
        "narrative":      narrative,

        # Metadata
        "is_rental":      "louer" in str(prop.get("Type","")).lower(),
        "governorate":    neighbourhood["governorate"],
    }
