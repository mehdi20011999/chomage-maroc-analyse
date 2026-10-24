-- Requêtes d'analyse. Chaque bloc commence par « -- name: <nom> » ;
-- src/analyze.py les exécute et enregistre le résultat dans results/<nom>.csv.
-- :derniere = dernier trimestre disponible, :an_avant = même trimestre un an avant.

-- name: classement_regions
-- Taux de chômage par région au dernier trimestre, du plus élevé au plus bas,
-- avec l'écart au taux national.
SELECT r.region,
       r.valeur                                   AS taux_chomage,
       ROUND(r.valeur - n.valeur, 1)              AS ecart_national,
       RANK() OVER (ORDER BY r.valeur DESC)       AS rang
FROM regions r
JOIN regions n ON n.periode = r.periode AND n.indicateur = r.indicateur AND n.region = 'Ensemble'
WHERE r.periode = :derniere AND r.indicateur = 'taux_chomage' AND r.region <> 'Ensemble'
ORDER BY r.valeur DESC;

-- name: evolution_regions
-- Variation sur un an (en points) du taux de chômage de chaque région.
SELECT a.region,
       b.valeur                       AS taux_an_avant,
       a.valeur                       AS taux_dernier,
       ROUND(a.valeur - b.valeur, 1)  AS variation_points
FROM regions a
JOIN regions b ON b.region = a.region AND b.indicateur = a.indicateur AND b.periode = :an_avant
WHERE a.periode = :derniere AND a.indicateur = 'taux_chomage'
ORDER BY variation_points;

-- name: chomage_par_groupe
-- Taux de chômage par sexe, âge et diplôme, en ville et à la campagne.
SELECT dimension, categorie,
       MAX(CASE WHEN milieu = 'Urbain'   THEN valeur END) AS urbain,
       MAX(CASE WHEN milieu = 'Rural'    THEN valeur END) AS rural,
       MAX(CASE WHEN milieu = 'Ensemble' THEN valeur END) AS ensemble
FROM national
WHERE periode = :derniere AND indicateur = 'taux_chomage' AND dimension <> 'ensemble'
GROUP BY dimension, categorie
ORDER BY CASE dimension WHEN 'sexe' THEN 1 WHEN 'age' THEN 2 ELSE 3 END, categorie;

-- name: tendance_nationale
-- Évolution trimestrielle du chômage : ensemble, femmes, hommes, jeunes, diplômés.
SELECT periode,
       MAX(CASE WHEN dimension = 'ensemble' THEN valeur END)                              AS ensemble,
       MAX(CASE WHEN categorie = 'Femmes'    THEN valeur END)                             AS femmes,
       MAX(CASE WHEN categorie = 'Hommes'    THEN valeur END)                             AS hommes,
       MAX(CASE WHEN categorie = '15-24 ans' THEN valeur END)                             AS jeunes_15_24,
       MAX(CASE WHEN categorie = 'Diplômés'  THEN valeur END)                             AS diplomes
FROM national
WHERE indicateur = 'taux_chomage' AND milieu = 'Ensemble'
GROUP BY periode
ORDER BY periode;

-- name: sous_emploi
-- Le sous-emploi : des personnes qui travaillent, mais pas assez ou mal payées.
SELECT periode,
       MAX(CASE WHEN milieu = 'Urbain'   THEN valeur END) AS urbain,
       MAX(CASE WHEN milieu = 'Rural'    THEN valeur END) AS rural,
       MAX(CASE WHEN milieu = 'Ensemble' THEN valeur END) AS ensemble
FROM national
WHERE indicateur = 'taux_sous_emploi' AND dimension = 'ensemble'
GROUP BY periode
ORDER BY periode;
