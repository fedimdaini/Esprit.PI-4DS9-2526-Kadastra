"""
KADASTRA ML Core — Constants + all 4 components + orchestrator
Extracted from KADASTRA_MODELING_v8.ipynb, zero modifications to business logic.
"""
import copy, json, os
import numpy as np
import pandas as pd
import numpy_financial as npf
import xgboost as xgb
import joblib
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.model_selection import train_test_split
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

# ═══════════════════════════════════════════════════════════════════════════
# TUNISIA CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════
_BASELINE = {
    "reg_new_promoter":[(200_000,0.01),(500_000,0.02),(float("inf"),0.03)],
    "cpf_rate":0.01,"reg_resale_low":0.06,"reg_resale_high":0.10,
    "reg_resale_thresh":1_000_000,"notary_rate":0.015,"deed_stamp_per_page":30,
    "tib_rate":0.015,"undeveloped_land":0.003,"ifi_rate":0.005,
    "ifi_threshold":3_000_000,"tcl_rate":0.002,
    "irpp_rental_flat":0.20,"irpp_nonresident":0.15,
    "cgt_lt10":0.10,"cgt_ge10":0.05,"cgt_index_per_year":0.10,"cgt_withholding":0.025,
    "bcт_tmm":0.0749,"mortgage_rate_mid":0.09,"mortgage_max_years":25,"ltv_max":0.70,
    "gross_yield_national":0.0543,"gross_yield_tunis":0.0725,"gross_yield_sfax":0.054,
    "appreciation_national":0.050,"appreciation_tunis":0.068,
    "appreciation_sousse":0.075,"appreciation_sfax":0.055,"appreciation_nabeul":0.065,
    "inflation_cpi":0.049,"vat_residential_new":0.13,
}
TUNISIA_CONSTANTS = copy.deepcopy(_BASELINE)

def rollback_constants():
    global TUNISIA_CONSTANTS
    TUNISIA_CONSTANTS = copy.deepcopy(_BASELINE)


# ═══════════════════════════════════════════════════════════════════════════
# INPUT VALIDATION
# ═══════════════════════════════════════════════════════════════════════════
_MARKET_BOUNDS = {
    "price_max":              50_000_000,  # 50 M TND (~17 M€) — absolute ceiling for sales
    "price_per_m2_max":       20_000,      # prime Tunis Lac ultra-luxury ceiling
    "surface_max":            50_000,      # 5 ha terrain — plausible upper bound
    "price_per_m2_warn_high": 12_000,      # soft warn — ultra-premium segment
}

def validate_property_input(prop: dict) -> dict:
    """
    Guard-rail check against Tunisian real estate market upper bounds only.
    Returns {"valid": bool, "errors": [...], "warnings": [...]}
    Hard errors stop analysis; warnings are shown alongside results.
    Lower bounds are not enforced — unusual prices may be legitimate.

    Rental properties ("louer") receive relaxed ppm2 checks because their
    price_numeric may represent a monthly rent that was normalised upstream.
    """
    errors, warnings = [], []
    price   = float(prop.get("price_numeric",   0) or 0)
    surface = float(prop.get("surface_numeric", 0) or 0)
    is_rental = "louer" in str(prop.get("Type", "")).lower()

    # ── Price — upper bound only ───────────────────────────────────────────
    if price <= 0:
        if is_rental:
            # For rentals, price = 0 means no price data; analysis will use
            # model defaults rather than blocking the request.
            warnings.append(
                "Prix non renseigné pour ce bien locatif — l'analyse utilisera "
                "des valeurs estimées par le modèle."
            )
        else:
            errors.append("Le prix est requis et doit être positif.")
    elif price > _MARKET_BOUNDS["price_max"]:
        errors.append(
            f"Prix de {price:,.0f} TND irréaliste pour le marché tunisien "
            f"(plafond: {_MARKET_BOUNDS['price_max']:,.0f} TND ≈ 17 M€). "
            "Vérifiez la saisie — erreur d'unité probable."
        )

    # ── Surface — upper bound only ────────────────────────────────────────
    if surface > _MARKET_BOUNDS["surface_max"]:
        warnings.append(
            f"Surface de {surface:,.0f} m² très grande — vérifiez si l'unité est correcte."
        )

    # ── Price per m² — hard cap for sales, soft warning for rentals ───────
    price_ok   = price > 0 and not errors
    surface_ok = surface > 0
    if price_ok and surface_ok:
        ppm2 = price / surface
        if ppm2 > _MARKET_BOUNDS["price_per_m2_max"]:
            if is_rental:
                # Rental: ppm2 check is unreliable (price may still be a rent
                # that slipped through normalisation). Warn, never block.
                warnings.append(
                    f"Prix au m² calculé ({ppm2:,.0f} TND/m²) inhabituel pour "
                    "un bien locatif — l'analyse continuera avec les données fournies."
                )
            else:
                errors.append(
                    f"Prix au m² de {ppm2:,.0f} TND/m² dépasse le plafond du marché tunisien "
                    f"({_MARKET_BOUNDS['price_per_m2_max']:,.0f} TND/m²). "
                    f"Calcul: {price:,.0f} TND ÷ {surface:.0f} m² = {ppm2:,.0f} TND/m². "
                    "Vérifiez le prix ou la surface."
                )
        elif ppm2 > _MARKET_BOUNDS["price_per_m2_warn_high"]:
            warnings.append(
                f"Prix au m² de {ppm2:,.0f} TND/m² — segment ultra-luxe "
                "(Lac 2, Gammarth, Marsa haut standing uniquement)."
            )

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


# ═══════════════════════════════════════════════════════════════════════════
# C1 — INVESTMENT SCENARIO SIMULATOR
# ═══════════════════════════════════════════════════════════════════════════
class InvestmentScenarioSimulator:
    FEAT_COLS = ['surface_numeric','pieces','chambres','sallesdebain',
                 'meuble','neuf','parking','ascenseur','balcon_terrasse',
                 'climatisation','chauffage','jardin','piscine']

    def __init__(self, df, tune=False):
        self.df = df; self.C = TUNISIA_CONSTANTS
        self._xgb_models = {}; self._xgb_trained = False
        self._metrics_table = []
        if tune:
            self._train_xgb(tune=True)

    def _train_xgb(self, tune=True):
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        from sklearn.model_selection import cross_val_score

        for pt, grp in self.df.groupby("Type"):
            grp = grp.dropna(subset=["price_numeric"])
            if len(grp) < 50: continue
            avail = [c for c in self.FEAT_COLS if c in grp.columns]
            X = grp[avail].astype(float).fillna(grp[avail].astype(float).median())
            y = grp["price_numeric"].astype(float)
            X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)

            if tune:
                def obj(trial):
                    p = {"n_estimators": trial.suggest_int("n_estimators",100,500),
                         "max_depth": trial.suggest_int("max_depth",3,8),
                         "learning_rate": trial.suggest_float("lr",0.01,0.2,log=True),
                         "subsample": trial.suggest_float("sub",0.6,1.0),
                         "colsample_bytree": trial.suggest_float("col",0.5,1.0)}
                    m = xgb.XGBRegressor(**p, random_state=42, verbosity=0)
                    m.fit(X_tr, y_tr, eval_set=[(X_te,y_te)], verbose=False)
                    return mean_absolute_error(y_te, m.predict(X_te))
                study = optuna.create_study(direction="minimize",
                                            sampler=optuna.samplers.TPESampler(seed=42))
                study.optimize(obj, n_trials=50, show_progress_bar=False)
                best_p = study.best_params
                best_p["learning_rate"] = best_p.pop("lr")
                best_p["subsample"] = best_p.pop("sub")
                best_p["colsample_bytree"] = best_p.pop("col")
            else:
                best_p = {"n_estimators":300,"max_depth":5,"learning_rate":0.05,
                           "subsample":0.8,"colsample_bytree":0.8}

            model = xgb.XGBRegressor(**best_p, random_state=42, verbosity=0)
            model.fit(X_tr, y_tr, eval_set=[(X_te,y_te)], verbose=False)
            pred = model.predict(X_te)
            mae = float(mean_absolute_error(y_te, pred))
            rmse = float(np.sqrt(mean_squared_error(y_te, pred)))
            r2 = float(r2_score(y_te, pred))
            self._xgb_models[pt] = {"model":model,"features":avail,
                                     "mae":mae,"rmse":rmse,"r2":r2,"params":best_p}
        self._xgb_trained = bool(self._xgb_models)

    def predict_exit_price(self, prop, years):
        pt = prop.get("Type","")
        rate = self._appr(prop.get("Adresse",""))
        if pt not in self._xgb_models:
            return float(prop.get("price_numeric",0) or 0)*(1+rate)**years
        info = self._xgb_models[pt]
        row = {c:float(prop.get(c,0) or 0) for c in info["features"]}
        base = float(info["model"].predict(pd.DataFrame([row]))[0])
        return base*(1+rate)**years

    def monte_carlo_npv(self, prop, years=5, n_sims=10_000, scenario="rental"):
        C=self.C; price=float(prop.get("price_numeric",0) or 0)
        if price <= 0: return {"npv_p5":0,"npv_p50":0,"npv_p95":0,"prob_positive":0,"n_sims":n_sims}
        down=price*(1-C["ltv_max"]); mortg=price-down
        mr=C["mortgage_rate_mid"]/12; nmo=C["mortgage_max_years"]*12
        mp=npf.pmt(mr,nmo,-mortg) if mortg>0 else 0.0; disc=C["bcт_tmm"]
        rng=np.random.default_rng(42)
        appr=rng.normal(self._appr(prop.get("Adresse","")),0.02,(n_sims,years))
        gy=rng.normal(self._yld(prop.get("Adresse","")),0.015,n_sims).clip(0.01,0.15)
        vac=rng.beta(2,8,(n_sims,years))
        npvs=np.empty(n_sims)
        for s in range(n_sims):
            cf=[-down]; cur=price
            for yr in range(years):
                cur*=(1+appr[s,yr]); gr=cur*gy[s]
                nr=gr*(1-vac[s,yr])*(1-C["irpp_rental_flat"])
                cf.append((nr-cur*0.01-mp*12) if scenario=="rental" else -(cur*0.01+mp*12))
            if scenario=="flip":
                gain=max(0,cur-price*(1+C["cgt_index_per_year"])**years)
                cgt=gain*(C["cgt_ge10"] if years>=10 else C["cgt_lt10"])
                rem=abs(npf.pv(mr,nmo-years*12,mp)); cf[-1]+=cur-rem-cgt
            npvs[s]=npf.npv(disc,cf)
        return {"npv_p5":float(np.percentile(npvs,5)),"npv_p50":float(np.percentile(npvs,50)),
                "npv_p95":float(np.percentile(npvs,95)),"prob_positive":float(np.mean(npvs>0)),
                "n_sims":n_sims}

    def calculate_rental_yield(self, prop):
        C=self.C; price=float(prop.get("price_numeric",0) or 0)
        if price<=0: return {"gross_yield":0,"net_yield":0,"estimated_monthly_rent":0,
                             "gross_annual_rent":0,"net_annual_rent":0,"annual_expenses":0}
        gr=self._yld(prop.get("Adresse",""))
        ga=price*gr; irpp=ga*C["irpp_rental_flat"]; maint=price*0.01; ins=300; mgmt=ga*0.10
        ext=(1000 if prop.get("piscine",0)==1 else 0)+(500 if prop.get("jardin",0)==1 else 0)
        exp=irpp+maint+ins+mgmt+ext; na=ga-exp
        return {"estimated_monthly_rent":round(ga/12),"gross_annual_rent":round(ga),
                "net_annual_rent":round(na),"annual_expenses":round(exp),
                "gross_yield":round(gr*100,2),"net_yield":round(na/price*100,2)}

    def calculate_roi(self, prop, years=5, scenario="rental"):
        C=self.C; price=float(prop.get("price_numeric",0) or 0)
        if price <= 0: return {"initial_investment":0,"monthly_mortgage":0,"irr_percent":0,
                               "npv_tnd":0,"payback_years":years,"cash_flows":[]}
        down=price*(1-C["ltv_max"]); mortg=price-down
        mr=C["mortgage_rate_mid"]/12; nmo=C["mortgage_max_years"]*12
        mp=npf.pmt(mr,nmo,-mortg) if mortg>0 else 0.0
        rental=self.calculate_rental_yield(prop)
        ap=self._appr(prop.get("Adresse",""))

        # Include acquisition costs in initial outflow for accurate IRR
        is_new=prop.get("neuf",0)==1
        if is_new:
            acq_reg=0
            for lim,rate in C["reg_new_promoter"]:
                if price<=lim: acq_reg=price*rate; break
        else:
            rr=C["reg_resale_low"] if price<=C["reg_resale_thresh"] else C["reg_resale_high"]
            acq_reg=price*rr
        acq_fees=acq_reg+price*C["cpf_rate"]+price*C["notary_rate"]

        cfs=[-(down+acq_fees)]; cur=price
        for _ in range(years):
            cur*=(1+ap)
            cfs.append((rental["net_annual_rent"]-mp*12) if scenario=="rental" else -(mp*12))

        # Terminal exit value applied to BOTH scenarios:
        # sell at appreciated price, pay off remaining mortgage balance, pay CGT.
        # Without this, the rental IRR has no sign change → npf.irr returns NaN → 0.
        gain=max(0,cur-price*(1+C["cgt_index_per_year"])**years)
        cgt=gain*(C["cgt_ge10"] if years>=10 else C["cgt_lt10"])
        months_rem=max(nmo-years*12, 0)
        rem=abs(npf.pv(mr,months_rem,mp)) if months_rem>0 and mortg>0 else 0.0
        cfs[-1]+=cur-rem-cgt

        try: irr=float(npf.irr(cfs))*100; irr=irr if np.isfinite(irr) else 0.0
        except: irr=0.0
        npv_val=float(npf.npv(C["bcт_tmm"],cfs))
        cumul=np.cumsum(cfs); pb=next((i for i,v in enumerate(cumul) if v>=0),years)
        return {"initial_investment":round(down+acq_fees),"monthly_mortgage":round(mp,2),
                "irr_percent":round(irr,2),"npv_tnd":round(npv_val),
                "payback_years":pb,"cash_flows":[round(c) for c in cfs]}

    def _appr(self, loc):
        C=self.C; l=str(loc).lower()
        if "tunis" in l: return C["appreciation_tunis"]
        if "sousse" in l: return C["appreciation_sousse"]
        if "sfax" in l: return C["appreciation_sfax"]
        if "nabeul" in l or "hammamet" in l: return C["appreciation_nabeul"]
        return C["appreciation_national"]

    def _yld(self, loc):
        C=self.C; l=str(loc).lower()
        if "tunis" in l: return C["gross_yield_tunis"]
        if "sfax" in l: return C["gross_yield_sfax"]
        return C["gross_yield_national"]


# ═══════════════════════════════════════════════════════════════════════════
# C2 — TAX ADVANTAGE OPTIMIZER
# ═══════════════════════════════════════════════════════════════════════════
class TaxAdvantageOptimizer:
    def __init__(self): self.C = TUNISIA_CONSTANTS

    def compute_acquisition_costs(self, price, is_new=False):
        C=self.C; cpf=price*C["cpf_rate"]; notary=price*C["notary_rate"]
        if is_new:
            reg=0
            for lim,rate in C["reg_new_promoter"]:
                if price<=lim: reg=price*rate; break
        else:
            rate=C["reg_resale_low"] if price<=C["reg_resale_thresh"] else C["reg_resale_high"]
            reg=price*rate
        tf=reg+cpf+notary
        return {"price":round(price),"registration":round(reg),"cpf":round(cpf),
                "notary":round(notary),"total_fees":round(tf),
                "total_cost":round(price+tf),"fees_pct":round(tf/price*100,2)}

    def compute_annual_taxes(self, dv, is_comm=False, patrimony=0, turnover=0):
        C=self.C; tib=dv*C["tib_rate"]
        tcl=turnover*C["tcl_rate"] if is_comm else 0
        ifi=dv*C["ifi_rate"] if patrimony>=C["ifi_threshold"] else 0
        return {"tib":round(tib),"tcl":round(tcl),"ifi":round(ifi),"total":round(tib+tcl+ifi)}

    def compute_capital_gains_tax(self, buy, sell, yrs):
        C=self.C; idx=buy*(1+C["cgt_index_per_year"])**yrs
        gain=max(0,sell-idx); rate=C["cgt_ge10"] if yrs>=10 else C["cgt_lt10"]
        cgt=gain*rate; wh=sell*C["cgt_withholding"]
        return {"sale_price":round(sell),"indexed_cost":round(idx),"taxable_gain":round(gain),
                "cgt_rate":rate,"cgt":round(cgt),"withholding":round(wh),
                "net_proceeds":round(sell-cgt)}

    def compute_rental_tax(self, gross):
        C=self.C; tax=gross*C["irpp_rental_flat"]
        return {"gross_rent":round(gross),"irpp":round(tax),"net_rent":round(gross-tax)}

    def sweep_holding_period(self, prop, profile):
        price=float(prop["price_numeric"]); ap=self.C["appreciation_national"]
        gr=self.C["gross_yield_national"]; is_new=profile.get("is_new_promoter",False)
        acq=self.compute_acquisition_costs(price,is_new); results=[]
        for yr in range(1,16):
            sale=price*(1+ap)**yr; cgt=self.compute_capital_gains_tax(price,sale,yr)
            rt=self.compute_rental_tax(price*gr); at=self.compute_annual_taxes(price)
            cfs=[-acq["total_cost"]]+[rt["net_rent"]-at["total"]]*yr
            cfs[-1]+=cgt["net_proceeds"]
            try: irr=float(npf.irr(cfs))*100; irr=irr if np.isfinite(irr) else 0
            except: irr=0
            results.append({"years":yr,"irr_pct":round(irr,2),"net_proceeds":cgt["net_proceeds"],
                             "cgt":cgt["cgt"],"cgt_rate":cgt["cgt_rate"]})
        return results

    def optuna_optimize(self, prop, n_trials=200):
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        C=self.C; price=float(prop["price_numeric"])
        def obj(trial):
            yr=trial.suggest_int("hold",1,15); ltv=trial.suggest_float("ltv",0.4,0.7)
            sc=trial.suggest_categorical("scenario",["rental","flip"])
            corp=trial.suggest_categorical("is_corp",[False,True])
            down=price*(1-ltv); mortg=price*ltv; mr=C["mortgage_rate_mid"]/12
            nmo=C["mortgage_max_years"]*12; mp=npf.pmt(mr,nmo,-mortg) if mortg>0 else 0
            sale=price*(1+C["appreciation_national"])**yr
            gross=price*C["gross_yield_national"]
            nr=gross*(1-(0.15 if corp else C["irpp_rental_flat"]))
            at=price*C["tib_rate"]; cgt_i=self.compute_capital_gains_tax(price,sale,yr)
            rem=abs(npf.pv(mr,max(nmo-yr*12,1),mp))
            cfs=[-down]+[(nr-at-mp*12 if sc=="rental" else -(at+mp*12))]*yr
            cfs[-1]+=cgt_i["net_proceeds"]-rem if sc=="flip" else 0
            try: irr=float(npf.irr(cfs))*100; return irr if np.isfinite(irr) else -999
            except: return -999
        study=optuna.create_study(direction="maximize",sampler=optuna.samplers.TPESampler(seed=42))
        study.optimize(obj,n_trials=n_trials,show_progress_bar=False)
        best=dict(study.best_params); best["best_irr_pct"]=round(study.best_value,2)
        return best

    def optimize_tax_structure(self, prop, profile):
        C=self.C; price=float(prop["price_numeric"])
        yr=profile.get("holding_period_years",5)
        gross=float(profile.get("rental_income",price*C["gross_yield_national"]))
        acq=self.compute_acquisition_costs(price,profile.get("is_new_promoter",False))
        at=self.compute_annual_taxes(price); rt=self.compute_rental_tax(gross)
        sale=price*(1+C["appreciation_national"])**yr
        cgt=self.compute_capital_gains_tax(price,sale,yr)
        sweep=self.sweep_holding_period(prop,profile)
        best_yr=max(sweep,key=lambda x:x["irr_pct"])
        opt=self.optuna_optimize(prop,n_trials=100)
        return {"acquisition_costs":acq,"annual_tax_burden":at,"rental_tax":rt,
                "capital_gains":cgt,"holding_period_sweep":sweep,
                "optimal_holding_years":best_yr["years"],"optimal_holding_irr":best_yr["irr_pct"],
                "optuna_best_params":opt,
                "cgt_cliff_note":f"Hold ≥10yr: CGT drops from {C['cgt_lt10']*100:.0f}% to {C['cgt_ge10']*100:.0f}%"}


# ═══════════════════════════════════════════════════════════════════════════
# C3 — RISK SCORING ENGINE
# ═══════════════════════════════════════════════════════════════════════════
class RiskScoringEngine:
    WEIGHTS = {"location_risk":0.30,"condition_risk":0.20,"liquidity_risk":0.20,
               "price_risk":0.15,"economic_risk":0.10,"regulatory_risk":0.05}
    GOV_RISK = {"tunis":0.20,"ariana":0.25,"ben arous":0.28,"manouba":0.40,
        "sousse":0.30,"monastir":0.32,"sfax":0.30,"nabeul":0.35,"hammamet":0.35,
        "bizerte":0.45,"beja":0.55,"jendouba":0.65,"kef":0.60,"siliana":0.60,
        "kairouan":0.55,"kasserine":0.70,"sidi bouzid":0.65,"gabes":0.50,
        "medenine":0.45,"tataouine":0.60,"tozeur":0.60,"kebili":0.65,
        "mahdia":0.40,"gafsa":0.55,"zaghouan":0.50}
    LIQ = {"Appartement a vendre":0.25,"Appartement a louer":0.35,
           "Maison a vendre":0.45,"Maison a louer":0.55,
           "Studio a vendre":0.30,"Studio a louer":0.40,
           "Villa a vendre":0.50,"Villa a louer":0.60,
           "Bureau a vendre":0.65,"Bureau a louer":0.70,
           "Local commercial a vendre":0.70,"Local commercial a louer":0.75,
           "Terrain a vendre":0.60}

    def __init__(self, df, tune=False):
        self.df=df; self.C=TUNISIA_CONSTANTS
        self._feat_cols=['price_numeric','surface_numeric','pieces','chambres','sallesdebain']
        self._ppm2=None; self._metrics={}
        self._if_model=None; self._rf_model=None; self._rf_feat_cols=[]
        self._X_train=None
        if tune:
            self._train(tune=True)

    def _get_ppm2(self):
        if self._ppm2 is None:
            s=self.df["surface_numeric"].replace(0,np.nan)
            self._ppm2=self.df["price_numeric"]/s
        return self._ppm2

    def _train(self, tune=True):
        fc=[c for c in self._feat_cols if c in self.df.columns]
        X_if=self.df[fc].astype(float).assign(price_per_m2=self._get_ppm2()).fillna(0)
        self._X_train=X_if
        best_cont=0.05
        if tune:
            best_sep=-1
            for cont in [0.02,0.05,0.08,0.10]:
                m=IsolationForest(n_estimators=200,contamination=cont,random_state=42)
                m.fit(X_if); scores=m.score_samples(X_if)
                sep=np.std(scores)/(np.max(scores)-np.min(scores)+1e-9)
                if sep>best_sep: best_cont,best_sep=cont,sep
        self._if_model=IsolationForest(n_estimators=200,contamination=best_cont,random_state=42)
        self._if_model.fit(X_if)

        ppm2=self._get_ppm2()
        type_med=ppm2.groupby(self.df["Type"]).transform("median")
        risky=((ppm2>3*type_med)|self.df["surface_numeric"].isna()).astype(int).fillna(0)
        X_rf=self.df[fc].astype(float).fillna(0)
        if "Type" in self.df.columns:
            le=LabelEncoder()
            X_rf["type_enc"]=le.fit_transform(self.df["Type"].fillna("unknown")).astype(float)
        X_rf=X_rf.fillna(0)
        self._rf_feat_cols=X_rf.columns.tolist()
        Xtr,Xte,ytr,yte=train_test_split(X_rf,risky,test_size=0.2,random_state=42,stratify=risky)
        rf_params={"n_estimators":200,"max_depth":10,"min_samples_split":5}
        self._rf_model=RandomForestClassifier(**rf_params,class_weight="balanced",
                                               random_state=42,n_jobs=-1)
        self._rf_model.fit(Xtr,ytr)

    def _if_score(self, prop):
        if self._if_model is None or self._X_train is None: return 50.0
        row={c:float(prop.get(c,0) or 0) for c in self._feat_cols if c in self._X_train.columns}
        row["price_per_m2"]=row.get("price_numeric",0)/max(row.get("surface_numeric",1),1)
        X=pd.DataFrame([row])[self._X_train.columns].fillna(0).astype(float)
        raw=self._if_model.score_samples(X)[0]
        tr=self._if_model.score_samples(self._X_train)
        s=100*(1-(raw-tr.min())/(tr.max()-tr.min()+1e-9))
        return float(np.clip(s,0,100))

    def _rf_score(self, prop):
        if self._rf_model is None: return 50.0
        row={c:float(prop.get(c,0) or 0) for c in self._rf_feat_cols}
        if "type_enc" in self._rf_feat_cols:
            le=LabelEncoder().fit(self.df["Type"].fillna("unknown"))
            try: row["type_enc"]=float(le.transform([prop.get("Type","unknown")])[0])
            except: row["type_enc"]=0.0
        X=pd.DataFrame([row])[self._rf_feat_cols].fillna(0).astype(float)
        return float(self._rf_model.predict_proba(X)[0][1]*100)

    def calculate_overall_risk(self, prop):
        C=self.C; loc=str(prop.get("Adresse","")).lower()
        gov=next((v for k,v in self.GOV_RISK.items() if k in loc),0.50)
        lr=gov
        for a,adj in [("parking",-0.03),("ascenseur",-0.02),("balcon_terrasse",-0.01),("neuf",-0.05)]:
            if prop.get(a,0)==1: lr+=adj
        lr=float(np.clip(lr,0,1))
        cr=0.30
        if prop.get("neuf",0)==1: cr-=0.20
        for a in ["climatisation","chauffage","balcon_terrasse"]:
            if prop.get(a,0)==1: cr-=0.04
        if pd.isna(prop.get("surface_numeric")): cr+=0.10
        cr=float(np.clip(cr,0,1))
        liq=self.LIQ.get(prop.get("Type",""),0.60)
        price=float(prop.get("price_numeric",0) or 0)
        if price>500_000: liq+=0.15
        elif price<100_000: liq-=0.10
        if any(r in loc for r in ["tunis","ariana","sousse"]): liq-=0.08
        liq=float(np.clip(liq,0,1))
        sim=self.df[self.df["Type"]==prop.get("Type","")]
        if len(sim)>5 and price>0:
            med=sim["price_numeric"].median(); dev=(price-med)/(med+1e-9)
            pr=0.8 if dev>0.3 else (0.3 if dev<-0.2 else 0.5)
        else: pr=0.55
        eco=float(np.clip((C["inflation_cpi"]+C["bcт_tmm"])/2,0,1))
        rr=0.35
        if "zone touristique" in loc: rr+=0.15
        rr=float(np.clip(rr,0,1))
        comp={"location_risk":lr,"condition_risk":cr,"liquidity_risk":liq,
              "price_risk":float(pr),"economic_risk":eco,"regulatory_risk":rr}
        overall=sum(self.WEIGHTS[k]*v for k,v in comp.items())
        ifs=self._if_score(prop); rfs=self._rf_score(prop)
        lvl="Low" if overall<0.30 else "Medium" if overall<0.60 else "High"
        flags=[]
        if lr>0.60: flags.append("High location risk")
        if cr>0.50: flags.append("Property condition concerns")
        if liq>0.65: flags.append("Low market liquidity")
        if float(pr)>0.70: flags.append("Overpriced vs type median")
        return {"overall_risk_score":round(overall,3),"risk_level":lvl,
                "component_scores":comp,"isolation_forest_100":round(ifs,1),
                "random_forest_100":round(rfs,1),"consensus_score_100":round((ifs+rfs)/2,1),
                "risk_flags":flags,
                "mitigation":[s for s in [
                    "Negotiate price." if lr>0.6 else None,
                    "Budget renovation." if cr>0.5 else None,
                    "Plan ≥5yr hold." if liq>0.65 else None,
                    "Submit below ask." if float(pr)>0.7 else None] if s]}


# ═══════════════════════════════════════════════════════════════════════════
# C4 — PORTFOLIO DIVERSIFICATION ADVISOR
# ═══════════════════════════════════════════════════════════════════════════
class PortfolioDiversificationAdvisor:
    def __init__(self, df):
        self.df=df.copy(); self.C=TUNISIA_CONSTANTS
        self._clusters_kmeans=None; self._kmeans_model=None
        self._kmeans_scaler=None; self._cluster_feats=[]
        self._hier_labels=[]; self._hier_clusters=None; self._metrics={}
        self._build()

    def _build(self):
        df=self.df.copy()
        if "Type" in df.columns and "type_enc" not in df.columns:
            le=LabelEncoder()
            df["type_enc"]=le.fit_transform(df["Type"].fillna("unknown")).astype(float)
            self.df["type_enc"]=df["type_enc"]
        df["_gov"]=df["Adresse"].fillna("").str.split(",").str[0].str.strip()
        df["_ret"]=self.C["gross_yield_national"]
        pivot=df.groupby(["Type","_gov"])["_ret"].mean().unstack(fill_value=0)
        if pivot.shape[1]>=2:
            corr=pivot.T.corr().fillna(0); dist=np.clip(1-corr.values,0,None)
            np.fill_diagonal(dist,0); cond=squareform(dist)
            Z=linkage(cond,method="ward")
            self._hier_clusters=fcluster(Z,t=4,criterion="maxclust")
            self._hier_labels=corr.index.tolist()
        fc=["price_numeric","surface_numeric","pieces","chambres","sallesdebain"]
        if "type_enc" in df.columns: fc.append("type_enc")
        avail=[c for c in fc if c in df.columns]
        X=df[avail].astype(float).fillna(df[avail].astype(float).median())
        for col in X.columns:
            lo,hi=X[col].quantile(0.01),X[col].quantile(0.99)
            X[col]=X[col].clip(lo,hi)
        scaler=StandardScaler(); X_sc=scaler.fit_transform(X)
        best_k,best_sil=5,-1.0
        for k in range(3,11):
            km=KMeans(n_clusters=k,random_state=42,n_init=10)
            lbl=km.fit_predict(X_sc); sil=silhouette_score(X_sc,lbl)
            if sil>best_sil: best_k,best_sil=k,sil
        km_final=KMeans(n_clusters=best_k,random_state=42,n_init=10)
        self._clusters_kmeans=km_final.fit_predict(X_sc)
        self._kmeans_model=km_final; self._kmeans_scaler=scaler
        self._cluster_feats=X.columns.tolist()
        self.df["_kmeans_cluster"]=self._clusters_kmeans
        self._metrics={"best_k":best_k,"best_sil":round(best_sil,4)}

    def _get_cluster(self, prop):
        if self._kmeans_model is None: return -1
        row={c:float(prop.get(c,0) or 0) for c in self._cluster_feats}
        X=pd.DataFrame([row])[self._cluster_feats].fillna(0).astype(float)
        return int(self._kmeans_model.predict(self._kmeans_scaler.transform(X))[0])

    def analyze_current_portfolio(self, portfolio):
        if not portfolio: return {"error":"Empty"}
        tv=sum(float(p.get("price_numeric",0) or 0) for p in portfolio)
        types=set(p.get("Type","") for p in portfolio)
        locs=set(str(p.get("Adresse","")).split(",")[0] for p in portfolio)
        div=min(len(types)*12+len(locs)*9+len(portfolio)*2,100)
        herf=sum((float(p.get("price_numeric",0) or 0)/tv)**2 for p in portfolio) if tv>0 else 1
        return {"total_value":tv,"diversification_score":div,"herfindahl":herf,
                "types":list(types),"locations":list(locs)}

    def recommend_diversification(self, portfolio, budget=500_000):
        if not portfolio: return {"error":"Empty"}
        cur=self._get_cluster(portfolio[0]); recs=[]
        for cl in sorted(set(self._clusters_kmeans)):
            if cl==cur: continue
            mask=(self.df["_kmeans_cluster"]==cl)&(self.df["price_numeric"]<=budget)&(self.df["price_numeric"]>0)
            cands=self.df[mask]
            if len(cands)==0: continue
            s=cands.sample(1,random_state=42).iloc[0]
            recs.append({"cluster":int(cl),"Type":s.get("Type",""),"Adresse":s.get("Adresse",""),
                          "price":float(s.get("price_numeric",0)),
                          "reason":f"Cluster {cl} diversifies from {cur}"})
        return {"current_cluster":cur,"candidates":recs[:5]}


# ═══════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════
class InvestmentScenarioGenerator:
    def __init__(self, df, sim, tax, risk, port):
        self.df=df; self.C=TUNISIA_CONSTANTS
        self.simulator=sim; self.tax_optimizer=tax
        self.risk_engine=risk; self.portfolio_advisor=port

    def generate_investment_scenario(self, prop=None, profile=None):
        if prop is None:
            valid=self.df[self.df["price_numeric"].notna() &
                          self.df["Type"].str.contains("vendre",case=False,na=False) &
                          (self.df["price_numeric"]>50_000)]
            if valid.empty: valid=self.df[self.df["price_numeric"].notna()]
            prop=valid.sample(1,random_state=42).iloc[0].to_dict()
        if profile is None:
            profile={"budget":300_000,"holding_period_years":5,"rental_income":0,
                     "first_time_buyer":True,"is_new_promoter":False,"risk_tolerance":"medium"}
        if isinstance(profile.get("rental_income"),bool): profile["rental_income"]=0
        yr=profile["holding_period_years"]

        rental=self.simulator.calculate_rental_yield(prop)
        if profile["rental_income"]==0: profile["rental_income"]=rental["gross_annual_rent"]
        xgb_exit=self.simulator.predict_exit_price(prop,yr)
        mc_r=self.simulator.monte_carlo_npv(prop,yr,scenario="rental")
        mc_f=self.simulator.monte_carlo_npv(prop,yr,scenario="flip")
        roi_r=self.simulator.calculate_roi(prop,yr,scenario="rental")
        roi_f=self.simulator.calculate_roi(prop,yr,scenario="flip")

        # Select primary MC scenario by property type:
        # rentals → rental scenario; for-sale → exit/flip scenario (buyer will eventually sell)
        _type_l = str(prop.get("Type","")).lower()
        if "louer" in _type_l:
            _primary_mc     = mc_r
            _scenario_label = "locatif"
        else:
            _primary_mc     = mc_f
            _scenario_label = "revente"

        profile["expected_capital_gain"]=max(0,xgb_exit-float(prop.get("price_numeric",0)))
        tax=self.tax_optimizer.optimize_tax_structure(prop,profile)
        risk=self.risk_engine.calculate_overall_risk(prop)
        port_a=self.portfolio_advisor.analyze_current_portfolio([prop])
        rem=max(0,profile["budget"]-float(prop.get("price_numeric",0)))
        port_r=self.portfolio_advisor.recommend_diversification([prop],budget=rem)

        verdict=self._verdict(rental,risk,roi_r,mc_rental=_primary_mc)

        # Financial-only language — no modeling/algorithmic terms
        _risk_labels = {
            "location_risk":"Risque localisation","condition_risk":"État du bien",
            "liquidity_risk":"Liquidité","price_risk":"Risque de prix",
            "economic_risk":"Risque économique","regulatory_risk":"Risque réglementaire",
        }
        explanations = {
            "rendement_locatif":  f"Rendement locatif brut {rental['gross_yield']:.2f}% (données marché TN 2025)",
            "rentabilite_levier": f"Taux de rentabilité annuel {roi_r['irr_percent']:.2f}% vs taux directeur BCT {self.C['bcт_tmm']*100:.2f}%",
            "composantes_risque": {
                _risk_labels.get(k,k): f"{float(v)*100:.0f}%"
                for k,v in risk["component_scores"].items()
            },
            "fiscalite": (
                f"Taxe sur plus-value: {tax['capital_gains']['cgt_rate']*100:.0f}% "
                f"(Code IRPP-IS 2024) · Impôt locatif: {self.C['irpp_rental_flat']*100:.0f}%"
            ),
            "duree_conseille": (
                f"{tax['optimal_holding_years']} ans recommandés pour maximiser "
                "la rentabilité après impôts"
            ),
            "probabilite_gain": (
                f"{_primary_mc['prob_positive']*100:.0f}% de probabilité de gain net positif "
                f"sur {_primary_mc['n_sims']:,} projections (scénario {_scenario_label})"
            ),
        }

        features_list = [k.replace("_"," ") for k in
                         ["meuble","neuf","parking","ascenseur","balcon_terrasse",
                          "climatisation","chauffage","jardin","piscine"]
                         if prop.get(k,0)==1]

        return {
            "property":{"type":prop.get("Type",""),"location":prop.get("Adresse",""),
                        "price":prop.get("price_numeric",0),"surface":prop.get("surface_numeric",""),
                        "features":features_list},
            "simulator":{"xgb_exit_price":xgb_exit,"mc_rental":mc_r,"mc_flip":mc_f,
                          "mc_primary":_primary_mc,"primary_scenario":_scenario_label,
                          "roi_rental":roi_r,"roi_flip":roi_f,"rental_yield":rental},
            "tax":tax, "risk":risk,
            "portfolio":{"analysis":port_a,"recommendations":port_r},
            "verdict":verdict, "explanations":explanations,
        }

    def _verdict(self, rental, risk, roi, mc_rental=None):
        C=self.C; hurdle=C["bcт_tmm"]*100; irr=roi["irr_percent"]
        gy=rental["gross_yield"]; rl=risk["risk_level"]
        score=0; ins=[]

        # Yield component — 0-25 pts
        if gy>C["gross_yield_tunis"]*100:   score+=25; ins.append(f"Yield {gy:.1f}%>Tunis avg")
        elif gy>C["gross_yield_national"]*100: score+=18; ins.append(f"Yield {gy:.1f}%>national avg")
        elif gy>4.0:                         score+=10; ins.append(f"Yield {gy:.1f}% moderate")
        else:                                score+=3;  ins.append(f"Yield {gy:.1f}% below avg")

        # Risk component — 0-25 pts
        if rl=="Low":    score+=25; ins.append("Low risk profile")
        elif rl=="Medium": score+=15; ins.append("Medium risk")
        else:            score+=5;  ins.append("High risk")

        # IRR vs BCT hurdle — 0-30 pts
        if irr>hurdle+5:       score+=30; ins.append(f"IRR {irr:.1f}% well above hurdle")
        elif irr>hurdle+2:     score+=22; ins.append(f"IRR {irr:.1f}% above hurdle")
        elif irr>hurdle:       score+=15; ins.append(f"IRR {irr:.1f}% marginally above hurdle")
        elif irr>0:            score+=7;  ins.append(f"IRR {irr:.1f}%<hurdle {hurdle:.2f}%")
        else:                             ins.append(f"Negative/zero IRR ({irr:.1f}%)")

        # Monte Carlo NPV probability — 0-20 pts
        if mc_rental:
            prob=mc_rental.get("prob_positive",0)
            if prob>0.60:   score+=20; ins.append(f"P(NPV>0)={prob*100:.0f}% — strong")
            elif prob>0.40: score+=12; ins.append(f"P(NPV>0)={prob*100:.0f}% — moderate")
            elif prob>0.20: score+=5;  ins.append(f"P(NPV>0)={prob*100:.0f}% — weak")
            else:                      ins.append(f"P(NPV>0)={prob*100:.0f}% — very weak")

        rec="STRONG BUY" if score>=75 else "CONSIDER" if score>=50 else "CAUTIOUS" if score>=30 else "AVOID"
        return {"score":score,"recommendation":rec,"key_insights":ins,"bct_hurdle_used":hurdle}
