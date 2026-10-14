# GL-040 Translation Quality Benchmark Report

**Milestone:** GL-040.2.3 (Decoupled Scoring, Input Alignment & Runtime Safety Metrics)
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

In **GL-040.2 through GL-040.2.3**, the evaluation framework has been completely restructured into a **decoupled, reproducible benchmark architecture** (`gamelingo.benchmark.evaluator`):
- **Decoupled Annotations**: Manual review annotations are stored separately in [`annotations_gl040.json`](file:///e:/GameLingo/src/gamelingo/benchmark/annotations_gl040.json) and pinned to the exact target text via SHA-256 hashes (`reviewed_target_hash`) and prompt context hashes (`reviewed_context_hash`). If an output changes, previous annotations are automatically invalidated and marked `pending_review`/`stale`.
- **Programmatic Passthrough Detection**: `expected_behavior` and reference parity are used to separate intentional passthrough from Japanese text requiring translation. Correctly unchanged technical identifiers are verified as valid passthroughs.
- **Strict Input Alignment (GL-040.2.3)**: Dataset items and raw translation records are matched by unique, stable item ID (`align_benchmark_inputs`). Missing, extra, duplicate, or mismatched records reject execution fail-closed.
- **Explicit Runtime Safety Metric (GL-040.2.3)**: Programmatic verification explicitly distinguishes basic structural validity ($82.0\%$) from runtime engine safety ($77.0\%$). Structurally valid text containing unexpected interpolation tokens (e.g. `[Current life]`) is classified as unsafe.
- **Timing Fallback Elimination (GL-040.2.3)**: Silent fallback durations have been removed. Throughput availability is tracked explicitly ($5.80\text{ items/sec}$ over $17.25\text{s}$ recorded duration).
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

## 3. Corrected Benchmark Metrics (GL-040.2 / GL-040.2.3)

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

### 3.3 Runtime Safety (Ren'Py Token & Crash Prevention — GL-040.2.3)
- **Runtime-Safe Outputs**: $77$ (**$77.0\%$**, Denominator: $N_{\text{total}} = 100$)
- **Runtime Unsafe Outputs**: $23$ (**$23.0\%$**, Denominator: $N_{\text{total}} = 100$)
  - $8$ Pipeline Error Rejections (dropped sentinels)
  - $6$ Truncated Fragments
  - $4$ Untranslated Japanese Fallbacks
  - $5$ Unexpected Ren'Py Interpolation Tokens in Multiline Cards (`bench_086`, `bench_088`, `bench_089`, `bench_092`, `bench_093`)
- **Safety Criterion**: An item is runtime-safe only if `structural_status == "Valid" and error is None and placeholder_status != "Fail"`.
- **Structural Validity ($82\%$) vs Runtime Safety ($77\%$)**: While 82 outputs are structurally valid non-empty English, 5 of them introduce unescaped square brackets (e.g. `[Current life]`, `[Sky]`, `[Resis ]`, `[degradation]`, `[Monstering and Human Hands]`). In Ren'Py text display, unescaped brackets trigger Python variable interpolation and name-lookup crashes at runtime. Thus, these 5 strings are classified as unsafe for game execution.
- *Limitation*: Static token and syntax verification only; does not guarantee arbitrary dynamic game scripts will not raise unhandled exceptions during execution.

### 3.4 Intentional Passthrough Handling
- **Passthrough Expected Strings**: $12$ ($N_{\text{pass\_exp}} = 12$)  
  *Identified via `reference == source_text` and `expected_behavior`.*
- **Verbatim Exact Matches**: $5$ (**$41.7\%$**, Denominator: $N_{\text{pass\_exp}}$)  
  *`[cur_foe.name]`, `SAVE`, `mat`, `END`, `----` preserved unchanged.*
- **Model Mutations**: $3$ (**$25.0\%$**, Denominator: $N_{\text{pass\_exp}}$)  
  *`CONFIG` -> `HOME` (hallucination), `fruit` -> `Fruit` (casing), `food` -> `Food` (casing).*
- **Pipeline Rejections**: $4$ (**$33.3\%$**, Denominator: $N_{\text{pass\_exp}}$)  
  *`{color...}`, `[_gl_unlocked]...`, `{size=17}...`, `{size=15}...` rejected due to sentinel loss.*

### 3.5 Placeholder & Formatting Integrity
- **Strings with Markup / Variables / Newlines**: $25$ ($N_{\text{markup}} = 25$)
- **Markup Preserved Intact**: $12$ (**$48.0\%$**, Denominator: $N_{\text{markup}}$)  
  *Includes 5 multiline cards with 100% intact line breaks and 7 variable cards with preserved sentinels.*
- **Markup Rejected or Lost**: $13$ (**$52.0\%$**, Denominator: $N_{\text{markup}}$)  
  * $8$ safely rejected by `PlaceholderProtector` fail-closed gate in `variables_tags`.  
  * $5$ detected by GL-040.2.2 complete inventory checks in `multiline` (`bench_086`, `bench_088`, `bench_089`, `bench_092`, `bench_093`) where translation introduced unexpected Ren'Py square bracket interpolation tokens (e.g. `[Current life]`, `[Sky]`, `[Resis ]`, `[degradation]`, `[Monstering and Human Hands]`), which would trigger syntax errors during engine execution.

### 3.6 Human Linguistic Quality (Strictly Reviewed Outputs)
- **Reviewed Outputs**: $100$ ($N_{\text{reviewed}} = 100$, **$100.0\%$** coverage of historical outputs)
- **Pending Manual Review**: $0$ ($0.0\%$)
- **Average Meaning Score**: **$2.81$ / $5.00$** (Denominator: $N_{\text{reviewed}} = 100$)
- **Average Grammar Score**: **$3.08$ / $5.00$** (Denominator: $N_{\text{reviewed}} = 100$)
- **Acceptable Translation Quality** ($\text{Meaning} \ge 3 \land \text{Grammar} \ge 3$): **$54$ / $100$** (**$54.0\%$**, Denominator: $N_{\text{reviewed}} = 100$)

### 3.7 Execution Timing & Throughput (GL-040.2.3)
- **Total Benchmark Duration**: **$17.25\text{s}$** (strictly accumulated from positive recorded translation durations; no silent fallback)
- **Throughput**: **$5.80\text{ items/sec}$** (available: true)

> [!IMPORTANT]
> **Hierarchical Quality Distinction**
> GameLingo distinguishes multiple orthogonal tiers of quality:
> 1. **Pipeline Execution ($92.0\%$)**: Provider calls that complete without dropped sentinel exceptions.
> 2. **Structural Validity ($82.0\%$)**: Non-empty, non-error, non-truncated text surviving translation.
> 3. **Runtime Safety ($77.0\%$)**: Structurally valid text without syntax-crashing unexpected Ren'Py interpolation tokens.
> 4. **Markup Integrity ($48.0\%$)**: Complete source-target placeholder token parity across strings with markup.
> 5. **Passthrough Accuracy ($41.7\%$)**: Technical strings preserved verbatim.
> 6. **Acceptable Translation Quality ($54.0\%$)**: Human-reviewed semantic fidelity ($\text{Meaning} \ge 3 \land \text{Grammar} \ge 3$). In particular, fluent hallucinations (e.g. `うぅ……おなか、すいた……` -> `"Home"`) are structurally valid English but severe semantic failures. GameLingo explicitly separates syntactic survival from human quality approval.

---

## 4. Category Breakdown Under Corrected Evaluation

| Category | Count | Structural Valid % | Runtime Safe % | Reviewed Count | Avg Meaning (0-5) | Avg Grammar (0-5) | Acceptable % (M>=3 & G>=3) | Untranslated | Truncated | Error |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **UI & Menu Labels** | 18 | 83.3% | 83.3% | 18 | **4.11** | **4.06** | **83.3%** | 2 | 1 | 0 |
| **Technical & Code** | 7 | 100.0% | 100.0% | 7 | **4.14** | **5.00** | **85.7%** | 0 | 0 | 0 |
| **Multiline Text** | 10 | 100.0% | **50.0%** | 10 | **2.60** | **2.60** | **60.0%** | 0 | 0 | 0 |
| **Dynamic & Status** | 15 | 86.7% | 86.7% | 15 | **2.67** | **3.13** | **46.7%** | 0 | 2 | 0 |
| **Dialogue & Narration** | 35 | 85.7% | 85.7% | 35 | **2.46** | **2.89** | **42.9%** | 2 | 3 | 0 |
| **Variables & Tags** | 15 | 46.7% | 46.7% | 15 | **1.73** | **1.73** | **33.3%** | 0 | 0 | 8 |
| **Overall Summary** | **100** | **82.0%** | **77.0%** | **100** | **2.81** | **3.08** | **54.0%** | **4** | **6** | **8** |

---

## 5. Side-by-Side Comparison: Frozen Baseline vs Corrected Evaluation (GL-040.2 / GL-040.2.3)

The table below contrasts the frozen GL-040.1 baseline snapshot against the corrected GL-040.2 through GL-040.2.3 evaluation:

| Dimension / Metric | Frozen GL-040.1 Baseline | Corrected GL-040.2 / GL-040.2.3 Evaluation | Primary Rationale for Difference |
| :--- | :---: | :---: | :--- |
| **Evaluation Architecture** | Hardcoded item-ID branches in runner script | Decoupled `evaluator.py` + hash-pinned `annotations_gl040.json` | Eliminates hardcoded score assignments; changing target text automatically invalidates stale annotation. |
| **Input Alignment & Identity** | Relied on implicit list order | **Strict 1-to-1 ID Match (`align_benchmark_inputs`)** | Matches by stable item ID; rejects missing, extra, duplicate, or mismatched records fail-closed. |
| **Intentional Passthroughs (`SAVE`, `mat`, `END`, `----`)** | Penalized as untranslated failures ($0/5$, Untranslated) | Scored as valid passthroughs ($5/5$, Valid) | Corrected handling based on explicit boolean metadata and reference parity. |
| **Technical Category Meaning Score** | 1.57 / 5.00 | **4.14 / 5.00** | 4 valid passthroughs are no longer miscategorized as untranslated errors. |
| **Variables Category Meaning Score** | 1.40 / 5.00 | **1.73 / 5.00** | Passthrough variable `[cur_foe.name]` correctly scored as valid passthrough. |
| **Overall Meaning Score** | 2.58 / 5.00 | **2.81 / 5.00** | Direct mathematical consequence of correcting intentional passthroughs. |
| **Overall Grammar Score** | 2.83 / 5.00 | **3.08 / 5.00** | Passthrough identifiers have perfect grammatical validity. |
| **Structural Validity Metric** | 75.0% "Pass Rate" (conflated with quality) | **82.0% Structural Validity Rate** | Structural validity ($82.0\%$) explicitly distinguished from Acceptable Quality ($54.0\%$). |
| **Runtime Safety Rate** | Not distinguished (conflated with Pass Rate) | **77.0% Runtime Safety Rate** | Programmatically isolates 5 multiline items with unexpected Ren'Py syntax from safe outputs ($82 - 5 = 77$). |
| **Acceptable Translation Quality** | Not explicitly reported | **54.0% (54 / 100)** | Defined as reviewed items with Meaning $\ge 3$ and Grammar $\ge 3$. |
| **Placeholder / Tag Integrity** | Mixed into category tables | **48.0% (12 / 25 intact)** | Complete inventory check detects missing source tokens and unexpected output tokens ($N_{\text{markup}} = 25$). |
| **Review Invalidation Safety** | None (static script) | **Strict Context & Target Hash Pinning** | Recomputed hashes validate annotation integrity; corrupted or legacy records fail closed. |
| **Duration & Throughput** | Silent 14.15s fallback | **17.25s (5.80 items/sec)** | Fallback eliminated; throughput derived strictly from verified positive durations. |

---

## 6. Verification & Automated Test Evidence (GL-040.2 through GL-040.2.3)

The evaluation methodology and its hardened integrity checks are verified by 21 dedicated automated unit tests in [`tests/unit/test_quality_benchmark.py`](file:///e:/GameLingo/tests/unit/test_quality_benchmark.py):
1. **Complete Placeholder Inventory Checks**: Proves programmatic checks compare source and target inventories, catching missing tokens, dropped occurrences (`%d/%d` vs `%d/`), duplicated tokens (`%d` vs `%d %d`), missing closing tags (`{b}...{/b}`), and unexpected target tokens (`%d` vs `%d %s`, or plain text vs `%s`).
2. **Unexpected Placeholder Syntax Rejection**: Proves introducing placeholder syntax into strings without source markup fails with `has_markup=True` and clear diagnostic details.
3. **Newline Count Parity**: Proves exact newline preservation validation across multiline cards (lost or added newlines fail).
4. **Strict Boolean Passthrough Metadata**: Proves `passthrough_expected` must be a strict boolean, rejecting string values (`"false"`, `"true"`) and numbers (`1`, `0`) with `TypeError`.
5. **Japanese Passthrough Safeguard Conflict Rejection**: Proves setting `passthrough_expected=True` for Japanese text raises a `ValueError` validation error.
6. **Annotation Target Hash Consistency**: Proves recomputed target hash must match stored `reviewed_target_hash`; corrupted hashes fail closed with `review_status="invalid"`.
7. **Annotation Context Hash Consistency**: Proves recomputed context hash must match stored `reviewed_context_hash`; corrupted context hashes fail closed with `review_status="invalid"`.
8. **Legacy Annotation Protection**: Proves annotations missing required context fields fail closed with `review_status="pending_review"`.
9. **Stale / Invalid Exclusion**: Proves stale, corrupted, and pending review annotations are cleanly excluded from quality score averages.
10. **Exact UTF-8 Whitespace Invalidation**: Proves leading, trailing, or newline modifications strictly invalidate annotations.
11. **Context Change Invalidation**: Proves modifying prompt context (source, reference, category) invalidates the annotation even if target text matches.
12. **Passthrough Handling**: Proves `SAVE`, `mat`, `END`, `----` are recognized as `is_passthrough_expected=True`, assigned `passthrough_status="Pass"`, and excluded from untranslated failures.
13. **Untranslated Japanese Fallback Detection**: Proves Japanese dialogue left untranslated is flagged as `Untranslated Japanese Fallback`.
14. **Structural Validity vs Quality Separation**: Proves hallucinated outputs like `"Home"` are marked `structural_status="Valid"` but excluded from acceptable quality passes (`meaning_score=1`).
15. **Frozen Baseline Verification**: Loads [`gl040_1_baseline_snapshot.json`](file:///e:/GameLingo/src/gamelingo/benchmark/results/gl040_1_baseline_snapshot.json) and verifies historical numbers ($2.58$ meaning, $2.83$ grammar, $1.57$ technical) and byte-for-byte SHA-256 (`024cb0d7536f22aefd10b6522f35f8c13941a36d2ae37c1885c3780496b1a361`).
16. **Deterministic Aggregation & Explicit Denominators**: Verifies all metric groups use explicit denominators and produce identical results across repeated runs.
17. **Dataset Schema Verification**: Proves all 100 items in `dataset_gl040_real_game.json` satisfy `validate_benchmark_item()`.
18. **Input Alignment Validation (GL-040.2.3)**: Proves 1-to-1 input alignment by unique item ID, rejecting duplicates, missing records, extra records, and missing ID fields with descriptive errors, while preserving dataset item ordering across reordered raw records.
19. **Runtime Safety Distinction (GL-040.2.3)**: Proves structurally valid translations with unexpected Ren'Py brackets (e.g. `[Current life]`) fail placeholder integrity and are marked `is_runtime_safe=False`, cleanly separating syntax safety from syntactic non-emptiness.
20. **Duration Validation & Throughput Availability (GL-040.2.3)**: Proves timing fallbacks are removed; missing (`None`) or nonpositive (`0.0`) durations report `throughput_available=False` and `None` timing metrics, whereas valid positive durations accurately compute throughput.
21. **Input Alignment Rejection in Recompute (GL-040.2.3)**: Proves `recompute_benchmark_evaluation()` cleanly raises `ValueError` or exits with status 1 on misaligned inputs when `exit_on_error=True`.

---

## 7. Integrity Checklist (GL-040.2.3)

| Requirement | Implementation | Verified Status |
| :--- | :--- | :---: |
| **Complete Token Inventory Check** | Compares `Counter(source_tokens)` and `Counter(target_tokens)` | **Passed** |
| **Unexpected Placeholder Detection** | Flags tokens in target absent from source; no silent `N/A` | **Passed** |
| **Strict Boolean Passthrough Metadata** | Rejects non-boolean types (`"false"`, `1`) with `TypeError` | **Passed** |
| **Japanese Content Conflict Guard** | Setting `passthrough_expected=True` with Japanese raises `ValueError` | **Passed** |
| **Annotation Target Hash Consistency** | Recomputed target hash must match stored `reviewed_target_hash` | **Passed** |
| **Annotation Context Hash Consistency** | Recomputed context hash must match stored `reviewed_context_hash` | **Passed** |
| **Legacy Incomplete Annotation Shield** | Missing context fields fail closed with `pending_review` | **Passed** |
| **Input Alignment & 1-to-1 ID Matching** | `align_benchmark_inputs()` matches by unique ID; rejects missing/extra/duplicates | **Passed** |
| **Explicit Runtime Safety Metric** | Separates syntax-crashing Ren'Py brackets ($77.0\%$) from structural validity ($82.0\%$) | **Passed** |
| **Timing Fallback Elimination** | Missing/nonpositive durations set `throughput_available=False`; no silent constants | **Passed** |
| **Frozen Snapshot File Integrity** | Full file SHA-256 `024cb0d7536f...` verified in tests | **Passed** |
| **Offline Recompute Capability** | `recompute_benchmark_evaluation()` updates evaluation without live translation | **Passed** |


