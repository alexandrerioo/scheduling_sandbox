# Guide entretien — FDE / Data (Oplit)

**Format :** 30–45 min, en live, **mené à l'oral** (l'interviewer partage l'écran, le candidat réagit). Hands-on léger : le candidat raisonne à voix haute sur les données affichées dans `notebooks/unified_interview.ipynb` ; il n'a quasiment pas à coder.

**Profil visé :** Forward-Deployed Engineer capable de **mener un projet DS de bout en bout en autonomie**, sur des données client sales. On note le **cadrage, le pragmatisme, la communication des arbitrages, la rigueur (fuite de données), le sens business et l'autonomie** — pas la performance algorithmique.

**Avant l'entretien :** ouvrir le notebook, `Cellule > Exécuter tout` (les vues sont déjà pré-rendues mais re-lancer ne coûte rien). Le jeu de données provient de `data/generate_dataset.py` (seed 42) ; voir l'antisèche en fin de guide pour la « vérité terrain ».

**Phrase d'intro (à lire) :**
> « On va dérouler un problème comme on le rencontre vraiment chez Oplit. Un client — une usine — veut de l'aide pour ordonnancer sa production. Pas de question piège : ce qui m'intéresse, c'est comment vous cadrez et comment vous expliquez vos arbitrages, bien plus que de réciter une formule. Pensez à voix haute, et "ça dépend" est une bonne réponse — à condition de me dire de quoi ça dépend. »

---

## Déroulé (~39 min cœur, tient dans 30–45 avec marge)

| Section | Contenu | Min |
|---|---|---|
| **A** — Cadrage ordonnancement (flow shop) | objectif / variables / contraintes / heuristique. Clôt sur **[KEEP-1] check-list optimisation**. | 8 |
| **Bridge** | « pour ordonnancer il faut connaître les durées → on ne les connaît pas → prédisons-les ». | 1 |
| **B.1** — Données à l'écran | cible ? grain ? colonnes inutilisables → **[KEEP-2] détection de fuite** ; **[KEEP-3] données ERP incohérentes / gros fichier : que fait-on en premier ?** | 8 |
| **B.2** — Le split | **[KEEP-4] split temporel vs aléatoire** (la question la plus discriminante). | 6 |
| **B.3** — Modèle & features (léger) | baseline à battre + modèle + **[KEEP-5] RF qui surapprend → réduire la profondeur, pas n_estimators**. | 7 |
| **D.1** — Évaluation | métriques reliées au business + **[KEEP-6] 99 % d'accuracy sur pièces défectueuses**. | 5 |
| **D.2** — Mise en prod + bouclage | bon en test / mauvais en prod → drift, skew, rappel fuite, monitoring ; reboucler sur l'ordonnanceur (Partie A). | 4 |

Les **6 questions [KEEP]** sont les seules programmées. Tout le reste est dans la **banque optionnelle** (à piocher si le temps / le candidat le permet).

---

## Partie A — Cadrage ordonnancement (8 min)

Montrer le tableau A/B/C × M1/M2. Laisser **60–90 s de silence** avant de relancer.

**À observer (sans souffler) :** le candidat reformule-t-il l'objectif business avant de plonger dans les maths ? Fait-il émerger spontanément les 4 ingrédients ?

- **Objectif** : minimiser le **makespan** (instant où la dernière pièce sort de M2).
- **Variables de décision** : l'**ordre de passage** des pièces (problème de permutation flow shop).
- **Contraintes** : M1 avant M2 ; une machine = une pièce à la fois ; pas de préemption.
- **Méthode** : une **heuristique** raisonnable suffit. La solution élégante est la **règle de Johnson** (2 machines) → optimale ici, mais **non exigée**. Une règle gloutonne défendue par un bon argument vaut tous les points sur le pragmatisme.

> **[KEEP-1] Check-list optimisation.** *« Prenez du recul : si demain un collègue vous amène n'importe quel problème d'optimisation, quelle est votre check-list avant d'écrire une ligne de code ? »*
> **Attendu :** objectif (et son unité), variables de décision, contraintes, données nécessaires, méthode/critère d'arrêt, comment on mesure une « bonne » solution. Signal d'autonomie : il en fait un modèle mental réutilisable.

⚠️ Ne pas laisser un candidat fort partir dans une formulation PLNE complète : rediriger avec le bridge.

**Bridge (1 min) :** *« Tout ça suppose qu'on connaît les durées. En vrai elles varient selon la pièce, la machine, le lot, le moment. Le client n'a pas de temps standards : il a un export brut de ce qui s'est passé. Donc l'ordonnancement dépend d'un problème de prédiction — combien de temps va durer une opération ? C'est le cœur. »*

---

## Partie B.1 — Les données à l'écran (8 min)

Afficher `head()`, `info()`, glossaire, volumétrie, courbe hebdo. Faire **réagir** le candidat.

**Cible & grain (attendu) :** la cible est `actual_processing_time_min`, au **grain de l'opération** `(of_id, step_no)` — c'est l'unité qu'ordonnance le planificateur. Ne pas agréger à l'OF (on perdrait le signal machine).

> **[KEEP-2] Détection de fuite (leakage).** *« Quelles colonnes ne pourrez-vous PAS utiliser pour prédire, et pourquoi ? »*
> **À éliminer :**
> - `actual_end_ts` — **définit** la cible (`cible = actual_end − actual_start`). Piège évident.
> - `delay_min` = `actual_end − planned_end` → **contient la cible**. Piège **subtil** (ressemble à un KPI inoffensif). ⭐ Le bon candidat le repère.
> - `status` (running/aborted/done), `scrap_qty`, `record_created_ts` (≈ heure de fin pour les lignes terminées) — connus seulement **après** l'opération.
> - **Piège profond** : toute feature d'historique (« durée moyenne par article ») calculée sur **tout** le dataset fuite le futur dans le passé. Doit être **strictement passée** (cf. B.2).
> **À garder :** `planned_*` (l'estimation du planificateur — légitime et c'est la baseline à battre), et `actual_start_ts` **uniquement** si on assume un cadrage « prédiction au démarrage de l'op ». Un bon candidat **explicite le moment de prédiction** (à la planification vs au démarrage).

> **[KEEP-3] Données incohérentes / gros fichier — que fait-on en premier ?** *« Le vrai fichier fait des dizaines de Go et ne tient pas en mémoire ; et il est incomplet/incohérent. Par quoi commencez-vous ? »*
> **Attendu :** (1) **ingestion** par **streaming / chunking**, ou pousser le gros du travail vers un système fait pour (warehouse) en assumant le coût/perf — ne pas tout charger en RAM ; (2) avant de modéliser : **parler au client / à l'expert métier**, **profiler et quantifier** la casse (manquants, doublons, valeurs impossibles), **définir le "suffisamment bon"** pour l'usage, décider quoi **dropper / imputer / signaler**. Le réflexe « je parle au client » est le meilleur signal FDE.
> *(Variante d'escalade dans la banque : OF éclaté sur plusieurs lignes dans le désordre → multi-passes streaming.)*

---

## Partie B.2 — Le split (6 min) — **la question la plus discriminante**

> **[KEEP-4] Split temporel vs aléatoire.** *« On a ~2 ans d'historique et on veut prédire des durées futures. Comment séparez-vous train / test ? »*
> **Piège :** `train_test_split` aléatoire. **Réponse attendue (niveau FDE) : split temporel** — train sur la période ancienne, test sur la récente — parce qu'**en prod on prédit le futur à partir du passé**, et qu'un split aléatoire **fait fuiter le futur** dans l'entraînement (features d'historique + dérive temporelle) → score gonflé qui ment au client.
> Relancer si besoin : *« Qu'est-ce qui cloche avec un 80/20 aléatoire ici ? »* Bonus : validation **time-series / origine glissante** plutôt qu'un seul découpage ; conscience que **août** (et la machine `MCH-12` apparue en cours d'année) sont des **régimes peu/pas vus** en train.

---

## Partie B.3 — Modèle & features (7 min, léger)

Le candidat nomme 2–3 features et un premier modèle. Pas de code attendu.

- **Features leakage-safe :** `quantity` (et `log`), `article` (normalisé), `article_family`, `machine_type`, `machine_id`, calendrier issu de `planned_start_ts` (`mois`/`is_august`, `week_index` = capte la courbe d'apprentissage), `planned_duration_min`, et **historique strictement passé** (moyenne glissante par article / type machine, décalée d'un cran, recalculée dans les bornes du split).
- **Baselines à battre :** (1) moyenne globale (nulle) ; (2) **le planificateur** `planned_duration_min` — *« est-on meilleur que l'existant ? »* (la vraie barre, ~**41 min de MAE**) ; (3) moyenne passée par article = `setup + cadence·q`, forte et interprétable.
- **Modèle :** un **gradient boosting** (ex. `HistGradientBoostingRegressor`) capte les interactions article×type-machine et le coude à q>100 → **~18 min de MAE** ici (≈ −55 % vs planificateur). Le linéaire reste au niveau du planificateur (structure additive seulement). La cible est log-normale → discuter MAE/MAPE et/ou cible en `log`.

> **[KEEP-5] RandomForest qui surapprend.** *« Votre Random Forest surapprend. Vous réduisez la profondeur des arbres ou le nombre d'arbres ? Justifiez. »*
> **Attendu : réduire la profondeur** (`max_depth`) — les arbres profonds mémorisent, c'est la source de variance. **Ajouter des arbres n'augmente PAS le surapprentissage** en RF (le bagging moyenne et stabilise). Le candidat qui couperait `n_estimators` pour corriger le surapprentissage a le modèle mental du bagging à l'envers.

---

## Partie D.1 — Évaluation (5 min)

**Attendu :** métriques **reliées au business** — MAE en **minutes** comparée au planificateur, erreur relative à la durée de l'op, là où l'erreur coûte le plus au planning — pas seulement un R².

> **[KEEP-6] 99 % d'accuracy.** *« Autre client, vite fait : un contrôle vision en fin de ligne détecte les pièces défectueuses, 99 % d'accuracy sur le test. Le client veut le déployer. Vous êtes à l'aise ? »*
> **Attendu :** les défauts sont **rares** → 99 % d'accuracy peut vouloir dire qu'il **n'en détecte (presque) aucun** (le « tout OK » fait déjà 99 %). Il faut **précision / rappel / matrice de confusion**, et **arbitrer le coût d'un défaut manqué vs une fausse alerte _avec le client_**. ⭐ Meilleure question sens business + rigueur — **à protéger**.

---

## Partie D.2 — Mise en prod & bouclage (4 min)

> **Bon en test, mauvais en prod — causes ?** **Attendu :** **dérive des données / distribution** (nouvelles pièces, nouvelle machine — clin d'œil à `MCH-12`, changement de process), **train/serving skew** (features calculées différemment en prod), **fuite** ayant gonflé le score offline (**rappel de B.2**), boucles de rétroaction, casse d'une source amont. Bonus : **comment monitorer** pour le détecter ; le correctif est un **process**, pas un one-shot.

> **Bouclage (1 min) :** *« Reliez à la Partie A : de meilleures prédictions de durée nourrissent l'ordonnanceur — qu'y gagne concrètement le client ? »* Récompense la vision E2E et confirme qu'il a tenu le fil.

---

## Grille d'évaluation (pondérée FDE)

Noter chaque dimension de 1 à 5.

| Dimension | Poids | Ce qu'on cherche |
|---|---|---|
| **Cadrage** | 20 % | Reformule le besoin business avant les maths ; fait émerger objectif/variables/contraintes ; transforme une demande floue en problème traitable. |
| **Pragmatisme** | 20 % | Va au plus simple qui marche ; baseline/heuristique avant la sophistication ; sait quand « assez bon » suffit ; arbitre coût/effort. |
| **Communication des arbitrages** | 20 % | Dit « ça dépend » *et* de quoi ; explique en langage responsable d'atelier ; défend un choix ET son alternative. |
| **Rigueur / fuite** | 15 % | Attrape le piège du split temporel ; repère `delay_min` / la fuite d'historique ; doute d'un score trop beau ; distingue outlier et erreur. |
| **Sens business** | 15 % | Relie les métriques aux résultats usine ; refuse une histoire causale tirée d'une corrélation ; pèse défaut manqué vs fausse alerte ; reboucle prédiction → ordonnancement. |
| **Autonomie / E2E** | 10 % | Mène le fil sans qu'on le tienne par la main ; pense cadrage→données→modèle→éval→prod→monitoring ; sait revenir vers le client. |

**Signaux forts (à noter, pas éliminatoires) :**
- 🟢 Soulève la fuite de données **avant** qu'on lui demande ; propose **spontanément** de parler au client des données sales ; relie l'échec en prod au score offline gonflé.
- 🔴 Défend un split aléatoire après relance ; « je coupe n_estimators pour corriger le surapprentissage RF » ; déploie le détecteur à 99 % ; lit de la causalité dans une corrélation.

---

## Banque de questions optionnelle (si temps / pour creuser)

Une ligne de réponse-type chacune. À piocher, pas à dérouler.

- **LEFT vs INNER JOIN (cas qui change le résultat)** : en joignant le log d'opérations au référentiel articles, un INNER **supprime silencieusement** les opérations dont l'article manque au référentiel → perte de données + biais. (Excellent réflexe FDE : la perte de données comme bug silencieux.)
- **Batch vs stream** : batch = lots périodiques ; stream = au fil de l'eau, faible latence. Ici l'import client est batch ; le suivi temps réel atelier justifierait du stream.
- **ETL vs ELT** : transformer avant (ETL) vs charger brut puis transformer dans le warehouse (ELT). ELT colle au « on atterrit le dump client brut, on transforme ensuite ».
- **Data lake vs data warehouse** : lac = brut/semi-structuré, schema-on-read ; entrepôt = structuré/modélisé pour l'analytique. Le dump brut au lac, les tables prêtes-modèle à l'entrepôt.
- **Limites d'une matrice de corrélation** : seulement linéaire et par paires ; rate interactions et non-linéarités ; rien sur la causalité ; sensible aux outliers.
- **Corrélation vs causalité** : « la machine X corrèle avec des durées longues » → confondeur (on lui confie les familles d'articles les plus complexes). Ne pas livrer d'histoire causale au client sur une corrélation.
- **Outlier vs valeur erronée** : détection (IQR/z-score/bornes métier) ; un run réel rare = signal, un glitch capteur = bruit → demander au client.
- **Cross-validation sur données temporelles** : la k-fold aléatoire fuite ; utiliser une CV à origine glissante (forward-chaining).
- **Normalisation** : utile pour modèles à base de distance/gradient (NN), inutile aux arbres ; Min-Max vs StandardScaler ; **fitter le scaler sur le train seul** puis l'appliquer au test (sinon fuite).
- **Paradigmes d'apprentissage** : supervisé (prédire la durée) ; non-supervisé (clustering de profils machine) ; RL (politique d'ordonnancement) ; semi-supervisé (peu de labels qualité + beaucoup de non-labellisé).
- **Bagging vs boosting** : bagging = arbres indépendants en parallèle, réduit la variance (RF) ; boosting = séquentiel, chaque arbre corrige le précédent, réduit le biais.
- **Surapprentissage / sous-apprentissage + 1 levier deep learning** : train bon / val mauvais = surapprentissage ; levier DL = dropout / early stopping / régularisation / plus de données.
- **Un optimiseur, est-ce de l'IA/ML ?** (~60 s) : la recherche/optimisation ≠ apprendre à partir de données, mais les deux sont complémentaires et sous l'ombrelle IA.
- **Schéma BDD pour CSV client à colonnes variables** (Exo2) : 3 colonnes fixes (date, quantité, ID) en colonnes stables + le reste en **semi-structuré** (document / JSON-like), avec **index** sur le champ semi-structuré si on doit y requêter. Arbitrage schema-on-read vs colonnes rigides.
- **Déplacer un gros volume entre systèmes** (Exo3) : streaming / pagination / extraction partitionnée par fenêtres, car un seul nœud ne peut pas tout tirer d'un coup.

---

## Antèche interviewer — « vérité terrain » du jeu de données

Pour situer les réponses du candidat (généré par `data/generate_dataset.py`, seed 42) :

- **Grain / cible** : 1 ligne = 1 opération `(of_id, step_no)` ; cible `actual_processing_time_min`. ~21 290 lignes, 6 000 OF, période **2024-01-01 → 2024-09-01**.
- **Loi latente** : `setup + cadence·q` avec **coude économie d'échelle** à q>100 ; vitesses par type machine `CNC_FAST 0.70 / CNC_STD 1.00 / MANUAL 1.45 / ROBOT_CELL 0.85` ; bruit log-normal ~12 %.
- **Dérive temporelle (rend le split temporel obligatoire)** : courbe d'apprentissage globale ; **`MCH-12` (ROBOT_CELL) n'apparaît qu'au jour 120** (2024-04-30) ; **ralentissement d'août ×1.10** (peu/pas vu en train → le test se dégrade).
- **`planned_duration_min`** : temps standard du planificateur, basé sur la **moyenne famille** (ignore le type machine et la dérive) → corrélé mais biaisé = **baseline à battre (~41 min MAE)**. GBM correct ≈ **18 min MAE** (val) / ~20 (test, qui inclut août).
- **Colonnes-pièges (fuite)** : `actual_end_ts`, `delay_min`, `status`, `scrap_qty`, `record_created_ts` (+ historique non strictement passé). *Inclure `delay_min` fait tomber la MAE à ~7 min → drapeau rouge si non repéré.*
- **Saletés injectées** : ~4 % cible manquante (running/aborted) ; **92 formes de surface d'`article_ref` → 40 articles réels** (typos, casse, espaces, suffixe `-MM`, tiret manquant) ; ~228 lignes dupliquées ; ~207 durées ≤ 0 (décalage horloge) ; **panne sur `MCH-04`** ~2 semaines (≈ ×8 sur les durées : 1086 vs 137 min) ; ~2 % d'OF aux étapes dans le désordre ; **dates au format FR `JJ/MM/AAAA` pour `MCH-07`** vs ISO ailleurs (aucun `to_datetime` unique ne parse correctement les deux).
