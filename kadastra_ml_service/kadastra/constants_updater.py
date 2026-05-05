"""
KADASTRA — Tunisia Constants Auto-Updater
Attempts weekly fetch of BCT TMM rate and market yields.
Falls back gracefully to a local override JSON file, then to hardcoded baseline.

Admin manual override: POST /api/update-constants  {"bcт_tmm": 0.0800, ...}
Override file: $KADASTRA_MODEL_DIR/constants_override.json
"""
import json, os, logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_OVERRIDE_FILE = Path(os.environ.get("KADASTRA_MODEL_DIR", "/app/kadastra_models")) / "constants_override.json"

# Updatable keys — only these are ever overwritten at runtime
UPDATABLE_KEYS = {
    "bcт_tmm", "mortgage_rate_mid", "inflation_cpi",
    "gross_yield_national", "gross_yield_tunis", "gross_yield_sfax",
    "appreciation_national", "appreciation_tunis",
    "appreciation_sousse", "appreciation_sfax", "appreciation_nabeul",
}


def _try_fetch_bct_tmm() -> float | None:
    """
    Attempt to scrape the BCT TMM rate from the central bank website.
    Returns a float (decimal, e.g. 0.0800 for 8.00%) or None on any failure.
    BCT publishes TMM monthly at bct.gov.tn — scraping is best-effort.
    """
    try:
        import re, requests
        from bs4 import BeautifulSoup
        resp = requests.get(
            "https://www.bct.gov.tn/bct/siteprod/english/indicateurs/taux_interet.jsp",
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (compatible; KadastraBot/1.0)"},
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(" ", strip=True)
        # BCT page typically shows "TMM  8,00%" or "TMM: 7.49"
        m = re.search(r'TMM[^0-9]{0,15}(\d{1,2}[.,]\d{1,2})', text, re.IGNORECASE)
        if m:
            rate = float(m.group(1).replace(",", ".")) / 100
            if 0.02 <= rate <= 0.25:   # sanity bounds
                logger.info(f"[constants_updater] BCT TMM fetched: {rate*100:.2f}%")
                return rate
    except Exception as exc:
        logger.warning(f"[constants_updater] BCT fetch failed: {exc}")
    return None


def load_override_file() -> dict:
    """Load manual overrides from the JSON file on disk."""
    if _OVERRIDE_FILE.exists():
        try:
            with open(_OVERRIDE_FILE) as f:
                data = json.load(f)
            logger.info(f"[constants_updater] Loaded override file ({_OVERRIDE_FILE})")
            return data
        except Exception as exc:
            logger.warning(f"[constants_updater] Could not read override file: {exc}")
    return {}


def save_override_file(data: dict):
    """Persist manual overrides to disk."""
    _OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["_last_updated"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(_OVERRIDE_FILE, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"[constants_updater] Override file saved → {_OVERRIDE_FILE}")


def run_weekly_update() -> dict:
    """
    Called by APScheduler every week.
    Priority order: BCT live fetch > override file > no change.
    Returns dict of keys that were updated.
    """
    from kadastra.core import TUNISIA_CONSTANTS
    updated = {}

    # 1. Try live BCT TMM fetch
    tmm = _try_fetch_bct_tmm()
    if tmm is not None:
        TUNISIA_CONSTANTS["bcт_tmm"] = tmm
        TUNISIA_CONSTANTS["mortgage_rate_mid"] = round(tmm + 0.015, 4)  # BCT + typical bank spread
        updated["bcт_tmm"] = tmm
        updated["mortgage_rate_mid"] = TUNISIA_CONSTANTS["mortgage_rate_mid"]

    # 2. Apply anything from the override file
    overrides = load_override_file()
    for k, v in overrides.items():
        if k in UPDATABLE_KEYS and k in TUNISIA_CONSTANTS:
            TUNISIA_CONSTANTS[k] = v
            updated[k] = v

    if updated:
        logger.info(f"[constants_updater] Weekly update applied: {list(updated.keys())}")
    else:
        logger.info("[constants_updater] Weekly update: no changes (BCT fetch failed, no override file)")

    return updated


def apply_manual_overrides(overrides: dict) -> dict:
    """
    Apply admin-supplied overrides immediately and persist to file.
    Returns dict of accepted (key, value) pairs.
    """
    from kadastra.core import TUNISIA_CONSTANTS
    accepted = {}
    for k, v in overrides.items():
        if k in UPDATABLE_KEYS and k in TUNISIA_CONSTANTS:
            try:
                TUNISIA_CONSTANTS[k] = float(v)
                accepted[k] = float(v)
            except (TypeError, ValueError):
                logger.warning(f"[constants_updater] Skipped invalid value for {k}: {v}")

    if accepted:
        existing = load_override_file()
        existing.update(accepted)
        save_override_file(existing)
        logger.info(f"[constants_updater] Manual overrides applied: {accepted}")

    return accepted
