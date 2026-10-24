"""Charge les CSV dans SQLite, exécute les requêtes de sql/analyses.sql
et produit les résultats, les graphiques, le rapport Excel et les données
du tableau de bord.

Usage : python src/analyze.py   (après src/extract.py)
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
RES = ROOT / "results"
FIG = ROOT / "figures"
DOCS = ROOT / "docs"

# Palette (validée daltonisme) et encre
BLEU, ORANGE, VERT_EAU, JAUNE, ROUGE = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e34948"
ENCRE, ENCRE_2, MUET, GRILLE, AXE, FOND = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
SOURCE = "Source : HCP, notes sur la situation du marché du travail (T2 et T3 2025)"


# ------------------------------------------------------------------ base SQL --
def construire_base() -> sqlite3.Connection:
    db = PROC / "chomage.db"
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    con.executescript((ROOT / "sql" / "schema.sql").read_text(encoding="utf-8"))
    for table in ("national", "regions"):
        df = pd.read_csv(PROC / f"{table}.csv")
        df.to_sql(table, con, if_exists="append", index=False)
    con.commit()
    return con


def requetes() -> dict[str, str]:
    texte = (ROOT / "sql" / "analyses.sql").read_text(encoding="utf-8")
    blocs = re.split(r"^-- name: (\w+)\s*$", texte, flags=re.M)
    return {nom: sql.strip() for nom, sql in zip(blocs[1::2], blocs[2::2])}


def periodes(con) -> tuple[str, str]:
    derniere = con.execute("SELECT MAX(periode) FROM regions").fetchone()[0]
    annee, trim = derniere.split("-")
    return derniere, f"{int(annee) - 1}-{trim}"


def libelle_periode(p: str) -> str:
    annee, t = p.split("-T")
    return f"T{t} {annee}"


# --------------------------------------------------------------- graphiques --
def style(ax, titre: str, sous_titre: str = "") -> None:
    ax.set_facecolor(FOND)
    for cote in ("top", "right", "left"):
        ax.spines[cote].set_visible(False)
    ax.spines["bottom"].set_color(AXE)
    ax.tick_params(colors=ENCRE_2, labelsize=10, length=0)
    ax.figure.text(0.02, 0.97, titre, fontsize=14, fontweight="bold", color=ENCRE, va="top")
    if sous_titre:
        ax.figure.text(0.02, 0.915, sous_titre, fontsize=10.5, color=ENCRE_2, va="top")
    ax.figure.text(0.02, 0.02, SOURCE, fontsize=8.5, color=MUET)


def fig_classement(df: pd.DataFrame, national: float, periode: str) -> None:
    d = df.sort_values("taux_chomage")
    fig, ax = plt.subplots(figsize=(9, 5.6), facecolor=FOND)
    fig.subplots_adjust(left=0.27, right=0.95, top=0.84, bottom=0.1)
    barres = ax.barh(d["region"], d["taux_chomage"], color=BLEU, height=0.62)
    ax.axvline(national, color=ENCRE_2, lw=1.2, ls=(0, (4, 3)))
    ax.text(national + 0.2, len(d) - 0.35, f"Moyenne nationale : {national:.1f} %".replace(".", ","),
            color=ENCRE_2, fontsize=9.5)
    for b, v in zip(barres, d["taux_chomage"]):
        ax.text(v + 0.25, b.get_y() + b.get_height() / 2, f"{v:.1f} %".replace(".", ","),
                va="center", fontsize=9.5, color=ENCRE)
    ax.set_xlim(0, d["taux_chomage"].max() * 1.15)
    ax.xaxis.set_visible(False)
    style(ax, f"Taux de chômage par région, {libelle_periode(periode)}",
          "L'Oriental et les régions du Sud dépassent 21 %, deux fois Tanger et Marrakech")
    fig.savefig(FIG / "1_chomage_par_region.png", dpi=150)
    plt.close(fig)


def fig_evolution(df: pd.DataFrame, periode: str, an_avant: str) -> None:
    d = df[df["region"] != "Ensemble"].sort_values("variation_points", ascending=False)
    fig, ax = plt.subplots(figsize=(9, 5.6), facecolor=FOND)
    fig.subplots_adjust(left=0.27, right=0.95, top=0.84, bottom=0.1)
    couleurs = [ROUGE if v > 0 else BLEU for v in d["variation_points"]]
    barres = ax.barh(d["region"], d["variation_points"], color=couleurs, height=0.62)
    ax.axvline(0, color=AXE, lw=1)
    for b, v in zip(barres, d["variation_points"]):
        decal = 0.08 if v >= 0 else -0.08
        ax.text(v + decal, b.get_y() + b.get_height() / 2, f"{v:+.1f} pt".replace(".", ","),
                va="center", ha="left" if v >= 0 else "right", fontsize=9.5, color=ENCRE)
    lim = d["variation_points"].abs().max() * 1.35
    ax.set_xlim(-lim, lim)
    ax.xaxis.set_visible(False)
    style(ax, f"Évolution du chômage en un an ({libelle_periode(an_avant)} → {libelle_periode(periode)})",
          "En points de pourcentage. Bleu : baisse ; rouge : hausse. Seule Rabat-Salé-Kénitra progresse nettement")
    fig.savefig(FIG / "2_evolution_par_region.png", dpi=150)
    plt.close(fig)


def fig_groupes(df: pd.DataFrame, periode: str) -> None:
    d = df.copy()
    fig, ax = plt.subplots(figsize=(9, 5.6), facecolor=FOND)
    fig.subplots_adjust(left=0.08, right=0.97, top=0.80, bottom=0.17)
    x = range(len(d))
    larg = 0.38
    b1 = ax.bar([i - larg / 2 - 0.01 for i in x], d["urbain"], larg, color=BLEU, label="Urbain")
    b2 = ax.bar([i + larg / 2 + 0.01 for i in x], d["rural"], larg, color=ORANGE, label="Rural")
    for barres in (b1, b2):
        for b in barres:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.6,
                    f"{b.get_height():.0f}", ha="center", fontsize=9, color=ENCRE)
    ax.set_xticks(list(x))
    ax.set_xticklabels(d["categorie"].str.replace(" ans", "\nans").str.replace(" diplômés", "\ndiplômés"),
                       fontsize=9.5)
    ax.yaxis.grid(True, color=GRILLE, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_ylabel("Taux de chômage (%)", color=ENCRE_2)
    ax.legend(frameon=False, loc="upper right", fontsize=10, labelcolor=ENCRE_2)
    style(ax, f"Qui est au chômage ? Sexe, âge et diplôme, {libelle_periode(periode)}",
          "En ville, près d'un jeune de 15-24 ans sur deux et une femme sur quatre sont au chômage")
    fig.savefig(FIG / "3_chomage_par_groupe.png", dpi=150)
    plt.close(fig)


def fig_tendance(df: pd.DataFrame) -> None:
    d = df.copy()
    labels = [libelle_periode(p) for p in d["periode"]]
    series = [("jeunes_15_24", "Jeunes 15-24 ans", JAUNE), ("femmes", "Femmes", ORANGE),
              ("ensemble", "Ensemble", BLEU), ("hommes", "Hommes", VERT_EAU)]
    fig, ax = plt.subplots(figsize=(9, 5.6), facecolor=FOND)
    fig.subplots_adjust(left=0.08, right=0.80, top=0.84, bottom=0.12)
    for col, nom, c in series:
        ax.plot(labels, d[col], color=c, lw=2, marker="o", ms=6, label=nom)
        ax.text(len(labels) - 1 + 0.08, d[col].iloc[-1], f"{nom} {d[col].iloc[-1]:.1f} %".replace(".", ","),
                va="center", fontsize=9.5, color=ENCRE)
    ax.yaxis.grid(True, color=GRILLE, lw=0.8)
    ax.set_ylim(0, d["jeunes_15_24"].max() * 1.15)
    ax.set_ylabel("Taux de chômage (%)", color=ENCRE_2)
    ax.legend(frameon=False, loc="upper left", ncol=4, fontsize=9.5, labelcolor=ENCRE_2,
              bbox_to_anchor=(0, 1.0))
    style(ax, "Évolution trimestrielle du chômage au Maroc",
          "En un an, il baisse pour les hommes et augmente pour les femmes (comparer T2 à T2, T3 à T3)")
    fig.savefig(FIG / "4_tendance_nationale.png", dpi=150)
    plt.close(fig)


# ------------------------------------------------------------- rapport Excel --
def rapport_excel(resultats: dict[str, pd.DataFrame]) -> None:
    chemin = RES / "rapport_chomage_maroc.xlsx"
    with pd.ExcelWriter(chemin, engine="openpyxl") as xl:
        for nom, df in resultats.items():
            df.to_excel(xl, sheet_name=nom[:31], index=False)
            feuille = xl.sheets[nom[:31]]
            feuille.freeze_panes = "A2"
            for col in feuille.columns:
                largeur = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                feuille.column_dimensions[col[0].column_letter].width = min(largeur + 3, 45)
        pd.read_csv(PROC / "regions.csv").to_excel(xl, sheet_name="donnees_regions", index=False)
        pd.read_csv(PROC / "national.csv").to_excel(xl, sheet_name="donnees_national", index=False)


# ------------------------------------------------------------------- main --
def main() -> None:
    for d in (RES, FIG, DOCS):
        d.mkdir(exist_ok=True)
    con = construire_base()
    derniere, an_avant = periodes(con)
    params = {"derniere": derniere, "an_avant": an_avant}

    resultats = {}
    for nom, sql in requetes().items():
        df = pd.read_sql_query(sql, con, params=params)
        df.to_csv(RES / f"{nom}.csv", index=False)
        resultats[nom] = df
        print(f"{nom}: {len(df)} lignes")

    national = con.execute(
        "SELECT valeur FROM regions WHERE periode=? AND indicateur='taux_chomage' AND region='Ensemble'",
        (derniere,)).fetchone()[0]

    fig_classement(resultats["classement_regions"], national, derniere)
    fig_evolution(resultats["evolution_regions"], derniere, an_avant)
    fig_groupes(resultats["chomage_par_groupe"], derniere)
    fig_tendance(resultats["tendance_nationale"])
    rapport_excel(resultats)

    # Données du tableau de bord (docs/ est publié avec GitHub Pages)
    tableau = {
        "derniere": libelle_periode(derniere),
        "an_avant": libelle_periode(an_avant),
        "national": national,
        **{nom: df.to_dict(orient="records") for nom, df in resultats.items()},
    }
    (DOCS / "data.json").write_text(json.dumps(tableau, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Figures -> {FIG}, résultats -> {RES}, tableau de bord -> {DOCS / 'data.json'}")


if __name__ == "__main__":
    main()
