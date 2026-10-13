# GL-040 Translation Quality Benchmark Report

**Milestone:** GL-040.2 (Decoupled & Reproducible Scoring Update)  
**Date:** 2026-10-14  
**Engine Under Test:** Ren'Py 8.5.0.25111603 (Visual Novel)  
**Source Game Fixture:** `island-1.0-win` (Japanese visual novel; 2,412 extracted units across 11 script/screen files)  
**Translation Provider:** `ArgosTranslateProvider` (`gamelingo.translation.argos_provider`)  
**Route / Model:** Japanese to English (`ja` -> `en`, Argos model package `translate-ja_en` version 1.1)  
**Execution Mode:** 100% Offline, Local-first  

---

## 1. Executive Summary & Methodology Correction

In GL-040.1, GameLingo established an initial translation benchmark across 100 real source strings. However, review identified three key methodological defects in the initial evaluation harness:
1. **Coupled Item-ID Scoring**: Quality scores were hardcoded in item-ID branches within the runner script, which could re-apply old manual scores even if a different translation output was generated.
2. **Conflation of Structural Validity with Semantic Quality**: Structurally intact outputs (such as non-empty hallucinated text like `"Home"`) were reported as "Pass", conflating basic syntactic survival with translation fidelity.
3. **Flawed Passthrough Handling**: Intentional passthroughs (e.g. `SAVE`, `mat`, `END`, `----`, and variable tags) that correctly remained unchanged were flagged as `IDENTICAL_TO_SOURCE` and penalized as untranslated failures ($0/5$).

In **GL-040.2**, the evaluation framework has been completely restructured into a **decoupled, reproducible benchmark architecture** (`gamelingo.benchmark.evaluator`):
- **Decoupled Annotations**: Manual review annotations are stored separately in [`annotations_gl040.json`](file:///e:/GameLingo/src/gamelingo/benchmark/annotations_gl040.json) and pinned to the exact target text via SHA-256 hashes (`reviewed_target_hash`). If an output changes, previous annotations are automatically invalidated and marked `pending_review`/`stale`.
- **Programmatic Passthrough Detection**: `expected_behavior` and reference parity are used to separate intentional passthrough from Japanese text requiring translation. Correctly unchanged technical identifiers are verified as valid passthroughs.
- **Explicit, Distinct Metrics**: Structural validity, fail-closed pipeline safety, intentional passthrough accuracy, formatting integrity, and human linguistic quality are reported as distinct metrics with explicit denominators.
- **Frozen Baseline Preservation**: The historical GL-040.1 baseline is preserved verbatim in [`gl040_1_baseline_snapshot.json`](file:///e:/GameLingo/src/gamelingo/benchmark/results/gl040_1_baseline_snapshot.json).

---

## 2. Decoupled Evaluation Architecture

```
+--------------------------------------------------------------------------------+
|                   GL-040.2 Decoupled Evaluation Architecture                   |
+--------------------------------------------------------------------------------+
| 1. Translation Execution (ArgosTranslateProvider)                              |
|    - Runs TranslationRequest across 100 curated strings                        |
|    - Captures raw outputs, execution durations, and pipeline exceptions        |
+--------------------------------------------------------------------------------+
| 2. Programmatic Structural & Markup Verification (evaluator.py)                |
|    - evaluate_structural_status(): Valid, Untranslated, Truncated, Empty, Error |
|    - evaluate_placeholder_integrity(): Verifies variables/tags/newlines        |
|    - is_passthrough_expected(): Flags intentional passthroughs                 |
+--------------------------------------------------------------------------------+
| 3. Hash-Pinned Human Annotation Lookup (annotations_gl040.json)                |
|    - Computes sha256(current_target_text)                                      |
|    - Exact Match   -> review_status: "reviewed", loads Meaning/Grammar scores  |
|    - Mismatch/New  -> review_status: "stale" / "pending_review", scores = None |
+--------------------------------------------------------------------------------+
| 4. Metric Aggregator with Explicit Denominators                                |
|    - Structural Validity Rate = Valid / Total                                  |
|    - Passthrough Accuracy Rate = Matched / Passthrough Expected                |
|    - Placeholder Integrity Rate = Intact / Strings With Markup                 |
|    - Human Meaning & Grammar Averages = Sum / Reviewed Count ONLY              |
|    - Acceptable Quality Rate = (Meaning>=3 & Grammar>=3) / Reviewed Count       |
+--------------------------------------------------------------------------------+
```

---

## 3. Corrected Benchmark Metrics (GL-040.2)

All metrics below document their exact denominators explicitly:

### 3.1 Pipeline Execution & Call Safety
- **Provider Calls Attempted**: $100$ ($N_{\text{total}} = 100$)
- **Provider Calls Succeeded**: $92$ (**$92.0\%$**, Denominator: $N_{\text{total}}$)
- **Pipeline Fail-Closed Rejections**: $8$ (**$8.0\%$**, Denominator: $N_{\text{total}}$)  
  *All 8 rejections were triggered by `PlaceholderProtector` detecting dropped sentinels in dense formatting strings.*

### 3.2 Structural Validity (Syntactic Integrity)
- **Structurally Valid Outputs**: $82$ (**$82.0\%$**, Denominator: $N_{\text{total}}$)
- **Untranslated Japanese Fallbacks**: $4$ (**$4.0\%$**, Denominator: $N_{\text{total}}$)  
  *Non-passthrough Japanese lines returning unchanged source text: `bench_001`, `bench_005`, `bench_039`, `bench_040`.*
- **Truncated Fragments / Word Damage**: $6$ (**$6.0\%$**, Denominator: $N_{\text{total}}$)  
  *Dropped dialogue (`......`), lone kana (`ブ`), lone kanji (`大`), and space truncation (`  .`)*
- **Pipeline Error Rejections**: $8$ (**$8.0\%$**, Denominator: $N_{\text{total}}$)

### 3.3 Intentional Passthrough Handling
- **Passthrough Expected Strings**: $12$ ($N_{\text{pass\_exp}} = 12$)  
  *Identified via `reference == source_text` and `expected_behavior`.*
- **Verbatim Exact Matches**: $5$ (**$41.7\%$**, Denominator: $N_{\text{pass\_exp}}$)  
  *`[cur_foe.name]`, `SAVE`, `mat`, `END`, `----` preserved unchanged.*
- **Model Mutations**: $3$ (**$25.0\%$**, Denominator: $N_{\text{pass\_exp}}$)  
  *`CONFIG` -> `HOME` (hallucination), `fruit` -> `Fruit` (casing), `food` -> `Food` (casing).*
- **Pipeline Rejections**: $4$ (**$33.3\%$**, Denominator: $N_{\text{pass\_exp}}$)  
  *`{color...}`, `[_gl_unlocked]...`, `{size=17}...`, `{size=15}...` rejected due to sentinel loss.*

### 3.4 Placeholder & Formatting Integrity
- **Strings with Markup / Variables / Newlines**: $25$ ($N_{\text{markup}} = 25$)
- **Markup Preserved Intact**: $17$ (**$68.0\%$**, Denominator: $N_{\text{markup}}$)  
  *Includes 100% (10/10) line break (`\n`) preservation across all multiline cards.*
- **Markup Rejected or Lost**: $8$ (**$32.0\%$**, Denominator: $N_{\text{markup}}$)  
  *All 8 safely rejected by `PlaceholderProtector` fail-closed gate.*

### 3.5 Human Linguistic Quality (Strictly Reviewed Outputs)
- **Reviewed Outputs**: $100$ ($N_{\text{reviewed}} = 100$, **$100.0\%$** coverage of historical outputs)
- **Pending Manual Review**: $0$ ($0.0\%$)
- **Average Meaning Score**: **$2.81$ / $5.00$** (Denominator: $N_{\text{reviewed}} = 100$)
- **Average Grammar Score**: **$3.08$ / $5.00$** (Denominator: $N_{\text{reviewed}} = 100$)
- **Acceptable Translation Quality** ($\text{Meaning} \ge 3 \land \text{Grammar} \ge 3$): **$54$ / $100$** (**$54.0\%$**, Denominator: $N_{\text{reviewed}} = 100$)

> [!IMPORTANT]
> **Structural Validity ($82.0\%$) vs Acceptable Translation Quality ($54.0\%$)**  
> While $82\%$ of strings successfully cleared the pipeline without syntax errors or truncation, only $54\%$ convey acceptable semantic meaning. In particular, fluent hallucinations (e.g. `うぅ……おなか、すいた……` -> `"Home"`) are structurally valid English but severe semantic failures. GameLingo explicitly separates syntactic survival from human quality approval.

---

## 4. Category Breakdown Under Corrected Evaluation

| Category | Count | Structural Valid % | Reviewed Count | Avg Meaning (0-5) | Avg Grammar (0-5) | Acceptable % (M>=3 & G>=3) | Untranslated | Truncated | Error |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **UI & Menu Labels** | 18 | 83.3% | 18 | **4.11** | **4.06** | **83.3%** | 2 | 1 | 0 |
| **Technical & Code** | 7 | 100.0% | 7 | **4.14** | **5.00** | **85.7%** | 0 | 0 | 0 |
| **Multiline Text** | 10 | 100.0% | 10 | **2.60** | **2.60** | **60.0%** | 0 | 0 | 0 |
| **Dynamic & Status** | 15 | 86.7% | 15 | **2.67** | **3.13** | **46.7%** | 0 | 2 | 0 |
| **Dialogue & Narration** | 35 | 85.7% | 35 | **2.46** | **2.89** | **42.9%** | 2 | 3 | 0 |
| **Variables & Tags** | 15 | 46.7% | 15 | **1.73** | **1.73** | **33.3%** | 0 | 0 | 8 |
| **Overall Summary** | **100** | **82.0%** | **100** | **2.81** | **3.08** | **54.0%** | **4** | **6** | **8** |

---

## 5. Side-by-Side Comparison: Frozen Baseline vs Corrected Evaluation

The table below contrasts the frozen GL-040.1 baseline snapshot against the corrected GL-040.2 evaluation:

| Dimension / Metric | Frozen GL-040.1 Baseline | Corrected GL-040.2 Evaluation | Primary Rationale for Difference |
| :--- | :---: | :---: | :--- |
| **Evaluation Architecture** | Hardcoded item-ID branches in runner script | Decoupled `evaluator.py` + hash-pinned `annotations_gl040.json` | Eliminates hardcoded score assignments; changing target text automatically invalidates stale annotation. |
| **Intentional Passthroughs (`SAVE`, `mat`, `END`, `----`)** | Penalized as untranslated failures ($0/5$, Untranslated) | Scored as valid passthroughs ($5/5$, Valid) | Corrected handling based on `expected_behavior` and reference parity. |
| **Technical Category Meaning Score** | 1.57 / 5.00 | **4.14 / 5.00** | 4 valid passthroughs are no longer miscategorized as untranslated errors. |
| **Variables Category Meaning Score** | 1.40 / 5.00 | **1.73 / 5.00** | Passthrough variable `[cur_foe.name]` correctly scored as valid passthrough. |
| **Overall Meaning Score** | 2.58 / 5.00 | **2.81 / 5.00** | Direct mathematical consequence of correcting intentional passthroughs. |
| **Overall Grammar Score** | 2.83 / 5.00 | **3.08 / 5.00** | Passthrough identifiers have perfect grammatical validity. |
| **Structural Validity Metric** | 75.0% "Pass Rate" (conflated with quality) | **82.0% Structural Validity Rate** | Structural validity ($82.0\%$) explicitly distinguished from Acceptable Quality ($54.0\%$). |
| **Acceptable Translation Quality** | Not explicitly reported | **54.0% (54 / 100)** | Defined as reviewed items with Meaning $\ge 3$ and Grammar $\ge 3$. |
| **Placeholder / Tag Integrity** | Mixed into category tables | **68.0% (17 / 25 intact)** | Evaluated programmatically and reported with explicit denominator ($N_{\text{markup}} = 25$). |
| **Review Invalidation Safety** | None (static script) | **Strict SHA-256 target pinning** | Any run producing differing output is marked `pending_review` with unassigned scores. |

---

## 6. Verification & Automated Test Evidence

The corrected evaluation methodology is verified by 7 dedicated automated unit tests in [`tests/unit/test_quality_benchmark.py`](file:///e:/GameLingo/tests/unit/test_quality_benchmark.py):
1. **Annotation Invalidation**: Proves modifying a translated output marks its review status as `stale`, sets `meaning_score` to `None`, and increments `pending_review_count`.
2. **Passthrough Handling**: Proves `SAVE`, `mat`, `END`, `----` are recognized as `is_passthrough_expected=True`, assigned `passthrough_status="Pass"`, and excluded from untranslated failures.
3. **Untranslated Japanese Detection**: Proves Japanese dialogue left untranslated is flagged as `Untranslated Japanese Fallback`.
4. **Structural Validity vs Quality Separation**: Proves hallucinated outputs like `"Home"` are marked `structural_status="Valid"` but excluded from acceptable quality passes (`meaning_score=1`).
5. **Frozen Baseline Verification**: Loads [`gl040_1_baseline_snapshot.json`](file:///e:/GameLingo/src/gamelingo/benchmark/results/gl040_1_baseline_snapshot.json) and verifies historical numbers ($2.58$ meaning, $2.83$ grammar, $1.57$ technical) remain unchanged.
6. **Denominator Explicit Accuracy**: Verifies all 5 metric groups use correct denominators and produce identical deterministic results.
7. **Direct Function Verification**: Tests `evaluate_placeholder_integrity` and `evaluate_structural_status` directly.

**Test Suite Execution**:
- Pytest: **270 passed in 21.04s**
- Ruff Linter: **All checks passed**
- Ruff Formatter: **91 files formatted**
