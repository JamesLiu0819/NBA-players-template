# Result Accuracy Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **This plan has two mandatory human checkpoints that override "execute without stopping"** — one between Task 4 (run calibration, report numbers) and Task 5 (apply thresholds), and one between Task 7 (simulate the proposed archetype classification, report numbers) and Task 8 (implement it). Both are explicit in the spec itself, not a generic ambiguity. Task 4 and Task 7 are deliberately sized to END at the checkpoint, so each can be dispatched as its own subagent task that reports back to the controller — the controller (not a subagent) relays the numbers to the human partner and waits for a decision before dispatching Task 5 / Task 8. Treat this as the plan's own stop instruction, binding regardless of execution method.

**Goal:** Fix seven result-accuracy problems (star ratings nearly always 1, the same few players always ranked #1, empty training plans, switching players not changing the menu, trivial gaps cluttering the plan, flat-answer users dumped into a meaningless archetype, body-measurement floors too high) without touching the three non-negotiable architecture rules in CLAUDE.md (deterministic pure functions in `src/engine`, environment weight injected up front, no runtime external calls).

**Architecture:** Every behavior change is a pure-function edit inside `src/engine` (`body_fit.py`, `player_matching.py`'s calibrated constants, `training_plan.py`, `archetype.py`), each covered by new unit tests before the call sites (`server/app.py`, `scripts/run_player_match.py`, `src/ui/index.html`) are updated to match. A new `scripts/simulate_results.py` harness (fixed seed, not part of `engine`) drives large synthetic-user runs through the real `server.app.compute_template_results` pipeline to produce the calibration numbers and the final acceptance-criteria report — it is the single source of truth for every percentage quoted in this plan's checkpoints.

**Tech Stack:** Python standard library only (no new dependencies). Existing Flask test client (`server/test_app.py` style) for integration coverage. `unittest`, `PYTHONPATH=src`.

**Spec:** `docs/superpowers/specs/2026-10-07-result-accuracy-design.md` — this plan implements its seven items in the exact order its own "實作順序" section specifies (7 → 1 → calibration → 2/3/4 → 5 → full rerun). Where this plan and the spec disagree, the spec wins; say so in the ledger if that happens.

## Global Constraints

- `/src/engine` stays free of I/O, randomness, and time dependence — every new or changed function there is a pure function (CLAUDE.md).
- Every new or modified `engine` function gets a unit test; same input must always give the same output.
- The simulation script lives in `scripts/`, uses a fixed random seed, and is never imported by `engine`.
- All three language data folders (`data/zh`, `data/zh-Hans`, `data/en`) and `src/ui/index.html`'s `UI_STRINGS` stay in sync; `tests/engine/test_i18n_parity.py` must stay green throughout.
- Code and commit messages in English; user-facing UI copy in natural, idiomatic Traditional Chinese (and its zh-Hans/en equivalents) — no stiff literal translations.
- Do not commit anything beyond what each task's steps describe. Do not push. The human partner reviews and decides on merge/push themselves.
- Two mandatory pauses (the Task 4→5 boundary and the Task 7→8 boundary) are not optional "nice to check in" points — Task 5 does not get dispatched until the human partner has responded to Task 4's report, and likewise Task 8 waits on Task 7's report.

## Review Focus

- A user whose raw height/weight lands exactly on a transition boundary (185cm, 195cm, 88kg, 98kg) — the blend weight must be continuous there, not jump (Task 3).
- A player pool of size 1 fed into the new within-pool percentile helper — must not divide by zero or crash (Task 3).
- `build_training_plan` called with a `signature_skill_id` that has no entry in `env_weights` — must raise clearly, the same way a missing weight for any other skill already does, not silently skip the signature item (Task 6).
- A user whose five-style-axis spread lands exactly on the 25-point archetype threshold — must deterministically pick one branch, not depend on float rounding (Task 8).
- Two or more archetypes tied on distance-to-user size in the body-only branch — must resolve the same way every time (ascending archetype id), not depend on list/dict ordering (Task 8).

---

## Task 1: Widen body-measurement lower bounds

**Files:**
- Modify: `data/zh/題庫.json` (body_measurements array + `_description`/`_editable_fields`)
- Modify: `data/zh-Hans/题库.json` (same fields, simplified-character mirror)
- Modify: `data/en/questions.json` (same fields, English mirror)
- Modify: `tests/engine/test_players_data.py:32-39` (`BODY_SANITY_RANGES`)
- Test: `tests/engine/test_data_integrity.py` (if it asserts exact bound numbers — grep first)

**Interfaces:**
- Produces: the new `min` values below are what every later task's body-measurement work (Task 3's transition constants, Task 6's `compute_user_size`) is written and tested against. No function signature changes in this task.

- [ ] **Step 1: Grep for every place the old bounds are asserted**

Run: `grep -rn "\"min\": 165\|\"min\": 50\|\"min\": 160\|\"min\": 180" data/ tests/ --include="*.json" --include="*.py"`

Expected: hits in the three language data files' `body_measurements` arrays (height/weight/wingspan/standing_reach questions) and nowhere else with a hardcoded number tied to these specific bounds — `tests/engine/test_data_integrity.py` and `tests/engine/test_i18n_parity.py` check structure/parity, not literal bound values. If a hidden hardcoded bound turns up elsewhere, add it to this task's file list before continuing.

- [ ] **Step 2: Edit the three language data files**

In each of `data/zh/題庫.json`, `data/zh-Hans/题库.json`, `data/en/questions.json`, change exactly these four `min` values in `body_measurements` (leave every `max` untouched, leave `running_vertical_reach_cm` and `sprint_100m_seconds` untouched):

| field | old min | new min |
|---|---|---|
| `height_cm` | 165 | 140 |
| `weight_kg` | 50 | 35 |
| `wingspan_cm` | 160 | 135 |
| `standing_reach_cm` | 180 | 175 |

Also update each file's `_description` (currently says "問診題庫,共18題" and doesn't mention bounds — no change needed there) — but if any file's `_editable_fields` or a nearby comment explicitly states the old bound numbers, update that prose too so it doesn't go stale.

- [ ] **Step 3: Widen the derived-player sanity ranges to stay wider than the new question bounds**

`tests/engine/test_players_data.py:32-39` currently reads:

```python
BODY_SANITY_RANGES = {
    "height_cm": (150, 260),
    "weight_kg": (50, 160),
    "wingspan_cm": (150, 280),
    "standing_reach_cm": (180, 340),
    "running_vertical_reach_cm": (200, 400),
    "sprint_100m_seconds": (8.0, 25.0),
}
```

Its own comment (lines 25-31) explicitly says these must stay "deliberately WIDER than data/questions.json's body_measurements [min, max]". With the new question mins (140/35/135/175), the old sanity mins (150/50/150/180) are no longer wider on `height_cm`, `weight_kg`, and `wingspan_cm`. Widen those three down:

```python
# Sanity bounds on derived player body data -- deliberately WIDER than
# data/questions.json's body_measurements [min, max], which is the input
# range for a *user* self-reporting their own body (see the 2026-10
# widening to 140-220cm / 35-120kg -- lower floors so a wider range of
# self-reported body types don't get rejected before reaching the engine).
# A handful of real players (e.g. Victor Wembanyama at 224cm/128kg)
# legitimately fall outside that self-report range -- these bounds only
# catch a broken/blown-up formula output, not "does this fit what a
# typical user could type in".
BODY_SANITY_RANGES = {
    "height_cm": (130, 260),
    "weight_kg": (30, 160),
    "wingspan_cm": (125, 280),
    "standing_reach_cm": (180, 340),
    "running_vertical_reach_cm": (200, 400),
    "sprint_100m_seconds": (8.0, 25.0),
}
```

(`standing_reach_cm`'s sanity min of 180 is still wider than the new question min of 175, so it is left unchanged.)

- [ ] **Step 4: Run the full engine test suite**

Run: `PYTHONPATH=src .venv/bin/python3 -m unittest discover -s tests -t . -p "test_*.py"`
Expected: all tests pass, including `tests/engine/test_i18n_parity.py` (confirms the three language files stayed structurally identical) and `tests/engine/test_players_data.py` (confirms no real player's recorded body falls outside the widened sanity range — it shouldn't, since the sanity range only got wider).

- [ ] **Step 5: Manually confirm the frontend has nothing hardcoded**

Run: `grep -n "q.min\|input.min" src/ui/index.html tools/survey.html`
Expected: every hit reads `min`/`max` off the question object fetched from the API (`q.min`), never a literal number — confirming no separate frontend edit is needed. (Already true as of this plan's research; this step is a verification, not a code change.)

- [ ] **Step 6: Commit**

```bash
git add data/zh/題庫.json data/zh-Hans/题库.json data/en/questions.json tests/engine/test_players_data.py
git commit -m "Widen body-measurement lower bounds for height/weight/wingspan/standing reach"
```

---

## Task 2: Build the simulation harness

**Files:**
- Create: `scripts/simulate_results.py`
- Modify: none (this is additive infrastructure; no existing file changes)

**Interfaces:**
- Consumes: `server.app.compute_template_results(payload, questions, players, skills, archetypes, drills_by_key, lang, pool)`, `server.app.load_data`, `server.app.load_archetypes`, `server.app.load_drills`, `server.app.ENV_WEIGHTS`, `server.app.environment_codes` — all exist today, unchanged signatures.
- Produces: a CLI script callable as `python3 scripts/simulate_results.py --pool current --n 900 --seed 20261007` (the height/weight sampling distribution is fixed module-level constants, `DEFAULT_HEIGHT_MEAN`/`SD`/`DEFAULT_WEIGHT_MEAN`/`SD` — not exposed as CLI flags; nothing in this plan needed to vary them at runtime, so none were added), printing the metrics every later task's checkpoints read: top-10-all-1-star %, best-match star histogram, top-1 player concentration (max share any single player gets across all runs), Pearson correlation between user height and the top-10's average player height, the specific 206cm/113kg body-fit-template check, empty-training-plan %, and distinct (skill_id, level) menu variety per user. Task 4 and Task 9 both call this script; Task 7's checkpoint uses a separate small throwaway (not this script — see Task 7 Step 1).

- [ ] **Step 1: Write the mock-user generator**

```python
#!/usr/bin/env python3
# 用途：模擬大量假使用者跑過完整的 compute_template_results 管線，印出
# 校準門檻、驗收標準需要的統計數字。固定種子，每次重跑結果完全一樣。
# 不是 engine 的一部分（會匯入 server.app），不含任何正式計算規則本身，
# 只是重複呼叫既有的 pure function 管線並統計輸出。
# 可手動調整的變數：DEFAULT_HEIGHT_MEAN/SD、DEFAULT_WEIGHT_MEAN/SD（抽樣用的
# 使用者身高體重分布，2026-10 校準改成接近真實使用者的 175/7、70/12，不是
# body_fit.GENERAL_POPULATION_BODY_STATS 的 180/8、78/12 —— 兩者是不同的
# 用途：GENERAL_POPULATION_BODY_STATS 是「一般打球的人母體」的參考基準，這裡
# 是「我們假設真實使用者長什麹樣」的抽樣來源，故意不共用同一個數字）。
"""Mock-user simulation harness for calibration and acceptance checking.

Usage:
    python3 scripts/simulate_results.py --pool current --n 900 --seed 20261007
    python3 scripts/simulate_results.py --pool alltime --n 900 --seed 20261007

Standard library only except reusing server.app's existing pipeline.
"""
import argparse
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "server"))

from app import (  # noqa: E402
    ENV_WEIGHTS,
    compute_template_results,
    environment_codes,
    load_archetypes,
    load_data,
    load_drills,
)

DEFAULT_HEIGHT_MEAN = 175.0
DEFAULT_HEIGHT_SD = 7.0
DEFAULT_WEIGHT_MEAN = 70.0
DEFAULT_WEIGHT_SD = 12.0


def mock_payload(rng, axis_questions, body_questions):
    """One synthetic respondent: every axis question answered with a fresh
    random 1-5 score (independent per question, matching how a real BARS
    respondent answers each question on its own merits), height/weight
    drawn from a normal distribution and clamped into the question's own
    [min, max] (so a sampled value is never rejected by collect_body_
    measurements' range check), the other four body questions skipped
    (optional on the real site; skipping them exercises the same code path
    missing_required_body_fields already allows).
    """
    axis_answers = [{"question_id": q["id"], "score": rng.randint(1, 5)} for q in axis_questions]

    body_by_field = {q["field"]: q for q in body_questions}
    height_q = body_by_field["height_cm"]
    weight_q = body_by_field["weight_kg"]
    height = min(height_q["max"], max(height_q["min"], rng.gauss(DEFAULT_HEIGHT_MEAN, DEFAULT_HEIGHT_SD)))
    weight = min(weight_q["max"], max(weight_q["min"], rng.gauss(DEFAULT_WEIGHT_MEAN, DEFAULT_WEIGHT_SD)))
    body_answers = [
        {"question_id": height_q["id"], "value": round(height, 1)},
        {"question_id": weight_q["id"], "value": round(weight, 1)},
    ]
    return {"axis_answers": axis_answers, "body_answers": body_answers}, height


def pearson_correlation(xs, ys):
    n = len(xs)
    mean_x, mean_y = statistics.mean(xs), statistics.mean(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return 0.0
    return cov / (var_x * var_y) ** 0.5
```

- [ ] **Step 2: Write the per-run metrics collector and report printer**

```python
def run_simulation(pool, n, seed, lang="zh"):
    rng = random.Random(seed)
    questions, skills, players = load_data(pool=pool, lang=lang)
    archetypes = load_archetypes(lang)
    drills_by_key = load_drills(lang)
    env = ENV_WEIGHTS[environment_codes()[0]]

    all_one_star_count = 0
    best_star_histogram = Counter()
    top1_name_counter = Counter()
    heights = []
    avg_top10_heights = []
    empty_plan_count = 0
    total_plan_count = 0
    menu_variety_samples = []

    for _ in range(n):
        payload, height = mock_payload(rng, questions["axis_positioning"], questions["body_measurements"])
        payload["pool"] = pool
        results = compute_template_results(payload, questions, players, skills, archetypes, drills_by_key, lang, pool)
        top10 = results["top_10"]

        stars = [p["fit_stars"] for p in top10]
        if all(s == 1 for s in stars):
            all_one_star_count += 1
        best_star_histogram[stars[0]] += 1
        top1_name_counter[top10[0]["name"]] += 1

        heights.append(height)
        player_heights = [
            p["body"]["height_cm"] for p in players if p["id"] == top10[0].get("id")
        ]
        # fall back: average body height across the displayed top 10 by name lookup
        by_name = {p["name"]: p for p in players}
        avg_top10_heights.append(
            statistics.mean(by_name[p["name"]]["body"]["height_cm"] for p in top10)
        )

        env_code = environment_codes()[0]
        all_pairs = set()
        for p in top10:
            plan = p["training_plans"][env_code]
            total_plan_count += 1
            if not plan:
                empty_plan_count += 1
            all_pairs.update((item["skill_id"], item["level"]) for item in plan)
        menu_variety_samples.append(len(all_pairs))

    n_runs = n
    print(f"pool={pool} n={n_runs} seed={seed}")
    print(f"  all-10-one-star %: {all_one_star_count / n_runs * 100:.1f}")
    print(f"  best-match star histogram: {dict(sorted(best_star_histogram.items()))}")
    top1_name, top1_count = top1_name_counter.most_common(1)[0]
    print(f"  top-1 concentration: {top1_name} at {top1_count / n_runs * 100:.1f}%")
    print(f"  height correlation (user vs top-10 avg player height): {pearson_correlation(heights, avg_top10_heights):.2f}")
    print(f"  empty-training-plan %: {empty_plan_count / total_plan_count * 100:.1f}")
    print(f"  menu variety (distinct skill+level pairs across a user's top 10): mean={statistics.mean(menu_variety_samples):.1f}")


def check_206_113_case(pool, lang="zh"):
    questions, skills, players = load_data(pool=pool, lang=lang)
    archetypes = load_archetypes(lang)
    drills_by_key = load_drills(lang)
    axis_answers = [{"question_id": q["id"], "score": 3} for q in questions["axis_positioning"]]
    body_by_field = {q["field"]: q for q in questions["body_measurements"]}
    body_answers = [
        {"question_id": body_by_field["height_cm"]["id"], "value": 206},
        {"question_id": body_by_field["weight_kg"]["id"], "value": 113},
    ]
    payload = {"axis_answers": axis_answers, "body_answers": body_answers, "pool": pool}
    results = compute_template_results(payload, questions, players, skills, archetypes, drills_by_key, lang, pool)
    body_fit = results["deep_templates"]["body_fit"]
    print(f"206cm/113kg body-fit template ({pool}): {body_fit}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", choices=["current", "alltime"], default="current")
    parser.add_argument("--n", type=int, default=900)
    parser.add_argument("--seed", type=int, default=20261007)
    parser.add_argument("--lang", default="zh")
    args = parser.parse_args()

    run_simulation(args.pool, args.n, args.seed, args.lang)
    check_206_113_case(args.pool, args.lang)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run it once to confirm it executes end to end**

Run: `PYTHONPATH=src:. .venv/bin/python3 scripts/simulate_results.py --pool current --n 50 --seed 1`
Expected: prints a one-line summary block with no traceback — exact numbers don't matter yet at `n=50`, only that every field prints a real number (not `nan`, not a crash). If `top10[0].get("id")` or any `players` lookup raises `KeyError`, re-check `data/zh/球員.json`'s schema (player dicts may use `"id"` under a different key, or `top_10` entries may not carry an `"id"` field at all through `player_brief`/`compute_template_results` — the real `top_10` list entries come straight from `rank_similar_players_by_style_and_body`, which spreads `**player` so `"id"` should be present; if not, switch the `by_name` lookup to be the only lookup path and drop the unused `player_heights` line).

- [ ] **Step 4: Commit**

```bash
git add scripts/simulate_results.py
git commit -m "Add a fixed-seed simulation harness for calibration and acceptance checks"
```

---

## Task 3: Segmented body-percentile comparison (spec item 1)

**Files:**
- Modify: `src/engine/body_fit.py`
- Test: `tests/engine/test_body_fit.py`

**Interfaces:**
- Consumes: nothing new from earlier tasks.
- Produces: `percentile_normalize_body(user_body, players, field_ranges)` — **same signature as today**, so every call site (`server/app.py`, `scripts/run_player_match.py`, `tools/survey.html`'s JS mirror) needs zero changes for this task. New private helpers `_transition_weight`, `_empirical_percentile_within_pool`, and new named constants `HEIGHT_TRANSITION_LOW/HIGH`, `WEIGHT_TRANSITION_LOW/HIGH` are internal to `body_fit.py`; later tasks do not call them directly.

- [ ] **Step 1: Write the failing tests for the two new private helpers**

```python
class TransitionWeightTest(unittest.TestCase):
    def test_at_or_below_low_bound_is_zero(self):
        self.assertEqual(_transition_weight(180, 185, 195), 0.0)
        self.assertEqual(_transition_weight(185, 185, 195), 0.0)

    def test_at_or_above_high_bound_is_one(self):
        self.assertEqual(_transition_weight(195, 185, 195), 1.0)
        self.assertEqual(_transition_weight(210, 185, 195), 1.0)

    def test_linear_in_between(self):
        self.assertAlmostEqual(_transition_weight(190, 185, 195), 0.5)


class EmpiricalPercentileWithinPoolTest(unittest.TestCase):
    def test_lowest_value_in_pool_is_near_zero(self):
        self.assertLess(_empirical_percentile_within_pool(170, [170, 180, 190, 200]), 20)

    def test_highest_value_in_pool_is_near_100(self):
        self.assertGreater(_empirical_percentile_within_pool(200, [170, 180, 190, 200]), 80)

    def test_single_player_pool_does_not_crash(self):
        self.assertEqual(_empirical_percentile_within_pool(190, [190]), 50.0)

    def test_tied_values_count_as_half_rank(self):
        self.assertEqual(_empirical_percentile_within_pool(190, [180, 190, 190, 200]), 50.0)
```

- [ ] **Step 2: Run to verify these fail**

Run: `PYTHONPATH=src .venv/bin/python3 -m unittest tests.engine.test_body_fit -v 2>&1 | tail -20`
Expected: `NameError` / `ImportError` for `_transition_weight` and `_empirical_percentile_within_pool` (not yet defined/imported).

- [ ] **Step 3: Implement the two helpers and the transition constants**

Add to `src/engine/body_fit.py`, right after `TALL_ATHLETE_THRESHOLD_Z`:

```python
# 2026-10 分段比較門檻（spec item 1）：使用者在門檻以下時，球員用「在自己
# 那個球員池內排第幾」取代常態分布百分位，避免身材比重幾乎占滿距離平方的
# 六成、把所有使用者拉向池子裡最矮最輕的幾位球員。兩組門檻各以現有的
# TALL_ATHLETE_THRESHOLD_Z 門檻（190cm／93kg）為中心，前後 10 個單位線性
# 過渡，是暫定值，之後要調整就直接改這四個數字。
HEIGHT_TRANSITION_LOW = 185.0
HEIGHT_TRANSITION_HIGH = 195.0
WEIGHT_TRANSITION_LOW = 88.0
WEIGHT_TRANSITION_HIGH = 98.0

TRANSITION_BOUNDS = {
    "height_cm": (HEIGHT_TRANSITION_LOW, HEIGHT_TRANSITION_HIGH),
    "weight_kg": (WEIGHT_TRANSITION_LOW, WEIGHT_TRANSITION_HIGH),
}


def _transition_weight(value, low, high):
    """0 at/below low, 1 at/above high, linear in between -- how much a
    player's percentile for this field should come from the population
    curve (_tail_capped_percentile) versus from ranking within the player
    pool (_empirical_percentile_within_pool), based on the USER's own raw
    value for this field."""
    if value <= low:
        return 0.0
    if value >= high:
        return 1.0
    return (value - low) / (high - low)


def _empirical_percentile_within_pool(value, pool_values):
    """Percentile (0-100) of value within pool_values, mean-rank method (a
    tie counts as half a rank) -- mirrors engine/archetype.py's
    _empirical_percentile, duplicated here rather than imported: this
    module stays self-contained (L1, no cross-module dependency), and the
    two percentiles serve different purposes even though the formula is
    the same shape.

    A single-element pool returns 50.0 (the value is simultaneously the
    pool's min and max; there is no meaningful rank to report).
    """
    below = sum(1 for v in pool_values if v < value)
    equal = sum(1 for v in pool_values if v == value)
    return (below + 0.5 * equal) / len(pool_values) * 100
```

- [ ] **Step 4: Run to verify the helper tests pass**

Run: `PYTHONPATH=src .venv/bin/python3 -m unittest tests.engine.test_body_fit -v 2>&1 | tail -30`
Expected: all `TransitionWeightTest` and `EmpiricalPercentileWithinPoolTest` cases pass; the existing `PercentileNormalizeBodyTest` cases now fail (not updated yet — that's Step 5/6 below).

- [ ] **Step 5: Write the failing tests for the new blended behavior in `percentile_normalize_body`**

Add to `tests/engine/test_body_fit.py`'s `PercentileNormalizeBodyTest`:

```python
    def test_short_user_gets_players_ranked_within_pool_not_population_percentile(self):
        # user height 175 is at/below HEIGHT_TRANSITION_LOW (185), so every
        # player's height percentile must come ENTIRELY from
        # _empirical_percentile_within_pool over this specific players list,
        # not from _tail_capped_percentile against the general population.
        field_ranges = {"height_cm": (140, 230), "weight_kg": (35, 160)}
        user_body = {"height_cm": 175, "weight_kg": 70}
        players = [
            {"id": "shortest", "body": {"height_cm": 180, "weight_kg": 70}},
            {"id": "middle", "body": {"height_cm": 200, "weight_kg": 90}},
            {"id": "tallest", "body": {"height_cm": 220, "weight_kg": 110}},
        ]

        new_user_body, new_players, _ = percentile_normalize_body(user_body, players, field_ranges)

        pool_heights = [180, 200, 220]
        for player, raw_height in zip(new_players, pool_heights):
            expected = _empirical_percentile_within_pool(raw_height, pool_heights)
            self.assertAlmostEqual(player["body"]["height_cm"], expected)
        # the user's own percentile is UNCHANGED -- still the population curve.
        height_mean, height_sd = GENERAL_POPULATION_BODY_STATS["height_cm"]
        self.assertAlmostEqual(
            new_user_body["height_cm"],
            _tail_capped_percentile(175, height_mean, height_sd, field_max=230),
        )

    def test_tall_user_gets_players_on_the_population_curve_same_as_before(self):
        # user height 206 is at/above HEIGHT_TRANSITION_HIGH (195), so this
        # must reproduce today's behavior exactly (the 2026-10 "two curves
        # must agree" fix this module already has).
        field_ranges = {"height_cm": (140, 230)}
        user_body = {"height_cm": 206}
        players = [{"id": "p1", "body": {"height_cm": 206}}]

        new_user_body, new_players, _ = percentile_normalize_body(user_body, players, field_ranges)

        self.assertAlmostEqual(new_user_body["height_cm"], new_players[0]["body"]["height_cm"])

    def test_mid_transition_user_blends_both_curves(self):
        field_ranges = {"height_cm": (140, 230)}
        user_body = {"height_cm": 190}  # exact midpoint of 185-195
        players = [{"id": "p1", "body": {"height_cm": 200}}]

        new_user_body, new_players, _ = percentile_normalize_body(user_body, players, field_ranges)

        height_mean, height_sd = GENERAL_POPULATION_BODY_STATS["height_cm"]
        tail_pct = _tail_capped_percentile(200, height_mean, height_sd, field_max=230)
        pool_pct = _empirical_percentile_within_pool(200, [200])
        expected = 0.5 * pool_pct + 0.5 * tail_pct
        self.assertAlmostEqual(new_players[0]["body"]["height_cm"], expected)

    def test_height_and_weight_blend_independently(self):
        # a user short in height (175, below HEIGHT_TRANSITION_LOW=185) but
        # heavy (95kg, inside the WEIGHT transition band 88-98) must get a
        # pure pool-rank blend for height and a genuinely mixed blend for
        # weight in the SAME call -- the two fields must not share one
        # overall "how tall-ish is this user" weight.
        field_ranges = {"height_cm": (140, 230), "weight_kg": (35, 160)}
        user_body = {"height_cm": 175, "weight_kg": 95}
        players = [{"id": "p1", "body": {"height_cm": 200, "weight_kg": 100}}]

        new_user_body, new_players, _ = percentile_normalize_body(user_body, players, field_ranges)

        height_mean, height_sd = GENERAL_POPULATION_BODY_STATS["height_cm"]
        weight_mean, weight_sd = GENERAL_POPULATION_BODY_STATS["weight_kg"]
        expected_height = _empirical_percentile_within_pool(200, [200])  # w=0, pure pool rank
        w_weight = _transition_weight(95, WEIGHT_TRANSITION_LOW, WEIGHT_TRANSITION_HIGH)
        expected_weight = (
            (1 - w_weight) * _empirical_percentile_within_pool(100, [100])
            + w_weight * _tail_capped_percentile(100, weight_mean, weight_sd, field_max=160)
        )
        self.assertAlmostEqual(new_players[0]["body"]["height_cm"], expected_height)
        self.assertAlmostEqual(new_players[0]["body"]["weight_kg"], expected_weight)
```

Also update the import line at the top of the test file to pull in the two new names and `WEIGHT_TRANSITION_LOW`/`WEIGHT_TRANSITION_HIGH`:

```python
from engine.body_fit import (
    GENERAL_POPULATION_BODY_STATS,
    TALL_ATHLETE_THRESHOLD_Z,
    WEIGHT_TRANSITION_HIGH,
    WEIGHT_TRANSITION_LOW,
    _empirical_percentile_within_pool,
    _normal_cdf_percentile,
    _tail_capped_percentile,
    _transition_weight,
    body_distance,
    collect_body_measurements,
    missing_required_body_fields,
    percentile_normalize_body,
)
```

- [ ] **Step 6: Run to verify the new tests fail (old implementation doesn't blend)**

Run: `PYTHONPATH=src .venv/bin/python3 -m unittest tests.engine.test_body_fit.PercentileNormalizeBodyTest -v 2>&1 | tail -30`
Expected: `test_short_user_gets_players_ranked_within_pool_not_population_percentile`, `test_mid_transition_user_blends_both_curves`, and `test_height_and_weight_blend_independently` FAIL (current code always uses `_tail_capped_percentile` for players, never the pool rank). `test_tall_user_gets_players_on_the_population_curve_same_as_before` and the two pre-existing tests (`test_converts_only_the_fields_with_population_stats_to_percentiles`, `test_returns_inputs_unchanged_when_no_percentile_fields_present`) should already pass, since those don't exercise a below-threshold user.

- [ ] **Step 7: Implement the blend in `percentile_normalize_body`**

Replace the body of `percentile_normalize_body` (keep its signature and docstring opening, extend the docstring with the new behavior):

```python
def percentile_normalize_body(user_body, players, field_ranges):
    """... (existing docstring, plus:)

    2026-10 (spec item 1): a player's percentile for height_cm/weight_kg is
    no longer always the population tail-capped curve. It's a blend between
    that curve and the player's rank WITHIN THIS SPECIFIC players POOL
    (_empirical_percentile_within_pool), weighted by where the USER's own
    raw value for that field falls relative to TRANSITION_BOUNDS[field]: at
    or below the low bound, players are ranked purely within the pool (a
    "how do you compare to other recreational players" framing on both
    sides); at or above the high bound, this reproduces today's behavior
    exactly (both sides on the same population curve); linear in between.
    The user's OWN percentile is never blended -- always the plain
    population curve, as before. Only height_cm/weight_kg are affected;
    every other field is untouched, same as before.
    """
    percentile_fields = set(GENERAL_POPULATION_BODY_STATS) & set(field_ranges)
    if not percentile_fields:
        return user_body, players, field_ranges

    def tail_pct(field, raw_value):
        mean, sd = GENERAL_POPULATION_BODY_STATS[field]
        field_max = field_ranges[field][1]
        return _tail_capped_percentile(raw_value, mean, sd, field_max)

    new_user_body = dict(user_body)
    new_field_ranges = dict(field_ranges)
    for field in percentile_fields:
        if field in user_body:
            new_user_body[field] = tail_pct(field, user_body[field])
        new_field_ranges[field] = (0, 100)

    # Pool of raw values per field, collected BEFORE any conversion -- needed
    # for the within-pool percentile and must never see already-converted
    # values from a previous call.
    pool_raw_values = {
        field: [player["body"][field] for player in players if field in player.get("body", {})]
        for field in percentile_fields
    }
    transition_weight = {
        field: (
            _transition_weight(user_body[field], *TRANSITION_BOUNDS[field])
            if field in user_body else 1.0  # no user value to decide the blend -> old behavior
        )
        for field in percentile_fields
    }

    new_players = []
    for player in players:
        body = dict(player.get("body", {}))
        for field in percentile_fields:
            if field not in body:
                continue
            w = transition_weight[field]
            pool_pct = _empirical_percentile_within_pool(body[field], pool_raw_values[field])
            population_pct = tail_pct(field, body[field])
            body[field] = (1 - w) * pool_pct + w * population_pct
        new_players.append({**player, "body": body})

    return new_user_body, new_players, new_field_ranges
```

- [ ] **Step 8: Run the full `test_body_fit.py` suite**

Run: `PYTHONPATH=src .venv/bin/python3 -m unittest tests.engine.test_body_fit -v 2>&1 | tail -40`
Expected: every test passes, old and new alike.

- [ ] **Step 9: Run the full engine + server suite to catch any downstream breakage**

Run: `PYTHONPATH=src .venv/bin/python3 -m unittest discover -s tests -t . -p "test_*.py" && cd server && PYTHONPATH=../src:.. ../.venv/bin/python3 -m unittest test_app && cd ..`
Expected: all green. `server/test_app.py` exercises `percentile_normalize_body` indirectly through `/api/template-results`; its fixtures use mid-range or deliberately-tall bodies (per existing test names), so behavior should be unaffected, but read the output rather than assume.

- [ ] **Step 10: Commit**

```bash
git add src/engine/body_fit.py tests/engine/test_body_fit.py
git commit -m "Blend player body percentiles toward within-pool ranking for shorter/lighter users"
```

---

## Task 4: Run star-rating calibration and report the numbers — ends at a mandatory checkpoint

**This task ends in a report, not a code change.** It is deliberately scoped to stop exactly where the spec requires a human decision (the raw calibrated numbers, with no "+7" bump applied, must be shown to the human partner before anything is written into `player_matching.py`). If dispatching this as a subagent task, its report back to the controller IS the deliverable — the controller then relays the two threshold tuples to the human partner and only dispatches Task 5 once an answer comes back on whether/how to adjust them.

**Files:**
- Create: `scripts/calibrate_star_thresholds.py`
- Modify: none in `src/engine` yet — that's Task 5, gated on this task's report.

**Interfaces:**
- Consumes: `engine.axis_position.score_axis_coordinates`, `engine.body_fit.percentile_normalize_body` (now with Task 3's blending), `engine.player_matching.rank_similar_players_by_style_and_body`, `engine.archetype.compute_player_sizes` (unchanged) -- same calibration shape the current header comment documents, just with the new body-percentile logic live and a new sampling distribution.
- Produces: `scripts/calibrate_star_thresholds.py`, a runnable script, plus two printed threshold tuples (current pool, all-time pool) that Task 5 consumes as its literal input. Nothing in `src/engine` changes in this task.

- [ ] **Step 1: Write the calibration script, following the documented method exactly**

```python
#!/usr/bin/env python3
# 用途：照 engine/player_matching.py 檔頭記載的校準方法，對指定球員池重新算出
# 星等門檻的八個切點。40 次模擬、k=10，共 400 筆距離樣本，取第
# 44/89/133/178/222/267/311/356 名（由小到大排序）當門檻，四捨五入到整數。
# 2026-10 改動：抽樣用的身高體重從 GENERAL_POPULATION_BODY_STATS 的 180/78
# 改成接近真實使用者的 175/7（身高）、70/12（體重）——兩者是不同用途，故意
# 不共用同一個數字，見 scripts/simulate_results.py 開頭的說明。
# 不是 engine 的一部分，不含校準公式本身的邏輯判斷，只是重複呼叫既有函數。
"""Recalibrate the 8 star-rating threshold cut points for one player pool.

Usage:
    python3 scripts/calibrate_star_thresholds.py --pool current
    python3 scripts/calibrate_star_thresholds.py --pool alltime
"""
import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import json  # noqa: E402

from engine.axis_position import AXES, score_axis_coordinates  # noqa: E402
from engine.body_fit import percentile_normalize_body  # noqa: E402
from engine.player_matching import rank_similar_players_by_style_and_body  # noqa: E402

CALIBRATION_HEIGHT_MEAN = 175.0
CALIBRATION_HEIGHT_SD = 7.0
CALIBRATION_WEIGHT_MEAN = 70.0
CALIBRATION_WEIGHT_SD = 12.0
N_SIMULATIONS = 40
K = 10
CUT_RANKS = [44, 89, 133, 178, 222, 267, 311, 356]  # i*400/9 for i in 1..8
STAR_LABELS = [5, 4.5, 4, 3.5, 3, 2.5, 2, 1.5]


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def mock_axis_coordinates(rng):
    return {
        axis: sum(rng.randint(1, 5) for _ in range(2)) / 2 / 4 * 100 - 25
        for axis in AXES
    }
    # NOTE: see Step 2 below -- this placeholder formula is replaced before
    # Step 4 with the exact same per-axis averaging score_axis_coordinates
    # itself uses, not a hand-rolled approximation.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", choices=["current", "alltime"], required=True)
    parser.add_argument("--seed", type=int, default=20261007)
    args = parser.parse_args()

    questions = load_json(ROOT / "data" / "zh" / "題庫.json")
    players_file = "球員.json" if args.pool == "current" else "歷史球員.json"
    players = load_json(ROOT / "data" / "zh" / players_file)["players"]
    body_field_ranges = {q["field"]: (q["min"], q["max"]) for q in questions["body_measurements"]}

    rng = random.Random(args.seed)
    all_distances = []
    for _ in range(N_SIMULATIONS):
        axis_answers = [
            {"question_id": q["id"], "score": rng.randint(1, 5)}
            for q in questions["axis_positioning"]
        ]
        coordinates = score_axis_coordinates(questions["axis_positioning"], axis_answers)
        height = max(
            body_field_ranges["height_cm"][0],
            min(body_field_ranges["height_cm"][1], rng.gauss(CALIBRATION_HEIGHT_MEAN, CALIBRATION_HEIGHT_SD)),
        )
        weight = max(
            body_field_ranges["weight_kg"][0],
            min(body_field_ranges["weight_kg"][1], rng.gauss(CALIBRATION_WEIGHT_MEAN, CALIBRATION_WEIGHT_SD)),
        )
        user_body = {"height_cm": height, "weight_kg": weight}
        user_body_pct, players_pct, field_ranges_pct = percentile_normalize_body(
            user_body, players, body_field_ranges
        )
        ranked = rank_similar_players_by_style_and_body(
            coordinates, user_body_pct, players_pct, field_ranges_pct, k=K
        )
        all_distances.extend(p["distance"] for p in ranked)

    all_distances.sort()
    print(f"pool={args.pool}  n_samples={len(all_distances)}")
    thresholds = []
    for rank, stars in zip(CUT_RANKS, STAR_LABELS):
        distance = round(all_distances[rank - 1])
        thresholds.append((distance, stars))
        print(f"  rank {rank:3d} -> distance {all_distances[rank - 1]:.1f} -> rounded {distance}  ({stars} stars)")
    print(f"\n  tuple to paste into player_matching.py:\n  {tuple(thresholds)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Fix `mock_axis_coordinates` to match `score_axis_coordinates` exactly, or drop it**

The placeholder in Step 1 is a stand-in formula, not the real one — the calibration method requires using "每軸2個獨立1-5隨機值取平均(對應 score_axis_coordinates 的真實算法)". Since `score_axis_coordinates` is already called directly in `main()` with real randomly-generated 1-5 axis answers, `mock_axis_coordinates` is dead code — delete that function entirely rather than fix it. Re-read `main()`: it already builds `axis_answers` as random 1-5 scores per question and feeds them through the real `score_axis_coordinates`, which is the correct approach (no approximation needed). Remove the unused function and its NOTE comment.

- [ ] **Step 3: Run calibration for the current-pool, with Task 3's blending now live**

Run: `PYTHONPATH=src:. .venv/bin/python3 scripts/calibrate_star_thresholds.py --pool current`
Expected: prints 8 increasing distance values and their rounded thresholds, plus a ready-to-paste tuple. Record the output.

- [ ] **Step 4: Run calibration for the all-time pool**

Run: `PYTHONPATH=src:. .venv/bin/python3 scripts/calibrate_star_thresholds.py --pool alltime`
Expected: same shape, 8 increasing values. Record the output.

- [ ] **Step 5: Commit the script, then report**

```bash
git add scripts/calibrate_star_thresholds.py
git commit -m "Add a star-rating threshold calibration script"
```

**This task's report to the controller/human partner must include both tuples verbatim**, labeled explicitly as *raw* calibrated numbers with no "+7" flat bump applied (the spec flags the old +7 adjustment as something to reconsider, not something to keep by default), plus the question: apply the raw numbers as-is, apply a flat adjustment (and how much), or something else? Task 5 does not start until this question is answered. This is one of this plan's two mandatory checkpoints (see the plan header) — if you are the controller orchestrating subagent dispatches, this is the point where YOU (not a subagent) relay these numbers to the human partner and wait.

---

## Task 5: Apply calibrated star thresholds and verify

**Files:**
- Modify: `src/engine/player_matching.py:50-70` (`CURRENT_POOL_STAR_THRESHOLDS`, `ALLTIME_POOL_STAR_THRESHOLDS`, header comment)
- Test: no new engine function is introduced here; the changed constants are exercised by every existing test in `tests/engine/test_player_matching.py` that references them — re-run, don't rewrite, unless one specifically pins the OLD numeric thresholds.

**Interfaces:**
- Consumes: Task 4's two reported threshold tuples, as approved (possibly adjusted) by the human partner at the checkpoint between Task 4 and this task. Do not start this task without that approved pair of tuples in hand.
- Produces: new values for `CURRENT_POOL_STAR_THRESHOLDS` and `ALLTIME_POOL_STAR_THRESHOLDS`. Task 6 and Task 8 read these constants by name only (never by value), so nothing downstream needs to change regardless of what the new numbers turn out to be.

- [ ] **Step 1: Apply the approved thresholds to `player_matching.py`**

Replace the values (not the shape) of `CURRENT_POOL_STAR_THRESHOLDS` and `ALLTIME_POOL_STAR_THRESHOLDS` in `src/engine/player_matching.py:50-70` with whatever the human partner approved at the Task 4→5 checkpoint. Update the module's header comment (lines 21-33) to describe the new sampling distribution (175/7, 70/12 instead of the population stats) and whatever was decided about the flat adjustment — do not leave the old "180/78" and "+7" prose in place once it no longer describes what the constants actually are.

- [ ] **Step 2: Run the player_matching test suite**

Run: `PYTHONPATH=src .venv/bin/python3 -m unittest tests.engine.test_player_matching -v 2>&1 | tail -40`
Expected: all pass. If any test asserts an exact star count tied to the OLD threshold numbers (e.g. "distance 70 -> 3 stars" using an old cutoff that moved), update that specific assertion to the new numbers — this is expected and is not a sign of a bug, just a test that hard-coded a calibrated constant.

- [ ] **Step 3: Re-run the Task 2 simulation harness and report the before/after numbers**

Run: `PYTHONPATH=src:. .venv/bin/python3 scripts/simulate_results.py --pool current --n 900 --seed 20261007`
Expected and report to the human partner: all-10-one-star % below the spec's problem-statement baseline of 53%, ideally near the spec's cited target of ~0%; best-star histogram spread across more than one bucket; top-1 concentration below the baseline 51%; height correlation above the baseline 0.42 (spec targets ≥0.74, though the per-field-blend version hasn't been simulated before now, so treat the spec's 0.74 as directional, not a hard pass/fail gate at this task -- Task 9's final rerun is where the acceptance criterion (≥0.6) is actually graded).

- [ ] **Step 4: Run the full engine + server suite**

Run: `PYTHONPATH=src .venv/bin/python3 -m unittest discover -s tests -t . -p "test_*.py" && cd server && PYTHONPATH=../src:.. ../.venv/bin/python3 -m unittest test_app && cd ..`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/engine/player_matching.py tests/engine/test_player_matching.py
git commit -m "Recalibrate star-rating thresholds for both player pools with the new body-percentile blend"
```

---

## Task 6: Training plan redesign — signature skill first, relative threshold, max 5 items (spec items 2/3/4)

**Files:**
- Modify: `src/engine/training_plan.py`
- Modify: `server/app.py:192-257` (`format_training_plan`, the `build_training_plan(...)` call site)
- Modify: `src/ui/index.html` (UI_STRINGS × 3 languages, `renderSkillItem`, `renderTrainingBody`)
- Test: `tests/engine/test_training_plan.py` (largely rewritten — see Step 1)
- Test: `server/test_app.py` (new/updated assertions for `is_signature` and the never-empty plan)

**Interfaces:**
- Consumes: `engine.priority.rank_priorities`, `engine.priority.compute_priority`, `engine.skill_level.skill_gap`, `engine.player_matching.skill_dominant_axis` — all unchanged.
- Produces: `build_training_plan(skills, env_weights, user_coords, target_coords, signature_skill_id, top_n=5)` — note the new required 5th positional parameter inserted before `top_n`. Every item in the returned list now has an `"is_signature"` boolean. Task 8 does not call this function, so no cross-task interface risk there.

- [ ] **Step 1: Rewrite `tests/engine/test_training_plan.py`'s fixtures and failing tests**

Replace the whole file:

```python
# 用途：測試 build_training_plan()——招牌技能固定排第一且不受差距/門檴限制、
# 其餘項目依 P 排序並套用相對門檻、總數上限 5 項、沒有其餘項目時只回傳招牌
# 技能一項——跟 skill_difficulty_level() 的難度判定。
# 可手動調整的變數：無——這裡的技能跟座標都是測試用的人造資料,不是要調的參數。

import unittest

from engine.training_plan import (
    LEVEL_ADVANCED,
    LEVEL_ENTRY,
    LEVEL_MASTERY,
    TRAINING_PLAN_RELATIVE_THRESHOLD,
    build_training_plan,
    skill_difficulty_level,
)

SKILLS = [
    {"id": "shooting", "cost_C": 2,
     "axis_relevance": {"A": 0.0, "B1": 1.0, "B2": 0.0, "C1": 0.0, "C2": 0.0, "D": 0.0}},
    {"id": "creation", "cost_C": 2,
     "axis_relevance": {"A": 1.0, "B1": 0.0, "B2": 0.0, "C1": 0.0, "C2": 0.0, "D": 0.0}},
    {"id": "rim", "cost_C": 4,
     "axis_relevance": {"A": 0.0, "B1": 0.0, "B2": 0.0, "C1": 0.0, "C2": 1.0, "D": 0.0}},
    {"id": "transition", "cost_C": 1,
     "axis_relevance": {"A": 0.0, "B1": 0.0, "B2": 0.0, "C1": 0.0, "C2": 0.0, "D": 1.0}},
]

USER = {"A": 30.0, "B1": 30.0, "B2": 30.0, "C1": 30.0, "C2": 30.0, "D": 30.0}
TARGET = {"A": 60.0, "B1": 80.0, "B2": 30.0, "C1": 30.0, "C2": 50.0, "D": 90.0}
EVEN_ENV = {"shooting": 1.0, "creation": 1.0, "rim": 1.0, "transition": 1.0}


class SkillDifficultyLevelTest(unittest.TestCase):
    def test_below_forty_is_entry(self):
        self.assertEqual(skill_difficulty_level(39.9), LEVEL_ENTRY)

    def test_forty_through_seventy_is_advanced(self):
        self.assertEqual(skill_difficulty_level(40), LEVEL_ADVANCED)
        self.assertEqual(skill_difficulty_level(70), LEVEL_ADVANCED)

    def test_above_seventy_is_mastery(self):
        self.assertEqual(skill_difficulty_level(70.1), LEVEL_MASTERY)


class BuildTrainingPlanTest(unittest.TestCase):
    def test_signature_skill_is_always_first(self):
        plan = build_training_plan(SKILLS, EVEN_ENV, USER, TARGET, signature_skill_id="rim")

        self.assertEqual(plan[0]["skill_id"], "rim")
        self.assertTrue(plan[0]["is_signature"])
        self.assertTrue(all(not item["is_signature"] for item in plan[1:]))

    def test_signature_skill_appears_even_with_zero_or_negative_gap(self):
        # target is at/below the user on every trainable axis -> every
        # OTHER skill would normally be excluded, but the signature skill
        # must still appear, unlike the pre-2026-10 "all gaps zero" behavior.
        target = {axis: 0.0 for axis in USER}

        plan = build_training_plan(SKILLS, EVEN_ENV, USER, target, signature_skill_id="shooting")

        self.assertEqual([item["skill_id"] for item in plan], ["shooting"])
        self.assertTrue(plan[0]["is_signature"])

    def test_signature_skill_on_the_d_axis_is_the_exception_to_d_being_untrainable(self):
        # "transition"'s axis_relevance is 100% on D. skill_gap() ignores D
        # entirely for the GAP calculation (so G is always 0 here), but the
        # item must still be included (as the signature) and still get a
        # real difficulty level off the D axis score.
        plan = build_training_plan(SKILLS, EVEN_ENV, USER, TARGET, signature_skill_id="transition")

        signature = plan[0]
        self.assertEqual(signature["skill_id"], "transition")
        self.assertEqual(signature["dominant_axis"], "D")
        self.assertEqual(signature["G"], 0.0)
        self.assertEqual(signature["level"], skill_difficulty_level(USER["D"]))

    def test_other_items_sorted_by_priority_after_the_signature(self):
        plan = build_training_plan(SKILLS, EVEN_ENV, USER, TARGET, signature_skill_id="rim")

        other_ids = [item["skill_id"] for item in plan[1:]]
        self.assertEqual(other_ids, sorted(other_ids, key=lambda sid: -next(i["P"] for i in plan if i["skill_id"] == sid)))

    def test_items_below_25_percent_of_the_best_other_item_are_dropped(self):
        # shooting: G = 1.0*(80-30) = 50, E=1 -> P = 50/2 = 25
        # creation: G = 1.0*(60-30) = 30, E=1 -> P = 30/2 = 15 (60% of 25, kept)
        # rim:      G = 1.0*(50-30) = 20, E=1 -> P = 20/4 = 5  (20% of 25, dropped)
        plan = build_training_plan(SKILLS, EVEN_ENV, USER, TARGET, signature_skill_id="transition")

        other_ids = {item["skill_id"] for item in plan[1:]}
        self.assertIn("shooting", other_ids)
        self.assertIn("creation", other_ids)
        self.assertNotIn("rim", other_ids)

    def test_relative_threshold_constant_is_twenty_five_percent(self):
        self.assertEqual(TRAINING_PLAN_RELATIVE_THRESHOLD, 0.25)

    def test_total_items_capped_at_top_n_including_the_signature(self):
        many_skills = SKILLS + [
            {"id": f"extra{i}", "cost_C": 1,
             "axis_relevance": {"A": 1.0, "B1": 0.0, "B2": 0.0, "C1": 0.0, "C2": 0.0, "D": 0.0}}
            for i in range(5)
        ]
        many_env = dict(EVEN_ENV, **{f"extra{i}": 1.0 for i in range(5)})

        plan = build_training_plan(many_skills, many_env, USER, TARGET, signature_skill_id="rim", top_n=5)

        self.assertLessEqual(len(plan), 5)
        self.assertEqual(plan[0]["skill_id"], "rim")

    def test_environment_weight_can_change_the_non_signature_order(self):
        tight_perimeter = {"shooting": 0.1, "creation": 1.8, "rim": 1.0, "transition": 1.0}

        plan = build_training_plan(SKILLS, tight_perimeter, USER, TARGET, signature_skill_id="transition")

        self.assertEqual(plan[1]["skill_id"], "creation")

    def test_level_comes_from_users_score_on_the_dominant_axis(self):
        user = dict(USER, B1=85.0)
        target = dict(TARGET, B1=100.0)

        plan = build_training_plan(SKILLS, EVEN_ENV, user, target, signature_skill_id="rim")

        shooting = next(item for item in plan if item["skill_id"] == "shooting")
        self.assertEqual(shooting["dominant_axis"], "B1")
        self.assertEqual(shooting["level"], LEVEL_MASTERY)

    def test_same_input_gives_same_output(self):
        self.assertEqual(
            build_training_plan(SKILLS, EVEN_ENV, USER, TARGET, signature_skill_id="rim"),
            build_training_plan(SKILLS, EVEN_ENV, USER, TARGET, signature_skill_id="rim"),
        )

    def test_missing_environment_weight_for_a_non_signature_skill_raises(self):
        with self.assertRaises(ValueError):
            build_training_plan(SKILLS, {"rim": 1.0}, USER, TARGET, signature_skill_id="rim")

    def test_missing_environment_weight_for_the_signature_skill_itself_raises(self):
        env_missing_signature = {"shooting": 1.0, "creation": 1.0, "transition": 1.0}
        with self.assertRaises(ValueError):
            build_training_plan(SKILLS, env_missing_signature, USER, TARGET, signature_skill_id="rim")

    def test_unknown_signature_skill_id_raises(self):
        with self.assertRaises(ValueError):
            build_training_plan(SKILLS, EVEN_ENV, USER, TARGET, signature_skill_id="does_not_exist")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify these fail**

Run: `PYTHONPATH=src .venv/bin/python3 -m unittest tests.engine.test_training_plan -v 2>&1 | tail -40`
Expected: `TypeError` (missing required argument `signature_skill_id`) on nearly every test, since the current `build_training_plan` doesn't accept it yet.

- [ ] **Step 3: Rewrite `build_training_plan`**

Replace `src/engine/training_plan.py`'s constants and `build_training_plan` (keep `skill_difficulty_level` and the two difficulty constants untouched):

```python
TRAINING_PLAN_RELATIVE_THRESHOLD = 0.25  # 暫定


def _priority_item(skill, env_weights, user_coords, target_coords, is_signature):
    if skill["id"] not in env_weights:
        raise ValueError(f"env weights missing skill: {skill['id']}")
    g = skill_gap(skill["axis_relevance"], user_coords, target_coords)
    dominant_axis = skill_dominant_axis(skill["axis_relevance"])
    return {
        "skill_id": skill["id"],
        "G": g,
        "E": env_weights[skill["id"]],
        "C": skill["cost_C"],
        "dominant_axis": dominant_axis,
        "user_axis_score": user_coords[dominant_axis],
        "is_signature": is_signature,
    }


def build_training_plan(skills, env_weights, user_coords, target_coords, signature_skill_id, top_n=5):
    """Rank skills by P = G x E / C, with the target player's signature
    skill forced into slot 1 regardless of its own gap, cost, or the
    relative threshold below -- see SPEC.md / the 2026-10 design doc item
    2/3/4: a training plan must never be empty (the signature skill is
    always a valid "something to work on"), and switching target players
    must always change at least the first item shown.

    skills: list of skill dicts (id, axis_relevance, cost_C), e.g. from 技能.json.
    env_weights: {skill_id: E} for the chosen league environment. Must contain
        an entry for EVERY skill in `skills`, signature included.
    user_coords / target_coords: {"A"..."D": 0-100}.
    signature_skill_id: the target player's signature_skill_id. Must be the
        id of one of the skills in `skills`.
    top_n: total item cap INCLUDING the signature skill (so at most
        top_n - 1 other items are added).

    Returns a list of 1 to top_n items (never empty), each with skill_id, G,
    E, C, P, dominant_axis, level, and is_signature. Item 0 is always the
    signature skill. The rest are sorted by P descending, excluding any
    non-signature skill whose own gap is <= 0, and further excluding any
    whose P is below TRAINING_PLAN_RELATIVE_THRESHOLD of the highest P
    among the OTHER (non-signature) items.

    Raises ValueError if signature_skill_id doesn't match any skill in
    `skills`, or if env_weights is missing an entry for any skill this
    function needs a weight for (signature included).
    """
    skills_by_id = {skill["id"]: skill for skill in skills}
    if signature_skill_id not in skills_by_id:
        raise ValueError(f"unknown signature_skill_id: {signature_skill_id}")

    signature_item = _priority_item(
        skills_by_id[signature_skill_id], env_weights, user_coords, target_coords, is_signature=True
    )
    signature_item["P"] = compute_priority(signature_item["G"], signature_item["E"], signature_item["C"])
    signature_item["level"] = skill_difficulty_level(signature_item["user_axis_score"])

    other_items = []
    for skill in skills:
        if skill["id"] == signature_skill_id:
            continue
        item = _priority_item(skill, env_weights, user_coords, target_coords, is_signature=False)
        if item["G"] <= 0:
            continue
        other_items.append(item)

    ranked_others = rank_priorities(other_items)
    if ranked_others:
        threshold = ranked_others[0]["P"] * TRAINING_PLAN_RELATIVE_THRESHOLD
        ranked_others = [item for item in ranked_others if item["P"] >= threshold]
    ranked_others = ranked_others[: max(0, top_n - 1)]

    plan = [signature_item] + ranked_others
    for item in plan:
        item["level"] = skill_difficulty_level(item["user_axis_score"])
    return plan
```

Update the imports at the top of `training_plan.py` to add `compute_priority`:

```python
from engine.priority import compute_priority, rank_priorities
```

- [ ] **Step 4: Run to verify all tests pass**

Run: `PYTHONPATH=src .venv/bin/python3 -m unittest tests.engine.test_training_plan -v 2>&1 | tail -40`
Expected: all pass. Double-check `test_items_below_25_percent_of_the_best_other_item_are_dropped`'s hand-worked P values against the actual run (the comment's arithmetic should match; if not, the comment has a mistake, not the code — fix the comment).

- [ ] **Step 5: Wire the new parameter into `server/app.py`**

In `compute_template_results`, change the `build_training_plan` call (currently inside the `for rank, player in enumerate(ranked_players, ...)` loop's `training_plans` dict comprehension):

```python
            "training_plans": {
                env: format_training_plan(
                    build_training_plan(
                        skills, ENV_WEIGHTS[env], coordinates, player["coordinates"],
                        player["signature_skill_id"], top_n=TRAINING_PLAN_TOP_N,
                    ),
                    skills_by_id,
                    drills_by_key,
                )
                for env in environment_codes()
            },
```

And add `is_signature` to `format_training_plan`'s per-item output:

```python
        formatted.append({
            "skill_id": item["skill_id"],
            "name_zh": skill["name_zh"],
            "P": item["P"],
            "level": level,
            "is_signature": item["is_signature"],
            "metric": {
                "action": metric["action"],
                "denominator": metric["denominator"],
                "direction": metric["direction"],
                "threshold": metric["thresholds"][level],
            },
            "drills": drills_by_key.get((item["skill_id"], level), []),
        })
```

- [ ] **Step 6: Update `server/test_app.py`'s expectations**

Grep for any test asserting an empty training plan or a fixed plan length:

Run: `grep -n "training_plans\|is_signature\|trainingEmpty" server/test_app.py`

For any test that currently builds a payload specifically to produce an empty `training_plans[env]` (e.g. targeting a player whose coordinates are all at/below the user's), update its assertion: the plan is no longer `[]`; it's a one-item list whose single item has `is_signature: True` and `skill_id` equal to that player's `signature_skill_id` (look up the fixture player in the loaded `data/zh/球員.json` to know which skill that is, or read it off the player dict already in the test's own fixture setup). Add one new test:

```python
    def test_every_top_10_training_plan_has_a_signature_item_first(self):
        response = self.client.post("/api/template-results", json=self.full_payload())
        data = response.get_json()

        for player in data["top_10"]:
            for env_code, plan in player["training_plans"].items():
                self.assertGreaterEqual(len(plan), 1, f"{player['name']} / {env_code} has an empty plan")
                self.assertTrue(plan[0]["is_signature"], f"{player['name']} / {env_code} doesn't lead with the signature skill")
```

(Adjust `self.full_payload()` to whatever this test file's existing helper for a complete valid payload is actually named — read the file to confirm before using a name that doesn't exist.)

- [ ] **Step 7: Run the server test suite**

Run: `cd server && PYTHONPATH=../src:.. ../.venv/bin/python3 -m unittest test_app -v 2>&1 | tail -60 && cd ..`
Expected: all pass.

- [ ] **Step 8: Update `src/ui/index.html` — signature badge + the "already ahead" message**

Add a new UI string to all three `UI_STRINGS` language blocks (next to `levelLabels`/`trainingEmpty`):

```js
      signatureSkillLabel: "招牌技能",
```
```js
      signatureSkillLabel: "招牌技能",
```
(zh-Hans block — identical characters, no simplification needed here)
```js
      signatureSkillLabel: "Signature Skill",
```
(en block)

Update the `trainingEmpty` string's wording in all three languages to the spec's exact phrasing (keep the key name `trainingEmpty` even though it's no longer shown only when the list is empty — renaming it is optional polish, not required):

```js
      trainingEmpty: "你在這些面向已經不輸這位球員。",
```
```js
      trainingEmpty: "你在这些面向已经不输这位球员。",
```
```js
      trainingEmpty: "You already hold your own against this player in these areas.",
```

In `renderSkillItem`, add the badge next to the level tag:

```js
  function renderSkillItem(item) {
    const s = t();
    const planHtml = item.drills.map(renderDrillContent).join("");
    const volumeHtml = item.drills
      .map((drill) => drillVolumeText(drill))
      .filter((volume) => volume)
      .map((volume) => `<p class="drill-line"><span class="drill-label">${s.drillVolumeLabel}</span>${escapeHtml(volume)}</p>`)
      .join("");
    return `
      <div class="skill-item">
        <div class="skill-item-head">
          <span class="skill-item-name">${escapeHtml(item.name_zh)}</span>
          ${item.is_signature ? `<span class="signature-tag">${s.signatureSkillLabel}</span>` : ""}
          <span class="skill-level-tag">${s.levelLabels[item.level]}</span>
        </div>
        ${planHtml ? `<div class="drill-plan">${planHtml}</div>` : ""}
        ${volumeHtml ? `<div class="drill-volume">${volumeHtml}</div>` : ""}
      </div>`;
  }
```

Add a `.signature-tag` style near `.skill-level-tag`'s existing CSS rule (match its visual weight -- find that rule first and mirror its font-size/padding/border-radius, giving `.signature-tag` a distinct accent color so it doesn't read as a second difficulty badge).

Update `renderTrainingBody` so the "already ahead" sentence appears ALONGSIDE the signature-only plan, not instead of it (today's `plan.length === 0` branch can no longer trigger in practice, since the plan is never empty now, but leave it as a defensive fallback rather than deleting it):

```js
  function renderTrainingBody(player, plan) {
    const radarHtml = buildRadarSvg(state.results.coordinates, player.coordinates, escapeHtml(player.name));
    const skillsHtml = plan.length === 0
      ? `<p class="training-empty">${t().trainingEmpty}</p>`
      : plan.map(renderSkillItem).join("")
        + (plan.length === 1 && plan[0].is_signature ? `<p class="training-empty">${t().trainingEmpty}</p>` : "");
    return `
      <div class="training-body">
        <div class="training-radar">${radarHtml}</div>
        <div class="training-skills">${skillsHtml}</div>
      </div>`;
  }
```

- [ ] **Step 9: Run the full i18n parity test and a manual browser check**

Run: `PYTHONPATH=src .venv/bin/python3 -m unittest tests.engine.test_i18n_parity -v`
Expected: pass (this task didn't touch the three JSON data folders' structure, only `index.html`'s JS, which that test doesn't cover -- this run is a sanity check that Task 1's earlier edits are still fine, not a check of this task's own changes).

Then start the dev server and walk through the results page by hand in all three languages (`?lang=zh`, `?lang=zh-Hans`, `?lang=en` query param or however the UI's language switcher works), specifically a target player whose every axis is at/below the test user's (to hit the signature-only case) and one with a clear gap (to see the badge next to a non-empty list). Confirm the badge renders, confirm the "already ahead" sentence appears below the signature card in that specific case, confirm nothing else regressed.

- [ ] **Step 10: Commit**

```bash
git add src/engine/training_plan.py tests/engine/test_training_plan.py server/app.py server/test_app.py src/ui/index.html
git commit -m "Make the signature skill always lead the training plan, with a 25% relative threshold on the rest"
```

---

## Task 7: Simulate the proposed archetype classification and report — ends at a mandatory checkpoint

> **OUTCOME (2026-10, after Task 9 and the final whole-branch review): Tasks 7 and 8 were implemented, reviewed clean, then REVERTED.** The Task 7 checkpoint's normal-distribution-fit correction to `compute_user_size` stopped the literal collapse-to-identical-values bug, but the final whole-branch review found the corrected version still put realistic users' body size at 0.03/0.48/4.3 (10th/50th/90th percentile) — all far below the 28-point threshold separating the smallest archetype anchor from the next one — so in practice almost everyone still landed on the same single archetype, and this skewed the dominant relative-strength branch too (not just the flat-answer case), while the new "based on your build" UI copy made an explicit claim that was false for most users. The human partner ruled: revert the whole redesign, restore the original `classify_archetype_by_majority` neighbor-vote scheme, and leave item 5 as an open problem for a future, differently-designed attempt. See the ledger (`.superpowers/sdd/2026-10-07-result-accuracy-fixes/progress.md`) for the full finding and the revert commit. The rest of this plan (items 1, 2/3/4, 7, and the calibration work) is unaffected and shipped as designed.

**This task ends in a report, not a code change.** It produces no commit and touches no tracked file. It is deliberately scoped to stop exactly where the spec requires a human decision ("實作前要先確認...我確認後再實作"). If dispatching this as a subagent task, its report back to the controller IS the deliverable — the controller then relays the findings to the human partner and only dispatches Task 8 once a go-ahead comes back.

**Files:** none tracked. A throwaway scratch script, written anywhere outside the repo's tracked paths, is deleted at the end of this task.

**Interfaces:**
- Consumes: nothing from earlier tasks (this is read-only analysis against the real data files, using the formula below reimplemented inline in the scratch script — not yet in `archetype.py`).
- Produces: a report (the four findings below) for the human partner. Task 8 is the task that actually produces `classify_archetype_for_user` and `compute_user_size` for other tasks to consume — nothing here is a durable interface.

- [ ] **Step 1: Throwaway simulation of the proposed classification — before writing any production code**

This step produces no commit and touches no tracked file. Write a scratch script (anywhere outside the repo's tracked paths, e.g. the worktree's own untracked scratch area) that, for a range of synthetic users, applies the PROPOSED formula below on paper (reimplemented inline in the scratch script, not yet in `archetype.py`) and reports:

1. For 900 users with axis scores drawn the same way `scripts/simulate_results.py` draws them (random 1-5 per question, same height/weight distribution): the resulting distribution of archetype ids, and what fraction land in the `>= 25 spread` (relative-strength) branch versus the `< 25` (body-only) branch.
2. For users who answer EVERY axis question with the same fixed score (try 1, 3, and 5), paired with height/weight drawn from the same distribution: confirm the spread is 0 in all three cases (so they all land in body-only), and report the resulting archetype distribution as height/weight alone varies -- this is the spec's specific "全選同一分數" acceptance check, done early as a design sanity check, not yet the final graded run.
3. Whether any single archetype's share of all 900 users exceeds 40%.
4. Whether `archetype_mode == "body_only"` plus the top-10 table's #1 player ever disagree sharply enough to look wrong (e.g. the archetype name implies a center-sized player while the #1 displayed player is a guard) -- spot-check 10 cases by eye.

The proposed formula for the scratch script (this is literally what Step 3 below will put into `archetype.py` once approved):

```python
STYLE_AXES = ("A", "B1", "B2", "C1", "C2")  # D excluded, same set skill_gap trains on

def style_axis_spread(coordinates):
    values = [coordinates[axis] for axis in STYLE_AXES]
    return max(values) - min(values)

def recentered(coordinates):
    mean = sum(coordinates[axis] for axis in STYLE_AXES) / len(STYLE_AXES)
    return {axis: coordinates[axis] - mean for axis in STYLE_AXES}

def relative_strength_distance(coordinates, archetype, size):
    user_c = recentered(coordinates)
    arch_c = recentered(archetype["coordinates"])
    squared = sum((user_c[axis] - arch_c[axis]) ** 2 for axis in STYLE_AXES)
    if size is not None and "size" in archetype:
        squared += (archetype["size"] - size) ** 2
    return squared ** 0.5
```

- [ ] **Step 2: Delete the scratch script** (it was never tracked; this step is just a reminder that nothing from Step 1 belongs in the commit history).

**This task's report to the controller/human partner must include the four numbers/observations from Step 1.** This is the plan's second mandatory checkpoint (see the plan header). Task 8 does not start — no line of `src/engine/archetype.py` gets touched — until the human partner has seen this report and said to proceed. If the distribution looks badly skewed (one archetype dominating, or body-only/relative-strength split looking wrong), the fix is to discuss it with the human partner, not to silently tweak `ARCHETYPE_SPREAD_THRESHOLD` and re-run until a report looks acceptable.

---

## Task 8: Implement archetype classification redesign (spec item 5)

> **REVERTED after the final whole-branch review — see the note at the top of Task 7.**

**Files:**
- Modify: `src/engine/archetype.py`
- Modify: `server/app.py` (`compute_template_results`'s archetype classification block)
- Modify: `scripts/run_player_match.py` (same classification call, plus its printed report)
- Modify: `src/ui/index.html` (one new UI string × 3 languages, one conditional in the headline render)
- Test: `tests/engine/test_archetype.py` (rewritten — `classify_archetype_by_majority`'s tests removed, new tests added)
- Test: `server/test_app.py` (new assertion that the response carries an archetype mode)

**Interfaces:**
- Consumes: Task 7's go-ahead (the human partner's response to that task's report). `engine.archetype.classify_archetype` (unchanged), `engine.archetype.compute_player_sizes` (still used by nothing after this task except its own tests — see Step 5; confirm before deleting it too, since the spec only names `classify_archetype_by_majority` for removal). The formula this task implements is exactly what Task 7's scratch script already validated — do not redesign it here, only productionize it.
- Produces: `classify_archetype_for_user(coordinates, archetypes, size=None, spread_threshold=ARCHETYPE_SPREAD_THRESHOLD)` returning `(archetype_dict, mode)` where `mode` is the literal string `"relative_strength"` or `"body_only"`. `compute_user_size(user_body, players)` returning a float or `None`. No other task consumes these, so there's no cross-task interface to keep in sync.

- [ ] **Step 1: Write the failing tests**

Add to `tests/engine/test_archetype.py` (keep `ClassifyArchetypeTest` and `ComputePlayerSizesTest` as-is; replace `ClassifyArchetypeByMajorityTest` entirely — see Step 7 for why):

```python
from engine.archetype import (
    ARCHETYPE_SPREAD_THRESHOLD,
    classify_archetype,
    classify_archetype_for_user,
    compute_player_sizes,
    compute_user_size,
    style_axis_spread,
)


class StyleAxisSpreadTest(unittest.TestCase):
    def test_max_minus_min_over_the_five_style_axes_only(self):
        # D is deliberately excluded -- a huge D-axis gap must not count.
        coords = {"A": 10, "B1": 90, "B2": 50, "C1": 50, "C2": 50, "D": 0}
        self.assertEqual(style_axis_spread(coords), 80)

    def test_flat_answers_give_zero_spread(self):
        coords = {"A": 50, "B1": 50, "B2": 50, "C1": 50, "C2": 50, "D": 50}
        self.assertEqual(style_axis_spread(coords), 0)


class ComputeUserSizeTest(unittest.TestCase):
    # 2026-10 Task 7 checkpoint finding: ranking the user's raw height/weight
    # within the player pool (the same method compute_player_sizes uses for
    # players) collapses almost every simulated user to percentile ~0,
    # because a typical self-reporting user (~175cm) falls below the
    # shortest real NBA player (~185cm) -- see the plan's Task 7 report.
    # compute_user_size instead fits a NORMAL distribution to the pool's own
    # real height_cm/weight_kg (mean/sd from the pool itself) and reads the
    # user's percentile off that curve, so it extrapolates smoothly below
    # the pool's observed floor instead of collapsing everyone there to the
    # same value. This is still the SAME 0-100 scale the archetype "size"
    # anchors in data/zh/原型.json were calibrated on (compute_player_sizes'
    # empirical rank and this normal approximation agree closely for values
    # WITHIN the pool's own range; they diverge only below/above it, which is
    # exactly the case compute_player_sizes couldn't handle).
    POOL = [
        {"id": "a", "body": {"height_cm": 190, "weight_kg": 90}},
        {"id": "b", "body": {"height_cm": 210, "weight_kg": 110}},
    ]
    # height pool mean=200/sd=10, weight pool mean=100/sd=10 (by construction).

    def test_user_at_the_pools_mean_gets_the_50th_percentile(self):
        user_size = compute_user_size({"height_cm": 200, "weight_kg": 100}, self.POOL)

        self.assertAlmostEqual(user_size, 50.0)

    def test_user_below_the_pools_observed_minimum_gets_a_small_but_nonzero_value(self):
        # 180cm is below BOTH pool members (190, 210) -- an empirical rank
        # (compute_player_sizes' method) would give exactly 0 here. The
        # normal-fit extrapolation must NOT collapse to 0.
        user_size = compute_user_size({"height_cm": 180, "weight_kg": 80}, self.POOL)

        self.assertGreater(user_size, 0.0)
        self.assertLess(user_size, 10.0)  # still clearly "small" -- a long way below the mean
        # hand-computed: z = (180-200)/10 = -2.0 for both fields ->
        # 50*(1+erf(-2/sqrt(2))) = 50*(1+erf(-1.41421356)) ~= 2.275
        self.assertAlmostEqual(user_size, 2.275, places=2)

    def test_two_users_below_the_floor_still_get_different_differentiated_values(self):
        # the whole point of the fix: two users BOTH below the pool's
        # observed minimum must still get two DIFFERENT percentiles,
        # ordered the same way their actual height/weight are ordered --
        # not both collapsed to the same floor value.
        higher = compute_user_size({"height_cm": 180, "weight_kg": 80}, self.POOL)
        lower = compute_user_size({"height_cm": 160, "weight_kg": 60}, self.POOL)

        self.assertGreater(higher, lower)
        self.assertGreater(lower, 0.0)

    def test_returns_none_when_user_body_missing_height_or_weight(self):
        self.assertIsNone(compute_user_size({"height_cm": 180}, self.POOL))
        self.assertIsNone(compute_user_size({}, self.POOL))

    def test_returns_none_when_no_player_has_body_data(self):
        players = [{"id": "a"}]
        self.assertIsNone(compute_user_size({"height_cm": 180, "weight_kg": 75}, players))

    def test_returns_none_when_fewer_than_two_players_have_body_data(self):
        players = [{"id": "a", "body": {"height_cm": 190, "weight_kg": 90}}]
        self.assertIsNone(compute_user_size({"height_cm": 180, "weight_kg": 75}, players))

    def test_returns_none_when_pool_has_zero_variance(self):
        # every player in the pool has the exact same height/weight -> sd=0
        # -> a normal-distribution fit is undefined, not a division-by-zero
        # crash.
        players = [
            {"id": "a", "body": {"height_cm": 200, "weight_kg": 100}},
            {"id": "b", "body": {"height_cm": 200, "weight_kg": 100}},
        ]
        self.assertIsNone(compute_user_size({"height_cm": 190, "weight_kg": 90}, players))


class ClassifyArchetypeForUserTest(unittest.TestCase):
    def setUp(self):
        self.archetypes = [
            {"id": "guard_shape", "name_zh": "控球型", "coordinates": {"A": 90, "B1": 50, "B2": 10, "C1": 50, "C2": 10, "D": 50}, "size": 20},
            {"id": "big_shape", "name_zh": "低位型", "coordinates": {"A": 10, "B1": 10, "B2": 90, "C1": 10, "C2": 50, "D": 50}, "size": 80},
        ]

    def test_high_spread_user_classified_by_relative_strength_ignoring_overall_level(self):
        # overall level is very high across the board, but the SHAPE (A is
        # the standout, by 50+ points over every other style axis) matches
        # guard_shape's shape, not big_shape's -- a plain (non-recentered)
        # distance would be dominated by the uniformly-high level instead.
        coordinates = {"A": 95, "B1": 60, "B2": 20, "C1": 60, "C2": 20, "D": 60}
        self.assertGreaterEqual(style_axis_spread(coordinates), ARCHETYPE_SPREAD_THRESHOLD)

        archetype, mode = classify_archetype_for_user(coordinates, self.archetypes, size=25)

        self.assertEqual(archetype["id"], "guard_shape")
        self.assertEqual(mode, "relative_strength")

    def test_low_spread_user_classified_by_size_alone(self):
        # every style axis is close together (spread < 25) -- the shape
        # carries no signal, so only size should decide the outcome.
        coordinates = {"A": 50, "B1": 55, "B2": 52, "C1": 48, "C2": 53, "D": 50}
        self.assertLess(style_axis_spread(coordinates), ARCHETYPE_SPREAD_THRESHOLD)

        archetype, mode = classify_archetype_for_user(coordinates, self.archetypes, size=18)

        self.assertEqual(archetype["id"], "guard_shape")  # size 20 is closer to 18 than 80 is
        self.assertEqual(mode, "body_only")

    def test_spread_exactly_at_threshold_uses_relative_strength(self):
        # spec: >= 25 is relative-strength, so the boundary itself is inclusive.
        coordinates = {"A": 50 + ARCHETYPE_SPREAD_THRESHOLD, "B1": 50, "B2": 50, "C1": 50, "C2": 50, "D": 50}
        self.assertEqual(style_axis_spread(coordinates), ARCHETYPE_SPREAD_THRESHOLD)

        _, mode = classify_archetype_for_user(coordinates, self.archetypes, size=50)

        self.assertEqual(mode, "relative_strength")

    def test_body_only_tie_breaks_on_ascending_archetype_id(self):
        tied_archetypes = [
            {"id": "z_archetype", "coordinates": {"A": 50, "B1": 50, "B2": 50, "C1": 50, "C2": 50, "D": 50}, "size": 40},
            {"id": "a_archetype", "coordinates": {"A": 50, "B1": 50, "B2": 50, "C1": 50, "C2": 50, "D": 50}, "size": 60},
        ]
        coordinates = {"A": 50, "B1": 50, "B2": 50, "C1": 50, "C2": 50, "D": 50}

        archetype, mode = classify_archetype_for_user(coordinates, tied_archetypes, size=50)

        self.assertEqual(archetype["id"], "a_archetype")
        self.assertEqual(mode, "body_only")

    def test_body_only_falls_back_to_relative_strength_when_size_is_none(self):
        coordinates = {"A": 50, "B1": 55, "B2": 52, "C1": 48, "C2": 53, "D": 50}

        archetype, mode = classify_archetype_for_user(coordinates, self.archetypes, size=None)

        self.assertEqual(mode, "relative_strength")

    def test_raises_when_archetypes_is_empty(self):
        with self.assertRaises(ValueError):
            classify_archetype_for_user({"A": 50, "B1": 50, "B2": 50, "C1": 50, "C2": 50, "D": 50}, [])
```

- [ ] **Step 2: Run to verify these fail**

Run: `PYTHONPATH=src .venv/bin/python3 -m unittest tests.engine.test_archetype -v 2>&1 | tail -40`
Expected: `ImportError` for the four new names, then (once that's fixed by Step 3's imports alone, before the real implementation) `AttributeError`/`NotImplementedError`-shaped failures for every new test.

- [ ] **Step 3: Implement `style_axis_spread`, `compute_user_size`, and `classify_archetype_for_user`**

Add to `src/engine/archetype.py` (keep `classify_archetype` and `compute_player_sizes` exactly as they are):

```python
ARCHETYPE_SPREAD_THRESHOLD = 25.0  # 暫定，見 spec item 5：每軸兩題平均，分數
# 只會是 12.5 的倍數，高低差小於 25 代表五軸全部落在相鄰兩格以內。
STYLE_AXES_FOR_SPREAD = ("A", "B1", "B2", "C1", "C2")  # D excluded -- athletic
# ability isn't part of "which skill are you strongest at".


def style_axis_spread(coordinates):
    """max - min over the five trainable style axes (A/B1/B2/C1/C2) -- D is
    excluded, same set skill_gap trains on. Used to decide whether a user
    has a real standout strength (classify by shape) or not (classify by
    body alone) -- see classify_archetype_for_user."""
    values = [coordinates[axis] for axis in STYLE_AXES_FOR_SPREAD]
    return max(values) - min(values)


def _recentered(coordinates):
    mean = sum(coordinates[axis] for axis in STYLE_AXES_FOR_SPREAD) / len(STYLE_AXES_FOR_SPREAD)
    return {axis: coordinates[axis] - mean for axis in STYLE_AXES_FOR_SPREAD}


def _relative_strength_distance(coordinates, archetype, size):
    user_centered = _recentered(coordinates)
    archetype_centered = _recentered(archetype["coordinates"])
    squared = sum(
        (user_centered[axis] - archetype_centered[axis]) ** 2 for axis in STYLE_AXES_FOR_SPREAD
    )
    if size is not None and "size" in archetype:
        squared += (archetype["size"] - size) ** 2 * SIZE_AXIS_WEIGHT
    return math.sqrt(squared)


def _pool_normal_fit_percentile(value, pool_values):
    """Percentile (0-100) of value under a normal distribution fit to
    pool_values' OWN mean/sd (computed from pool_values itself, not a fixed
    external constant), via the standard erf-based CDF.

    Unlike a plain rank-within-pool percentile (compute_player_sizes'
    method), this extrapolates smoothly below the pool's observed minimum
    (or above its maximum) instead of collapsing every value past the edge
    to the same 0 or 100 -- see compute_user_size's docstring for why this
    matters (2026-10, Task 7 checkpoint finding).

    Raises ValueError if pool_values has fewer than 2 values, or its
    variance is 0 (a normal fit is undefined when every value is
    identical).
    """
    if len(pool_values) < 2:
        raise ValueError("pool must have at least 2 values; percentile fit is undefined")
    mean = sum(pool_values) / len(pool_values)
    variance = sum((v - mean) ** 2 for v in pool_values) / len(pool_values)
    if variance == 0:
        raise ValueError("pool has zero variance; normal fit is undefined")
    sd = math.sqrt(variance)
    z = (value - mean) / sd
    return 50 * (1 + math.erf(z / math.sqrt(2)))


def compute_user_size(user_body, players):
    """Return the user's body size (0-100) on the SAME 0-100 scale the
    archetype "size" anchors (data/zh/原型.json, 25-87) were calibrated on.

    2026-10 (Task 7 checkpoint finding): this does NOT rank the user within
    the player pool the way compute_player_sizes ranks a player -- a plain
    empirical rank collapses almost every self-reporting user to
    percentile ~0, because a typical user (~175cm) falls below the
    shortest real NBA player (~185cm), below the entire pool's observed
    floor. Simulating 300 users with a flat answer profile (so this
    function was the ONLY thing deciding their archetype) showed 99-100%
    landing on the same single archetype regardless of their actual height
    or weight -- the body-only branch carried no real signal.

    Instead, this fits a NORMAL distribution to THIS SPECIFIC players
    pool's own real height_cm/weight_kg (mean & sd computed from the pool
    itself -- the current and all-time pools have different real
    distributions, so this is never a fixed constant) and reads the user's
    percentile off that curve via _pool_normal_fit_percentile. This agrees
    closely with compute_player_sizes' empirical rank for values WITHIN the
    pool's own observed range, but -- unlike that rank -- extrapolates
    smoothly below/above the pool's floor/ceiling instead of collapsing
    every out-of-range value to the same number.

    Returns None if user_body is missing height_cm or weight_kg, if fewer
    than 2 players in `players` have both fields, or if the pool's
    height/weight values have zero variance (a degenerate pool where a
    normal fit is undefined).
    """
    if "height_cm" not in user_body or "weight_kg" not in user_body:
        return None
    with_body = [
        p for p in players
        if "height_cm" in p.get("body", {}) and "weight_kg" in p.get("body", {})
    ]
    if len(with_body) < 2:
        return None
    height_pool = [p["body"]["height_cm"] for p in with_body]
    weight_pool = [p["body"]["weight_kg"] for p in with_body]
    try:
        height_pct = _pool_normal_fit_percentile(user_body["height_cm"], height_pool)
        weight_pct = _pool_normal_fit_percentile(user_body["weight_kg"], weight_pool)
    except ValueError:
        return None
    return (height_pct + weight_pct) / 2


def classify_archetype_for_user(coordinates, archetypes, size=None, spread_threshold=ARCHETYPE_SPREAD_THRESHOLD):
    """Classify the USER's own coordinates directly against the archetype
    anchors -- replaces the old neighbor-majority-vote approach (2026-10,
    spec item 5): a user who answers every question the same way no longer
    gets dumped into whatever archetype their nearest (equally-flat)
    neighbors happen to be voted into.

    style_axis_spread(coordinates) >= spread_threshold (a real standout
    strength exists): classify by SHAPE -- both the user and each
    archetype are recentered (each axis minus that entity's own five-axis
    mean) before comparing, so overall level cancels out and only "which
    block are you strongest in" matters. Body size still factors in
    exactly as classify_archetype already does (added to the squared
    distance when both `size` and the archetype's own "size" field are
    present).

    style_axis_spread(coordinates) < spread_threshold (no standout -- a
    flat or near-flat answer profile): classify by BODY SIZE ALONE among
    archetypes that have a "size" field, picking the closest; ties (or a
    genuinely missing `size`) break on ascending archetype id for
    determinism. If `size` itself is None (no body data to compare), this
    falls back to the shape-based classification above instead -- there is
    no signal to pick a body-only answer from.

    Returns (archetype, mode) where mode is the literal string
    "relative_strength" or "body_only", so callers can choose the matching
    UI copy. Raises ValueError if archetypes is empty.
    """
    if not archetypes:
        raise ValueError("archetypes must not be empty; classification is undefined")

    spread = style_axis_spread(coordinates)
    if spread >= spread_threshold or size is None:
        winner = min(archetypes, key=lambda a: _relative_strength_distance(coordinates, a, size))
        return winner, "relative_strength"

    with_size = [a for a in archetypes if "size" in a]
    if not with_size:
        winner = min(archetypes, key=lambda a: _relative_strength_distance(coordinates, a, size))
        return winner, "relative_strength"

    winner = min(with_size, key=lambda a: (abs(a["size"] - size), a["id"]))
    return winner, "body_only"
```

- [ ] **Step 4: Run to verify all new tests pass**

Run: `PYTHONPATH=src .venv/bin/python3 -m unittest tests.engine.test_archetype -v 2>&1 | tail -40`
Expected: all pass, including the untouched `ClassifyArchetypeTest` and `ComputePlayerSizesTest` classes.

- [ ] **Step 5: Confirm `classify_archetype_by_majority` has no remaining callers, then remove it**

Run: `grep -rn "classify_archetype_by_majority" --include="*.py" .`
Expected (after Steps 6-7 below update the two call sites): only its own definition and its own tests. Delete the function from `src/engine/archetype.py` and delete the entire `ClassifyArchetypeByMajorityTest` class from `tests/engine/test_archetype.py`. Do this step LAST, after Steps 6-7, so the grep genuinely shows zero remaining callers rather than the ones you haven't updated yet.

- [ ] **Step 6: Update `server/app.py`'s classification call**

Replace:
```python
    player_sizes = compute_player_sizes(players)
    user_body_pct, players_pct, body_field_ranges_pct = percentile_normalize_body(
        user_body, players, body_field_ranges
    )
```
with:
```python
    user_size = compute_user_size(user_body, players)
    user_body_pct, players_pct, body_field_ranges_pct = percentile_normalize_body(
        user_body, players, body_field_ranges
    )
```
(note: `compute_user_size` must run on the RAW `players`/`user_body`, same as the old `compute_player_sizes(players)` line it replaces -- both must come BEFORE `percentile_normalize_body` overwrites `user_body`/`players` into the population-percentile scale; this ordering requirement is exactly what archetype.py's own header comment already warns about.)

Replace:
```python
    archetype = classify_archetype_by_majority(ranked_players, archetypes, player_sizes=player_sizes)
```
with:
```python
    archetype, archetype_mode = classify_archetype_for_user(coordinates, archetypes, size=user_size)
```

Update the import line:
```python
from engine.archetype import classify_archetype_for_user, compute_user_size  # noqa: E402
```

And add `archetype_mode` to the returned dict (next to the existing `"archetype"` key):
```python
        "archetype": {"name_zh": archetype["name_zh"], "flavor": archetype["flavor"]},
        "archetype_mode": archetype_mode,
```

- [ ] **Step 7: Update `scripts/run_player_match.py`'s classification call and its printed report**

Replace:
```python
    player_sizes = compute_player_sizes(players)
    user_body_pct, players_pct, body_field_ranges_pct = percentile_normalize_body(
        user_body, players, body_field_ranges
    )
```
with:
```python
    user_size = compute_user_size(user_body, players)
    user_body_pct, players_pct, body_field_ranges_pct = percentile_normalize_body(
        user_body, players, body_field_ranges
    )
```

Replace:
```python
    archetype = classify_archetype_by_majority(ranked, archetypes, player_sizes=player_sizes)
    print(f"\n球場定位原型：{archetype['name_zh']}")
```
with:
```python
    archetype, archetype_mode = classify_archetype_for_user(coordinates, archetypes, size=user_size)
    label = "球場定位原型" if archetype_mode == "relative_strength" else "以你的身材，最適合往以下方向發展"
    print(f"\n{label}：{archetype['name_zh']}")
```

Update the import line:
```python
from engine.archetype import classify_archetype_for_user, compute_user_size  # noqa: E402
```

- [ ] **Step 8: Run the grep from Step 5 again to confirm zero remaining callers, then delete the function and its tests**

Run: `grep -rn "classify_archetype_by_majority" --include="*.py" .`
Expected: no output. Now delete `classify_archetype_by_majority` from `src/engine/archetype.py` and `ClassifyArchetypeByMajorityTest` from `tests/engine/test_archetype.py`.

- [ ] **Step 9: Run the full engine + server test suite**

Run: `PYTHONPATH=src .venv/bin/python3 -m unittest discover -s tests -t . -p "test_*.py" && cd server && PYTHONPATH=../src:.. ../.venv/bin/python3 -m unittest test_app && cd ..`
Expected: all green. If `server/test_app.py` has an assertion on the shape of the `archetype` key that doesn't yet know about `archetype_mode`, add one:

```python
    def test_response_includes_an_archetype_mode(self):
        response = self.client.post("/api/template-results", json=self.full_payload())
        data = response.get_json()

        self.assertIn(data["archetype_mode"], ("relative_strength", "body_only"))
```

(again, confirm the real helper-method name for a full valid payload before using `self.full_payload()` literally.)

- [ ] **Step 10: Update `src/ui/index.html` for the body-only phrasing**

Add one new UI string per language (next to the other archetype-related strings), taking the archetype name as an argument:

```js
      archetypeBodyOnlyLabel: (name) => `以你的身材，最適合往${name}方向發展`,
```
```js
      archetypeBodyOnlyLabel: (name) => `以你的身材，最适合往${name}方向发展`,
```
```js
      archetypeBodyOnlyLabel: (name) => `Based on your build, you're best suited to develop toward ${name}`,
```

In the headline-card render (around the `archetype-name` div), branch on the new `archetype_mode` field:

```js
          <div class="archetype-name">${
            data.archetype_mode === "body_only"
              ? escapeHtml(t().archetypeBodyOnlyLabel(data.archetype.name_zh))
              : escapeHtml(data.archetype.name_zh)
          }</div>
```

- [ ] **Step 11: Manual browser check**

Start the dev server, submit a questionnaire with every axis answered identically (e.g. all 3s) plus a short and a tall body in two separate runs, and confirm the headline shows the "以你的身材,最適合往...方向發展" phrasing and that it changes between the two runs. Then submit a questionnaire with one clearly dominant axis and confirm the headline reverts to the plain name, unchanged from before this task.

- [ ] **Step 12: Commit**

```bash
git add src/engine/archetype.py tests/engine/test_archetype.py server/app.py server/test_app.py scripts/run_player_match.py src/ui/index.html
git commit -m "Classify archetypes from the user's own coordinates instead of neighbor majority vote"
```

---

## Task 9: Final acceptance run, documentation sync

**Files:**
- No new production code expected; this task is verification + documentation. If the simulation surfaces a genuine bug, fix it here under `systematic-debugging`, with its own test, before writing the report.
- Modify: `CLAUDE.md`, `SPEC.md` (relevant sections), header comments in `src/engine/body_fit.py`, `src/engine/player_matching.py`, `src/engine/training_plan.py`, `src/engine/archetype.py` (only where Tasks 1-8 changed behavior those headers describe and haven't already updated it).

**Interfaces:** none new.

- [ ] **Step 1: Run the full automated suite one more time**

Run: `PYTHONPATH=src .venv/bin/python3 -m unittest discover -s tests -t . -p "test_*.py" && cd server && PYTHONPATH=../src:.. ../.venv/bin/python3 -m unittest test_app && cd ..`
Expected: all green. Paste the actual pass counts into the final report (the spec explicitly asks for this).

- [ ] **Step 2: Run the simulation harness against both pools at full scale**

Run:
```
PYTHONPATH=src:. .venv/bin/python3 scripts/simulate_results.py --pool current --n 900 --seed 20261007
PYTHONPATH=src:. .venv/bin/python3 scripts/simulate_results.py --pool alltime --n 900 --seed 20261007
```
Expected: for each pool, read off and report every number against the spec's acceptance criteria list:
- all-10-one-star % < 5%
- best-star histogram spans more than one bucket
- top-1 concentration <= 10% (both pools)
- height correlation >= 0.6
- 206cm/113kg case: body-fit template still ~206cm
- empty-training-plan % == 0 (should be trivially true now; report it anyway)
- menu variety mean > 7

- [ ] **Step 3: Run the dedicated flat-answer archetype check**

Extend `scripts/simulate_results.py` (or write a second small CLI invocation using the same imported pipeline, your choice, but it must use the same fixed seed discipline as the rest of this plan) to generate ~300 users who answer every axis question with the same fixed score, with height/weight drawn from the calibration distribution, and report the resulting archetype id distribution and its max single-archetype share. Expected: max share <= 40%, and spot-check that varying only height/weight (holding the flat score constant) is what's actually driving the archetype changes, not the flat score itself.

- [ ] **Step 4: Fix anything that fails, with its own failing-test-first cycle**

If any criterion fails, use `systematic-debugging` to find the actual cause (don't retune a threshold constant just to make a report number cross a line) -- write a test that reproduces the failure in the relevant `tests/engine/*.py` file, watch it fail, fix the `engine` function, watch it pass, re-run the full suite, re-run the simulation, and only then continue.

- [ ] **Step 5: Update documentation headers**

- `src/engine/body_fit.py`: header already documents the pre-2026-10 tail-capped scheme; add a short note describing the segmented transition-weight blend from Task 3 (what it is, why, the four new constants) in the same terse style as the existing comments -- don't rewrite the whole header, append.
- `src/engine/player_matching.py`: the header's calibration-method paragraph (lines 21-33) was already updated in Task 5 Step 1; just confirm it still accurately describes the FINAL thresholds (post-checkpoint) and the resolved "+7" decision.
- `src/engine/training_plan.py`: header currently only documents the two difficulty constants; add the `TRAINING_PLAN_RELATIVE_THRESHOLD` constant and the signature-skill-always-first rule.
- `src/engine/archetype.py`: header currently documents the now-deleted majority-vote scheme at length; replace that section with the new direct-classification scheme (spread threshold, two branches, `compute_user_size`'s scale, deterministic tie-break) -- this header needs the heaviest rewrite of the four, since its subject changed the most.
- `CLAUDE.md`: update the one-sentence project summary's question count if Task 1 changed it (it didn't -- bounds changed, not the count), and anywhere it describes the old training-plan/archetype behavior.
- `SPEC.md`: update whichever numbered sections describe G_i/archetype classification/star calibration to match what's actually implemented now.

- [ ] **Step 6: Final report to the human partner**

Report, in one message:
- Every acceptance criterion from the spec with its actual measured number (not a pass/fail guess -- the number itself).
- The full list of provisional constants and their final values: `HEIGHT_TRANSITION_LOW/HIGH`, `WEIGHT_TRANSITION_LOW/HIGH`, the two calibrated threshold tuples (and whatever was decided about the flat "+7" adjustment at the Task 4→5 checkpoint), `TRAINING_PLAN_RELATIVE_THRESHOLD`, `ARCHETYPE_SPREAD_THRESHOLD`, the calibration sampling distribution (175/7, 70/12), and the four new body-measurement floors.
- Anything from the spec that couldn't be done as written, or that you implemented differently, and why (this plan's two checkpoints already surfaced the biggest judgment calls -- if a smaller one came up during execution, e.g. the Review Focus items, report it here too).

- [ ] **Step 7: Do not commit documentation-only changes separately from the fixes they document** -- if Step 4 produced no code fixes, one commit for this task is enough:

```bash
git add CLAUDE.md SPEC.md src/engine/body_fit.py src/engine/player_matching.py src/engine/training_plan.py src/engine/archetype.py
git commit -m "Sync documentation headers and project docs with the result-accuracy fixes"
```

If Step 4 did produce code fixes, each fix gets its own commit at the point it was made (per `systematic-debugging` / TDD discipline), and this step's commit is documentation-only, same as above.

---

## Self-Review Notes

**Spec coverage:** item 7 -> Task 1. Item 1 -> Task 3. Calibration -> Task 4 (report) + Task 5 (apply). Items 2/3/4 -> Task 6. Item 5 -> Task 7 (report) + Task 8 (implement). Item 6 ("不另外處理") -> covered by Task 9's historical-pool simulation run, no dedicated code task needed, matching the spec's own "做完第1項就會改善" framing. The two "實作前先確認/校準後給我看" gates -> the Task 4→5 and Task 7→8 boundaries. Documentation sync -> Task 9.

**Placeholder scan:** every step above either contains real code or is a real shell command with a real expected-output description; Task 4 and Task 7 are intentionally report-only tasks (they are literally "ask a human" steps the spec itself mandates) and are marked as checkpoints, not left as vague TODOs.

**Type consistency:** `build_training_plan`'s new `signature_skill_id` parameter name and `is_signature` field name are used identically in Task 6's engine code, test code, `server/app.py`, and `src/ui/index.html`. `classify_archetype_for_user`'s `mode` return value (`"relative_strength"` / `"body_only"`) and `archetype_mode` field name are used identically across Task 8's engine code, test code, `server/app.py`, and `src/ui/index.html`.

**Review Focus:** all five items each have an explicit test in their owning task (transition-boundary continuity and single-player pool in Task 3; missing env weight for the signature skill in Task 6; the spread-exactly-25 boundary and the body-only tie-break in Task 8).

**Note on splitting Task 4/7 from Task 5/8:** these splits were made specifically to support Subagent-Driven Development execution — a dispatched implementer subagent runs to completion and cannot itself pause mid-task to hold a conversation with the human partner. Ending Task 4 and Task 7 exactly at the checkpoint, as their own dispatchable units, lets the controller (not a subagent) relay the report and gate the next dispatch on the human partner's answer.
