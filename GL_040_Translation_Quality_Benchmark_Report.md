# GL-040 Real Translation Quality Benchmark Report

**Milestone:** GL-040.1  
**Date:** 2026-10-14  
**Engine Under Test:** Ren'Py 8.5.0.25111603 (Visual Novel)  
**Source Game Fixture:** `island-1.0-win` (Japanese visual novel; 2,412 extracted units across 11 script/screen files)  
**Translation Provider:** `ArgosTranslateProvider` (`gamelingo.translation.argos_provider`)  
**Route / Model:** Japanese to English (`ja` -> `en`, Argos model package `translate-ja_en` version 1.1)  
**Execution Mode:** 100% Offline, Local-first  

---

## 1. Executive Summary

In milestone GL-040.1, GameLingo moves beyond synthetic translation markers (e.g. `[EN] text`) to measure the quality of machine translations on **100 genuine source strings** extracted directly from a real Japanese Ren'Py 8.5 game (`island-1.0-win`).

The benchmark was executed using GameLingo's production translation pipeline (`TranslationRequest`, `PlaceholderProtector`, `ArgosTranslateProvider`, and automated validation rules in `gamelingo.translation.validation`). Outputs were evaluated against a standardized game localization rubric covering:
1. **Meaning & Context Preservation** (0 to 5)
2. **Grammar & Phrasing** (0 to 5)
3. **Terminology & Consistency** (Pass / Inconsistent / Fail / N/A)
4. **Placeholder & Markup Integrity** (Pass / Warn / Fail / N/A)
5. **Structural Validity** (Valid / Untranslated / Truncated / Empty / Error)

### Key Metrics Summary

| Metric | Measured Value | Notes |
| :--- | :---: | :--- |
| **Total Benchmark Items** | 100 | Sampled across 6 distinct categories |
| **Overall Meaning Score** | **2.58 / 5.00** | Acceptable for basic UI; substantial drift in dialogue/context |
| **Overall Grammar Score** | **2.83 / 5.00** | Comprehensible in short sentences; broken in complex narration |
| **Pipeline Throughput** | **7.0 items/sec** | 14.19 seconds total translation execution time |
| **Valid Pass Rate** | **75.0%** | 75/100 outputs syntactically valid and non-empty |
| **Fail-Closed Placeholder Errors** | **8.0%** (8/100) | Rejected by `PlaceholderProtector` due to NMT sentinel drops |
| **Untranslated Fallback Rate** | **9.0%** (9/100) | Safely defaulted to source Japanese on empty/whitespace MT |
| **Truncated / Damaged Rate** | **8.0%** (8/100) | Partial words, lone kanji, or sentence fragments |

---

## 2. Environment & Dependency Audit

Before executing benchmark translations, the local runtime environment was audited to confirm model availability and prevent fabricated claims:

1. **ArgosTranslate**:
   - `argostranslate` is installed in the active Python 3.12 environment (`uv sync --group argos`).
   - Verified local package: `ja -> en` (`translate-ja_en` v1.1, CC0 model weights, MIT code).
   - No other Argos language pairs (`en -> ja`, `zh -> en`, `ko -> en`) are installed locally.
2. **Hugging Face / OPUS-MT / Transformers**:
   - `transformers` and `torch` are **not installed** in the active runtime venv.
   - Any claims of active local OPUS-MT translation without the optional `benchmark` dependency group are accurately reported as unavailable in this environment.
3. **Game Asset Integrity**:
   - The master game directory `D:\New folder\island-1.0-win` was treated as strictly read-only.
   - All string extraction was performed via `RenPyAdapter.extract()` directly in memory and cached locally.
   - No original game files or archives were modified or patched during this benchmark.

---

## 3. Dataset Composition

The 100 benchmark items were curated from 2,412 extracted translation units in `island-1.0-win`, representing real dialogue, UI layouts, dynamic gameplay state, embedded Ren'Py tags, and multiline card instructions.

```
+--------------------------------------------------------------------------+
|                     GL-040 Benchmark Dataset (N=100)                     |
+---------------------+-------+--------------------------------------------+
| Category            | Count | Representation                             |
+---------------------+-------+--------------------------------------------+
| Dialogue & Narration|  35   | Spoken speech, internal thoughts, sensory  |
| UI & Menu Labels    |  18   | Buttons, preferences, confirmation dialogs |
| Dynamic & Status    |  15   | Encounter names, combat state, minigames   |
| Variables & Tags    |  15   | [var], {color}, {size}, %s, %d specifiers  |
| Multiline Text      |  10   | Tutorial cards containing embedded \n      |
| Technical & Code    |   7   | ASCII keywords, state flags, separators    |
+---------------------+-------+--------------------------------------------+
```

---

## 4. Benchmark Results by Category

The table below summarizes performance across each of the 6 benchmark categories:

| Category | Items | Avg Meaning (0-5) | Avg Grammar (0-5) | Pass Rate | Valid | Pipeline Errors | Untranslated | Truncated |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **UI & Menu Labels** | 18 | **4.11** | **4.06** | **83.3%** | 15 | 0 | 2 | 1 |
| **Dynamic & Status** | 15 | **2.67** | **3.13** | **86.7%** | 13 | 0 | 0 | 2 |
| **Multiline Text** | 10 | **2.60** | **2.60** | **100.0%** | 10 | 0 | 0 | 0 |
| **Dialogue & Narration** | 35 | **2.46** | **2.89** | **80.0%** | 28 | 0 | 2 | 5 |
| **Technical & Code** | 7 | **1.57** | **2.14** | **42.9%** | 3 | 0 | 4 | 0 |
| **Variables & Tags** | 15 | **1.40** | **1.40** | **40.0%** | 6 | 8 | 1 | 0 |
| **Overall Total** | **100** | **2.58** | **2.83** | **75.0%** | **75** | **8** | **9** | **8** |

---

## 5. Detailed Category Analysis & Observed Failure Modes

### 5.1 UI and Menu Labels (Strongest Category — Score: 4.11 / 5)

Standard UI navigation commands and options performed best because conventional VN menu terms occur frequently in generic translation training corpora.

- **Clean Translations**:
  - `設定` -> `"Settings"` (Meaning: 5, Grammar: 5)
  - `ロード` -> `"Load"` (Meaning: 5, Grammar: 5)
  - `スタート` -> `"Start"` (Meaning: 5, Grammar: 5)
  - `タイトルに戻る` -> `"Back to Title"` (Meaning: 5, Grammar: 5)
  - `リプレイ終了` -> `"Replay End"` (Meaning: 5, Grammar: 4)
  - `ゲームを終了しますか？` -> `"End the game?"` (Meaning: 5, Grammar: 5)
  - `セーブを上書きしますか？` -> `"Overwrite save?"` (Meaning: 5, Grammar: 5)
- **Observed Failures**:
  - **Katakana Truncation**: `セーブ` (Save) was truncated to a single kana character `"ブ"` (Meaning: 1).
  - **Untranslated Fallback**: `スキップ` (Skip) and `オート` (Auto) produced empty translation strings from Argos, triggering GameLingo's fallback protection to retain the source text unchanged.

### 5.2 Dialogue and Narration (Mixed Quality — Score: 2.46 / 5)

Dialogue revealed the severe limitations of small offline sentence-level NMT models when translating literary, conversational, or ellipsis-heavy Japanese text without discourse context.

- **Acceptable & Fluent Output**:
  - `筋肉の塊みたいな男だった。` -> `"A man like a mass of muscle."` (Meaning: 5, Grammar: 5)
  - `まずは、動くしかない。` -> `"First of all, you have to move."` (Meaning: 5, Grammar: 4)
  - `でも、生き延びるには。この力が本当なら、立派な武器になる。` -> `"But to survive. If this power is true, it becomes a good weapon."` (Meaning: 4, Grammar: 4)
  - `あ……こんにちは` -> `"Hello"` (Meaning: 5, Grammar: 5)
- **Critical Failure Modes**:
  1. **Hallucination on Conversational Ellipses**:
     - `うぅ……おなか、すいた……` (Ugh... I'm so hungry...) -> `"Home"` (Score: 1/5)
     - `わりぃな。俺の方が先だ` (Sorry pal, I was here first) -> `"Home"` (Score: 1/5)
     - `——いた。ちょっと、あんた` (—There you are. Hey, you) -> `"Dutch Comment"` (Score: 1/5)
  2. **Inverted Polarity / Opposite Meaning**:
     - `何か食べないと。` (I have to eat something) -> `"Don’t eat anything."` (Score: 1/5)
     - `生き残りは、いったい何人いるんだろう。` (How many survivors are there, I wonder?) -> `"There are many people who live."` (Score: 1/5)
  3. **Content Loss on Emotional Gasps**:
     - `い、いえ、なんでも……っ` (N-No, it's nothing...) -> `"......"` (Dialogue text dropped completely)
     - `あった……っ` (Found it...!) -> `"......"` (Only dots preserved)
  4. **Lexical Hallucination**:
     - `木陰に女の子がひとり、しゃがみ込んでいた。` (A lone girl was crouching in the shade) -> `"A woman's child sneezed in the shade."` (`しゃがみ込んでいた` mistranslated as "sneezed")
     - `ピンクのパーカー。あどけない顔。` (Pink hoodie. An innocent face.) -> `"Pink sandals. I can't face."`

### 5.3 Dynamic and Status Text (Moderate Quality — Score: 2.67 / 5)

- **Strengths**:
  - Monster/creature nouns translated recognizably: `野犬` -> `"Dogs"`, `毒蛇` -> `"Poison Snake"`.
  - Notification text: `NEW  図鑑に登録` -> `"NEW Sign up for the book"`.
- **Failure Modes**:
  - **State Collapse / Ambiguity**: Opposite combat states (`こちらが押している` [We have upper hand] and `こちらが押されている` [We are being pushed back]) were both translated as the identical ambiguous string `"This is pressed"`.
  - **Severe Mistranslation**: `ならず者` (Rogue/Ruffian) translated as `"Others"`.
  - **Kanji Remnants**: `大猪` and `大男` both truncated to a single untranslated kanji `"大"`.

### 5.4 Variables and Formatting Tags (Critical Vulnerability — Score: 1.40 / 5)

This category revealed the vital protective role of GameLingo's `PlaceholderProtector`.

- **Fail-Closed Protection (8 / 15 Rejected)**:
  - Strings containing dense formatting tags or multiple variable placeholders:
    - `{color=#8a9aad}[label] {/color}{color=#e8eef4}[value]{/color}`
    - `{size=21}{color=#b0b8d0}%d日目{/color}{color=%s}　迎えの船まで %d日{/color}{/size}`
    - `%s の反撃！ %d ダメージ`
    - `渾身の一撃！ %s に %d ダメージ`
    - `罠が炸裂！ %s に %d ダメージ`
    - `[_gl_unlocked]/[_gl_total]`
    - `{size=17}HP{/size}`
    - `{size=15}%d/%d{/size}`
  - **Root Cause**: ArgosTranslate's sequence-to-sequence model dropped masking tokens (`XXXTOKEN0XXX`, `XXXTOKEN1XXX`) during translation.
  - **Safety Action**: GameLingo's `PlaceholderProtector.restore()` detected missing tokens and raised `MaskingError`. The pipeline failed closed, preventing corrupted markup from ever entering game files.
- **Successful Variable Translations (6 / 15)**:
  - When sentences had sufficient surrounding natural language, formatting tokens were preserved:
    - `逃げ損ねた！ %d ダメージ` -> `"I couldn't run away! %d Damage"` (Preserved `%d`)
    - `罠を仕掛ける（%d）` -> `"Set trap (%d)"` (Preserved `%d`)
    - `[cur_foe.name]` -> `"[cur_foe.name]"` (Preserved variable code intact)

### 5.5 Multiline Text (High Structural Resilience — Score: 2.60 / 5)

- **100% Structural Preservation**:
  - Embedded `\n` line breaks were preserved without loss across all 10 multiline tutorial cards.
  - Bullet markers (`*`), parenthetical costs (`+2`), and arrow delimiters (`→`) survived translation intact.
- **Semantic Weaknesses**:
  - Domain terminology was frequently mistranslated:
    - `セリフ` (lines/dialogue) -> `"serif"` (typographic font)
    - `バレ度` (suspicion level) -> `"ballet"` (dance)
    - `隙` (opening / mental vulnerability) -> `"Sky"`
    - `昼に稼ぎ、夜に堕とす` -> `"earn at lunch and fall at night"`

### 5.6 Technical and Untranslatable Strings (Score: 1.57 / 5)

- Pure ASCII identifiers (`SAVE`, `mat`, `END`, `----`) remained unchanged as intended, but triggered `IDENTICAL_TO_SOURCE` warnings.
- `CONFIG` suffered an unexpected semantic transformation into `"HOME"`.

---

## 6. Implications for GameLingo Review and QA Architecture

The findings of GL-040.1 prove why automated machine translation cannot be deployed to real games without strict QA gates and validation filters:

1. **`PlaceholderProtector` is Mandatory**:
   Without fail-closed sentinel checks, 53% of variable/tagged strings would have suffered corrupted syntax, broken Ren'Py styling tags, or crash-inducing printf specifier mismatches.
2. **Polarity and Hallucination Filter Needed**:
   Colloquial Japanese particles and ellipses produce catastrophic hallucinations in ArgosTranslate (e.g., `おなか、すいた` -> `"Home"`). The review workbench must highlight short dialogue lines containing ellipses or negative verb inflections (`ない`, `ず`) for priority human review.
3. **Glossary & Terminology Injection**:
   Core visual novel terms (`セーブ`, `スキップ`, `セリフ`, `陥落度`) should be intercepted by pre-translation glossary lookups rather than relying on raw NMT inference.
4. **Katakana Truncation Detector**:
   Single-character katakana/kanji outputs (`ブ`, `大`) must be caught as `TRUNCATED_OUTPUT` validation errors before saving to translation memory.

---

## 7. Deliverables & Artifacts Produced

1. **Benchmark Dataset**:
   `src/gamelingo/benchmark/dataset_gl040_real_game.json` (100 verified source strings from `island-1.0-win`, categories, contexts, references, and expected behaviors).
2. **Automated Benchmark Runner**:
   `scripts/run_quality_benchmark.py` (offline executable runner with timing, metrics calculation, and evaluation outputs).
3. **Machine-Readable Evaluation Artifact**:
   `src/gamelingo/benchmark/results/gl040_benchmark_evaluation.json` (complete record containing summary statistics and item-by-item rubric scoring).
4. **Raw Translation Telemetry**:
   `src/gamelingo/benchmark/results/gl040_raw_translations.json` (raw provider outputs, latencies, and validation issues).
5. **Regression & Quality Unit Tests**:
   `tests/unit/test_quality_benchmark.py` (verifies dataset integrity, schema completeness, category distributions, and evaluation logic).
