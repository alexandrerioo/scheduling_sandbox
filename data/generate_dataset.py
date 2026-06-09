"""
Génère un jeu de données synthétique d'opérations de production (atelier flow-shop)
pour l'exercice DS/ML de l'entretien Oplit.

Grain : une ligne = un OF = une opération (1 OF = 1 opération, pas de gamme multi-étapes).
Cible  : la durée réelle de l'opération, **non pré-calculée** -> à dériver des timestamps
         (actual_end_ts - actual_start_ts). Volontairement absente du fichier.

Le processus génératif est volontairement :
  - piloté par des **caractéristiques d'article** observables (diametre, matiere) qui
    sont de vraies features prédictives, plus une feature **leurre** (couleur) sans effet ;
  - assorti de plusieurs OF par article -> l'agrégation par article a du sens (baseline) ;
  - riche en interactions (article x type machine x quantité) -> les arbres battent
    un modèle linéaire, mais ça reste interprétable ;
  - sujet à une dérive temporelle (courbe d'apprentissage, machine introduite en
    cours de période, ralentissement d'août) -> un split aléatoire fuite, un split
    temporel est obligatoire ;
  - bruité et "sale" (valeurs manquantes, doublons, typos, outliers de panne...) ->
    le candidat doit nettoyer ;
  - assorti de colonnes "pièges" qui fuitent la cible (actual_end_ts, record_created_ts...).

Reproductible : seed=42, sous-générateurs via rng.spawn() par étape pour que
l'ajout de lignes plus tard ne rebatte pas les étapes précédentes.

Usage : python data/generate_dataset.py
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Constantes du monde
# --------------------------------------------------------------------------- #
SEED = 42
T0 = datetime(2024, 1, 1)
N_DAYS = 244  # 2024-01-01 -> 2024-08-31
N_ARTICLES = 40
N_OFS = 6000  # 1 OF = 1 opération -> ~150 OF par article (agrégation pertinente)
WORK_HOURS = (6, 22)  # opérations planifiées dans la journée

MCH12_BORN_DAY = 120  # MCH-12 (ROBOT_CELL) n'existe pas avant ce jour
BREAKDOWN_MACHINE = "MCH-04"
BREAKDOWN_START_DAY = 80
BREAKDOWN_LEN_DAYS = 14

# vitesse par type machine (plus petit = plus rapide)
SPEED = {"CNC_FAST": 0.70, "CNC_STD": 1.00, "MANUAL": 1.45, "ROBOT_CELL": 0.85}

# familles d'articles : base (min/unité), setup (min), types machine autorisés
FAMILIES = {
    "Usinage":    {"base": 1.2, "setup": 15, "types": ["CNC_FAST", "CNC_STD"]},
    "Soudure":    {"base": 2.0, "setup": 25, "types": ["MANUAL", "ROBOT_CELL"]},
    "Assemblage": {"base": 0.8, "setup": 10, "types": ["MANUAL", "ROBOT_CELL", "CNC_STD"]},
    "Finition":   {"base": 0.5, "setup": 8,  "types": ["MANUAL", "CNC_FAST"]},
}

# --- caractéristiques d'article ---
# matiere : VRAIE feature (multiplie la difficulté d'usinage)
MATERIALS = {
    "Aluminium":     0.80,
    "Acier":         1.00,
    "Inox":          1.25,
    "Titane":        1.60,
}
# couleur : LEURRE (aucun effet sur la durée -> doit ressortir comme inutile)
COLORS = ["Rouge", "Bleu", "Vert", "Noir", "Gris", "Jaune"]
DIAM_REF = 50.0   # mm de référence
DIAM_ALPHA = 0.55  # exposant : la durée croît avec le diamètre, sous-linéairement

# 12 machines -> 4 types ; MCH-12 naît au jour 120
MACHINES = {
    "MCH-01": "CNC_FAST", "MCH-02": "CNC_FAST",
    "MCH-03": "CNC_STD",  "MCH-04": "CNC_STD",  "MCH-05": "CNC_STD",
    "MCH-06": "MANUAL",   "MCH-07": "MANUAL",   "MCH-08": "MANUAL",
    "MCH-09": "ROBOT_CELL", "MCH-10": "ROBOT_CELL", "MCH-11": "ROBOT_CELL",
    "MCH-12": "ROBOT_CELL",
}
TYPE_TO_MACHINES = {}
for _m, _t in MACHINES.items():
    TYPE_TO_MACHINES.setdefault(_t, []).append(_m)


# --------------------------------------------------------------------------- #
# Dérive temporelle
# --------------------------------------------------------------------------- #
def learn(machine_id: str, t: int) -> float:
    """Courbe d'apprentissage : on devient plus efficace avec le temps."""
    if machine_id == "MCH-12":
        # machine neuve -> démarrage plus lent puis apprentissage plus rapide
        return 1.0 + 0.30 * np.exp(-(t - MCH12_BORN_DAY) / 20.0)
    return 1.0 + 0.20 * np.exp(-t / 35.0)


def season(date: datetime) -> float:
    """Ralentissement estival (août) : effectifs réduits, congés."""
    return 1.10 if date.month == 8 else 1.0


# --------------------------------------------------------------------------- #
# Entités (tirées une fois)
# --------------------------------------------------------------------------- #
def build_articles(rng) -> pd.DataFrame:
    """Un article = une référence + ses caractéristiques (diametre, matiere, couleur).

    diametre et matiere pilotent la difficulté latente (vraies features) ;
    couleur est un leurre. Plusieurs OF référenceront le même article.
    """
    fam_names = list(FAMILIES.keys())
    materials = list(MATERIALS.keys())
    rows = []
    for i in range(N_ARTICLES):
        fam = fam_names[i % len(fam_names)]
        f = FAMILIES[fam]
        letter = fam[0].upper()

        diameter = float(round(rng.uniform(8.0, 200.0), 1))     # mm
        material = materials[int(rng.integers(0, len(materials)))]
        color = COLORS[int(rng.integers(0, len(COLORS)))]        # leurre

        diam_factor = (diameter / DIAM_REF) ** DIAM_ALPHA
        mat_factor = MATERIALS[material]

        # complexité (min/unité) et setup (min) DÉRIVÉS des caractéristiques
        # + petit aléa propre à l'article (mais features ~prédictives)
        c_a = f["base"] * diam_factor * mat_factor * rng.lognormal(0.0, 0.12)
        s_a = f["setup"] * (0.6 + 0.4 * diam_factor) * rng.lognormal(0.0, 0.12)

        rows.append({
            "article_id": i,
            "article_ref": f"ART-{letter}{i:02d}",  # référence canonique
            "article_family": fam,
            "diameter_mm": diameter,
            "material": material,
            "color": color,
            "C_a": c_a,    # complexité min/unité (latente, dérivée des features)
            "S_a": s_a,    # setup min (latent, dérivé des features)
            "types": f["types"],
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Génération des opérations (1 OF = 1 opération)
# --------------------------------------------------------------------------- #
def sample_quantity(rng) -> int:
    # mélange de petits lots (dominés par le setup) et gros lots (dominés par la cadence)
    if rng.random() < 0.70:
        return int(rng.integers(5, 81))
    return int(rng.integers(100, 401))


def per_unit_with_kink(per_unit: float, q: int) -> float:
    # économie d'échelle : au-delà de 100 unités, légère remise sur la cadence
    eff_q = q if q <= 100 else 100 + 0.92 * (q - 100)
    return per_unit * eff_q


def datetime_for(day: int, rng) -> datetime:
    hour = int(rng.integers(*WORK_HOURS))
    return T0 + timedelta(days=day, hours=hour, minutes=int(rng.integers(0, 60)))


def generate_operations(rng, articles: pd.DataFrame) -> pd.DataFrame:
    art_records = articles.to_dict("records")

    rows = []
    for of_idx in range(N_OFS):
        art = art_records[rng.integers(0, N_ARTICLES)]
        of_day = int(rng.integers(0, N_DAYS))
        of_id = f"OF-2024-{of_idx:05d}"

        planned_start = datetime_for(of_day, rng)
        t = (planned_start - T0).days

        mtype = art["types"][int(rng.integers(0, len(art["types"])))]
        # machines de ce type existantes à la date t (MCH-12 naît au jour 120)
        candidates = [m for m in TYPE_TO_MACHINES[mtype]
                      if not (m == "MCH-12" and t < MCH12_BORN_DAY)]
        machine_id = candidates[int(rng.integers(0, len(candidates)))]
        q = sample_quantity(rng)

        # --- temps réel latent ---
        setup = art["S_a"] * SPEED[mtype]
        per_unit = art["C_a"] * SPEED[mtype]
        base = setup + per_unit_with_kink(per_unit, q)
        drift = learn(machine_id, t) * season(planned_start)

        # fenêtre de panne sur MCH-04
        breakdown = 1.0
        if (machine_id == BREAKDOWN_MACHINE
                and BREAKDOWN_START_DAY <= t < BREAKDOWN_START_DAY + BREAKDOWN_LEN_DAYS):
            breakdown = rng.uniform(5.0, 12.0)

        mu = base * drift * breakdown
        true_time = mu * rng.lognormal(0.0, 0.12)  # bruit multiplicatif ~12%

        start_jitter = rng.exponential(8.0)  # min
        actual_start = planned_start + timedelta(minutes=start_jitter)
        actual_end = actual_start + timedelta(minutes=true_time)

        scrap_qty = int(rng.poisson(0.3 * (true_time / max(mu, 1e-6))))  # plus long -> + de rebut
        record_created = actual_end + timedelta(minutes=rng.uniform(0.5, 5.0))

        rows.append({
            "of_id": of_id,
            "article_ref": art["article_ref"],
            "article_family": art["article_family"],
            "diameter_mm": art["diameter_mm"],
            "material": art["material"],
            "color": art["color"],
            "quantity": q,
            "machine_id": machine_id,
            "machine_type": mtype,
            "planned_start_ts": planned_start,
            "actual_start_ts": actual_start,
            "actual_end_ts": actual_end,
            "status": "done",
            "scrap_qty": scrap_qty,
            "record_created_ts": record_created,
        })

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Injection des problèmes de qualité de données
# --------------------------------------------------------------------------- #
def corrupt(rng, df: pd.DataFrame) -> pd.DataFrame:
    df = df.reset_index(drop=True)
    n = len(df)

    # 1) Durées négatives / nulles (~1%) : décalage d'horloge -> la durée dérivée
    #    des timestamps devient <= 0 (le candidat doit filtrer)
    bad = rng.choice(n, size=int(0.01 * n), replace=False)
    for i in bad:
        if rng.random() < 0.5:
            df.loc[i, "actual_end_ts"] = df.loc[i, "actual_start_ts"] - timedelta(minutes=float(rng.integers(1, 30)))
        else:
            df.loc[i, "actual_end_ts"] = df.loc[i, "actual_start_ts"]

    # 2) actual_end_ts manquant (~4%) : opérations en cours / abandonnées
    #    -> la cible (dérivée) est inconnue
    miss = rng.choice(n, size=int(0.04 * n), replace=False)
    df.loc[miss, "actual_end_ts"] = pd.NaT
    df.loc[miss, "status"] = rng.choice(["running", "aborted"], size=len(miss))

    # 3) Typos / incohérences sur article_ref (~10% des lignes, sous-ensemble d'articles)
    refs = df["article_ref"].unique()
    dirty_refs = set(rng.choice(refs, size=max(1, len(refs) // 3), replace=False))
    dirty_mask = df["article_ref"].isin(dirty_refs) & (rng.random(n) < 0.30)
    dirty_idx = df.index[dirty_mask].tolist()
    for i in dirty_idx:
        ref = df.loc[i, "article_ref"]
        choice = rng.integers(0, 4)
        if choice == 0:
            df.loc[i, "article_ref"] = ref.lower()
        elif choice == 1:
            df.loc[i, "article_ref"] = f"  {ref} "          # espaces parasites
        elif choice == 2:
            df.loc[i, "article_ref"] = ref + "-MM"           # suffixe d'unité parasite
        else:
            df.loc[i, "article_ref"] = ref.replace("-", "")  # tiret manquant

    # 4) Formats de date mélangés : les lignes d'une machine en JJ/MM/AAAA HH:MM (str)
    #    (fait sur une copie écrite plus tard -> on marque les lignes, conversion au write)
    df["_fr_dates"] = df["machine_id"] == "MCH-07"

    # 5) Doublons (~1.5%) : exacts + quelques quasi-doublons (record_created_ts différent)
    dup_idx = rng.choice(n, size=int(0.015 * n), replace=False)
    dups = df.loc[dup_idx].copy()
    near = rng.random(len(dups)) < 0.3
    dups.loc[near, "record_created_ts"] = dups.loc[near, "record_created_ts"] + timedelta(minutes=1)
    df = pd.concat([df, dups], ignore_index=True)

    return df


# --------------------------------------------------------------------------- #
# Écriture
# --------------------------------------------------------------------------- #
TS_COLS = ["planned_start_ts", "actual_start_ts", "actual_end_ts", "record_created_ts"]


def format_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """Écrit les timestamps en ISO, sauf les lignes marquées (_fr_dates) en JJ/MM/AAAA HH:MM."""
    df = df.copy()
    fr = df["_fr_dates"].to_numpy()
    for col in TS_COLS:
        s = pd.to_datetime(df[col], errors="coerce")
        iso = s.dt.strftime("%Y-%m-%d %H:%M:%S")
        frs = s.dt.strftime("%d/%m/%Y %H:%M")
        df[col] = np.where(fr, frs, iso)
        df[col] = df[col].where(s.notna(), "")  # NaT -> chaîne vide
    return df.drop(columns=["_fr_dates"])


def main() -> None:
    root = np.random.default_rng(SEED)
    s_articles, s_ops, s_corrupt = root.spawn(3)

    articles = build_articles(s_articles)
    df = generate_operations(s_ops, articles)
    df = corrupt(s_corrupt, df)

    # ordre des colonnes (figé)
    cols = ["of_id", "article_ref", "article_family",
            "diameter_mm", "material", "color", "quantity",
            "machine_id", "machine_type",
            "planned_start_ts", "actual_start_ts", "actual_end_ts",
            "status", "scrap_qty", "record_created_ts", "_fr_dates"]
    df = df[cols]
    df = format_timestamps(df)

    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, "operations_raw.csv")
    df.to_csv(out_path, index=False)

    # --- résumé ---
    print(f"Écrit : {out_path}")
    print(f"Lignes : {len(df)}  |  OF : {df['of_id'].nunique()}")
    print(f"Références article distinctes (surface) : {df['article_ref'].nunique()} "
          f"(canoniques attendues : {N_ARTICLES})")
    print(f"OF moyens par article (canonique) : {N_OFS / N_ARTICLES:.0f}")
    print(f"actual_end_ts manquants : {(df['actual_end_ts'] == '').sum()}")
    print(f"Période : {df['planned_start_ts'].min()} -> {df['planned_start_ts'].max()}")


if __name__ == "__main__":
    main()
