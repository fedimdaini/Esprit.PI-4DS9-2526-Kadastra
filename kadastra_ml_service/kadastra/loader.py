"""
Model loader — loads pre-trained kadastra_models/ artifacts into component classes.
Models are cached in memory after first load (singleton pattern).
"""
import os, json
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from .core import (TUNISIA_CONSTANTS, InvestmentScenarioSimulator,
                   TaxAdvantageOptimizer, RiskScoringEngine,
                   PortfolioDiversificationAdvisor, InvestmentScenarioGenerator)

_generator = None
_df = None

MODEL_DIR = os.environ.get("KADASTRA_MODEL_DIR", "/app/kadastra_models")
DATA_PATH = os.environ.get("KADASTRA_DATA_PATH", "/app/data/df_clean_K.xlsx")


def _load_dataframe():
    global _df
    if _df is not None:
        return _df
    if os.path.exists(DATA_PATH):
        _df = pd.read_excel(DATA_PATH)
    else:
        # Minimal dummy dataframe for model serving without full dataset
        _df = pd.DataFrame({
            "Type": ["Appartement a vendre"] * 10,
            "Adresse": ["Tunis"] * 10,
            "price_numeric": [200_000.0] * 10,
            "surface_numeric": [100.0] * 10,
            "pieces": [3.0] * 10,
            "chambres": [2.0] * 10,
            "sallesdebain": [1.0] * 10,
            "meuble": [0] * 10, "neuf": [0] * 10, "parking": [0] * 10,
            "ascenseur": [0] * 10, "balcon_terrasse": [0] * 10,
            "climatisation": [0] * 10, "chauffage": [0] * 10,
            "jardin": [0] * 10, "piscine": [0] * 10,
        })
    return _df


def get_generator() -> InvestmentScenarioGenerator:
    """Return a cached generator instance with pre-loaded models."""
    global _generator
    if _generator is not None:
        return _generator

    df = _load_dataframe()

    # C1: Simulator with XGBoost models
    sim = InvestmentScenarioSimulator(df, tune=False)
    if os.path.exists(MODEL_DIR):
        for fname in os.listdir(MODEL_DIR):
            if fname.startswith("xgb_") and fname.endswith(".json") and "_meta" not in fname:
                sn = fname.replace("xgb_", "").replace(".json", "")
                mp = os.path.join(MODEL_DIR, f"xgb_{sn}_meta.json")
                if os.path.exists(mp):
                    m = xgb.XGBRegressor()
                    m.load_model(os.path.join(MODEL_DIR, fname))
                    with open(mp) as f:
                        meta = json.load(f)
                    pt = sn.replace("_", " ")
                    sim._xgb_models[pt] = {
                        "model": m, "features": meta["features"],
                        "mae": meta.get("mae", 0), "rmse": meta.get("rmse", 0),
                        "r2": meta.get("r2", 0), "params": meta.get("params", {})}
        sim._xgb_trained = bool(sim._xgb_models)

    # C2: Tax optimizer (no models to load — rule engine)
    tax = TaxAdvantageOptimizer()

    # C3: Risk engine
    risk = RiskScoringEngine(df, tune=False)
    try:
        risk._if_model = joblib.load(os.path.join(MODEL_DIR, "isolation_forest.joblib"))
        risk._rf_model = joblib.load(os.path.join(MODEL_DIR, "random_forest.joblib"))
        risk._rf_feat_cols = joblib.load(os.path.join(MODEL_DIR, "rf_feat_cols.joblib"))
        risk._X_train = joblib.load(os.path.join(MODEL_DIR, "if_X_train.joblib"))
    except Exception:
        pass

    # C4: Portfolio advisor
    port = PortfolioDiversificationAdvisor(df)
    try:
        port._kmeans_model = joblib.load(os.path.join(MODEL_DIR, "kmeans.joblib"))
        port._kmeans_scaler = joblib.load(os.path.join(MODEL_DIR, "kmeans_scaler.joblib"))
        port._cluster_feats = joblib.load(os.path.join(MODEL_DIR, "kmeans_feats.joblib"))
        port._clusters_kmeans = joblib.load(os.path.join(MODEL_DIR, "kmeans_labels.joblib"))
    except Exception:
        pass

    _generator = InvestmentScenarioGenerator(df, sim, tax, risk, port)
    return _generator
