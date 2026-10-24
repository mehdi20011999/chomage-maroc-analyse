"""Extraction des tableaux des notes trimestrielles du HCP (format .docx).

Chaque note « Situation du marché du travail » contient trois tableaux :
  0. activité et emploi au niveau national (urbain / rural / ensemble)
  1. chômage au niveau national (urbain / rural / ensemble)
  2. taux d'activité, d'emploi et de chômage par région

Les deux premiers sont fusionnés dans data/processed/national.csv,
le troisième dans data/processed/regions.csv, au format « long »
(une ligne = une valeur).

Usage : python src/extract.py
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import docx
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"

# Ordre important : le premier libellé qui correspond l'emporte.
# (« Taux de féminisation de la population active en chômage » contient aussi
# « population active en chômage », d'où la place en tête.)
INDICATEURS = [
    ("taux de feminis", "taux_feminisation"),
    ("taux de feminit", "taux_feminisation"),
    ("population active occupee en sous-emploi", "pop_sous_emploi_milliers"),
    ("population active occupee", "pop_occupee_milliers"),
    ("population active en chomage", "pop_chomage_milliers"),
    ("population active", "pop_active_milliers"),
    ("taux d'activite", "taux_activite"),
    ("taux d'emploi", "taux_emploi"),
    ("taux de chomage", "taux_chomage"),
    ("taux de sous-emploi", "taux_sous_emploi"),
    ("structure de l'emploi", "structure_emploi"),
    ("part de l'emploi remunere", "part_emploi_remunere"),
]

DIMENSIONS = {
    "sexe": "sexe",
    "age": "age",
    "diplome": "diplome",
    "forme de sous-emploi": "forme_sous_emploi",
}

# Les lignes qui suivent ces indicateurs sont des sous-catégories.
DIMENSION_IMPLICITE = {
    "structure_emploi": "secteur",
    "part_emploi_remunere": "statut",
}


def norm(texte: str) -> str:
    """Minuscules, sans accents, apostrophes et espaces normalisés."""
    t = unicodedata.normalize("NFKD", texte)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("’", "'").replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip().lower()


def valeur(texte: str) -> float | None:
    """« 8 180 » -> 8180.0 ; « 24,3 » -> 24.3 ; cellule vide -> None."""
    t = texte.replace("\xa0", "").replace(" ", "").replace(",", ".").strip()
    if t in ("", "-"):
        return None
    return float(t)


def periode(texte: str) -> str:
    """« 3ème trimestre de 2025 » ou « 2èmetrimestre2024 » -> « 2025-T3 »."""
    m = re.search(r"(\d)\D*trimestre\D*(\d{4})", norm(texte))
    if not m:
        raise ValueError(f"période illisible : {texte!r}")
    return f"{m.group(2)}-T{m.group(1)}"


def indicateur(libelle: str) -> str | None:
    n = norm(libelle)
    for cle, code in INDICATEURS:
        if n.startswith(cle):
            if code == "taux_feminisation":
                return code + ("_chomeurs" if "chomage" in n else "_actifs")
            return code
    return None


# Les libellés changent légèrement d'une note à l'autre : on les harmonise.
CATEGORIES = [
    ("lie a la duree", "Lié à la durée de travail"),
    ("lie aux revenus", "Lié aux revenus et à l'adéquation formation-emploi"),
    ("industrie", "Industrie (y compris artisanat)"),
    ("agriculture", "Agriculture, forêt et pêche"),
]
REGIONS = {"National": "Ensemble"}


def harmoniser(libelle: str) -> str:
    n = norm(libelle)
    for cle, propre in CATEGORIES:
        if cle in n:
            return propre
    return re.sub(r"\s+", " ", libelle).strip()


def dimension(libelle: str) -> str:
    """« • Selon le diplôme » -> « diplome »."""
    n = norm(libelle).lstrip("• ").removeprefix("selon ")
    for article in ("la ", "le ", "l'"):
        n = n.removeprefix(article)
    if n not in DIMENSIONS:
        raise ValueError(f"dimension inconnue : {libelle!r}")
    return DIMENSIONS[n]


def cellules(row) -> list[str]:
    return [c.text.strip() for c in row.cells]


def tableau_national(table, source: str) -> list[dict]:
    lignes = [cellules(r) for r in table.rows]
    periodes = [periode(c) for c in lignes[0][1:]]
    milieux = [c.strip() for c in lignes[1][1:]]
    sortie, ind, dim = [], None, None

    for c in lignes[2:]:
        libelle, valeurs = c[0], c[1:]
        if norm(libelle).startswith("•"):           # « • Selon le sexe » -> dimension
            dim = dimension(libelle)
            continue
        code = indicateur(libelle)
        if code:                                    # nouvel indicateur
            ind, dim, categorie = code, DIMENSION_IMPLICITE.get(code, "ensemble"), "Ensemble"
            if len(set(c)) == 1:                    # titre fusionné, sans valeur
                continue
        elif len(set(c)) == 1:                      # titre de section (Activité, Chômage…)
            continue
        else:                                       # sous-catégorie de l'indicateur courant
            categorie = harmoniser(libelle)
            if ind is None or dim in (None, "ensemble"):
                raise ValueError(f"{source} : ligne orpheline {libelle!r}")

        for per, mil, v in zip(periodes, milieux, valeurs):
            x = valeur(v)
            if x is None:
                continue
            sortie.append({
                "periode": per, "indicateur": ind, "dimension": dim,
                "categorie": categorie, "milieu": mil, "valeur": x, "source": source,
            })
    return sortie


def tableau_regions(table, source: str) -> list[dict]:
    lignes = [cellules(r) for r in table.rows]
    debut = next(i for i, c in enumerate(lignes) if "trimestre" in norm(" ".join(c[1:])))
    periodes = [periode(c) for c in lignes[debut][1:]]
    sortie, ind = [], None

    for c in lignes[debut + 1:]:
        if len(set(c)) == 1:
            ind = indicateur(c[0])
            if ind is None:
                raise ValueError(f"{source} : section inconnue {c[0]!r}")
            continue
        region = re.sub(r"\s+", " ", c[0]).strip()
        region = REGIONS.get(region, region)
        for per, v in zip(periodes, c[1:]):
            sortie.append({
                "periode": per, "indicateur": ind, "region": region,
                "valeur": valeur(v), "source": source,
            })
    return sortie


def extraire(fichier: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = docx.Document(str(fichier))
    if len(d.tables) != 3:
        raise ValueError(f"{fichier.name} : 3 tableaux attendus, {len(d.tables)} trouvés")
    nat = tableau_national(d.tables[0], fichier.name) + tableau_national(d.tables[1], fichier.name)
    reg = tableau_regions(d.tables[2], fichier.name)
    return pd.DataFrame(nat), pd.DataFrame(reg)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    nats, regs = [], []
    for f in sorted(RAW.glob("*.docx")):
        n, r = extraire(f)
        nats.append(n)
        regs.append(r)
        print(f"{f.name}: {len(n)} valeurs nationales, {len(r)} valeurs régionales")

    national = pd.concat(nats).sort_values(["periode", "indicateur", "dimension", "categorie", "milieu"])
    regions = pd.concat(regs).sort_values(["periode", "indicateur", "region"])
    national.to_csv(OUT / "national.csv", index=False)
    regions.to_csv(OUT / "regions.csv", index=False)
    print(f"-> {OUT / 'national.csv'} ({len(national)} lignes)")
    print(f"-> {OUT / 'regions.csv'} ({len(regions)} lignes)")


if __name__ == "__main__":
    main()
