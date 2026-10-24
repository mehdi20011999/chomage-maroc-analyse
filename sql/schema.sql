-- Schéma de la base SQLite (data/processed/chomage.db)

DROP TABLE IF EXISTS national;
CREATE TABLE national (
    periode     TEXT NOT NULL,              -- ex. 2025-T3
    indicateur  TEXT NOT NULL,              -- taux_chomage, taux_activite, ...
    dimension   TEXT NOT NULL,              -- ensemble, sexe, age, diplome, ...
    categorie   TEXT NOT NULL,              -- Ensemble, Femmes, 15-24 ans, ...
    milieu      TEXT NOT NULL CHECK (milieu IN ('Urbain', 'Rural', 'Ensemble')),
    valeur      REAL NOT NULL,
    source      TEXT NOT NULL,
    PRIMARY KEY (periode, indicateur, dimension, categorie, milieu)
);

DROP TABLE IF EXISTS regions;
CREATE TABLE regions (
    periode     TEXT NOT NULL,
    indicateur  TEXT NOT NULL CHECK (indicateur IN ('taux_activite', 'taux_emploi', 'taux_chomage')),
    region      TEXT NOT NULL,
    valeur      REAL NOT NULL CHECK (valeur BETWEEN 0 AND 100),
    source      TEXT NOT NULL,
    PRIMARY KEY (periode, indicateur, region)
);
