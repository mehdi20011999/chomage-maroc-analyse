"""Contrôles de qualité des données extraites.

Ces tests vérifient que l'extraction n'a rien perdu ni déformé :
couverture complète, valeurs plausibles, et cohérence interne des
chiffres du HCP (une identité comptable qui doit tenir pour chaque région).
"""
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
NAT = pd.read_csv(ROOT / "data" / "processed" / "national.csv")
REG = pd.read_csv(ROOT / "data" / "processed" / "regions.csv")
PERIODES = ["2024-T2", "2024-T3", "2025-T2", "2025-T3"]
REGIONS = {
    "Tanger-Tétouan-Al Hoceïma", "Oriental", "Fès-Meknès", "Rabat-Salé-Kénitra",
    "Béni Mellal-Khénifra", "Casablanca-Settat", "Marrakech-Safi", "Drâa-Tafilalet",
    "Souss-Massa", "Régions du Sud", "Ensemble",
}


def test_quatre_trimestres():
    assert sorted(NAT.periode.unique()) == PERIODES
    assert sorted(REG.periode.unique()) == PERIODES


@pytest.mark.parametrize("periode", PERIODES)
@pytest.mark.parametrize("indicateur", ["taux_activite", "taux_emploi", "taux_chomage"])
def test_toutes_les_regions(periode, indicateur):
    d = REG[(REG.periode == periode) & (REG.indicateur == indicateur)]
    assert set(d.region) == REGIONS
    assert d.valeur.notna().all()


def test_pas_de_doublon():
    assert not NAT.duplicated(["periode", "indicateur", "dimension", "categorie", "milieu"]).any()
    assert not REG.duplicated(["periode", "indicateur", "region"]).any()


def test_taux_entre_0_et_100():
    taux = NAT[NAT.indicateur.str.startswith(("taux", "part", "structure"))]
    assert taux.valeur.between(0, 100).all()
    assert REG.valeur.between(0, 100).all()


def test_chiffres_publies_par_le_hcp():
    """Quelques valeurs relues à la main dans les notes du HCP."""
    def nat(p, cat="Ensemble", mil="Ensemble"):
        return NAT.query("periode == @p and indicateur == 'taux_chomage' "
                         "and categorie == @cat and milieu == @mil").valeur.item()

    def reg(p, r):
        return REG.query("periode == @p and indicateur == 'taux_chomage' and region == @r").valeur.item()

    assert nat("2025-T3") == 13.1
    assert nat("2024-T3") == 13.6
    assert nat("2025-T2") == 12.8
    assert nat("2025-T3", "Femmes") == 21.6
    assert nat("2025-T3", "15-24 ans", "Urbain") == 48.2
    assert reg("2025-T3", "Oriental") == 21.2
    assert reg("2025-T3", "Tanger-Tétouan-Al Hoceïma") == 8.6
    assert reg("2024-T2", "Oriental") == 21.1


def test_coherence_activite_emploi_chomage():
    """Taux d'emploi = taux d'activité x (1 - taux de chômage).

    Les trois taux sont publiés séparément et arrondis à 0,1 : si
    l'extraction avait décalé une ligne ou une colonne, l'identité casserait.
    """
    large = REG.pivot_table(index=["periode", "region"], columns="indicateur", values="valeur")
    calcule = large.taux_activite * (1 - large.taux_chomage / 100)
    ecart = (calcule - large.taux_emploi).abs()
    assert ecart.max() < 0.2, ecart.sort_values().tail()


def test_population_active_occupee_plus_chomeurs():
    """Population active = actifs occupés + chômeurs (en milliers, à l'arrondi près)."""
    ens = NAT[(NAT.dimension == "ensemble")].pivot_table(
        index=["periode", "milieu"], columns="indicateur", values="valeur")
    ecart = (ens.pop_occupee_milliers + ens.pop_chomage_milliers - ens.pop_active_milliers).abs()
    assert ecart.max() <= 2, ecart


def test_secteurs_somment_a_100():
    s = NAT[NAT.indicateur == "structure_emploi"].groupby(["periode", "milieu"]).valeur.sum()
    assert ((s - 100).abs() <= 0.3).all(), s
