# GL-037 Preflight Report: Source Determination of Untranslated UI Text

**Project:** GameLingo  
**Task:** GL-037 Preflight  
**Target Game Inspected:** `island-1.0-win` (Ren'Py 8.x / RPA-3.0 visual novel)  
**Date:** 2026-10-12  

---

## 1. Executive Summary

This preflight investigation audited all readable scripts, decompiled `.rpyc` archives, and visual assets of the supplied Ren'Py visual novel (`island-1.0-win`) to determine the exact origin of all visible, previously untranslated Japanese UI text elements.

### Key Conclusions

1. **Scripts vs Image Assets:**  
   The vast majority (**>99%**) of visible in-game Japanese interface text—including the status HUD, action choices, tutorial modal panels, night hypnosis actions, and quit confirmation dialog—is **rendered from scripts** (Ren'Py screen language statements and `init python` data structures), **NOT embedded in image assets**.
2. **True Image-Embedded Text:**  
   Only **one primary Japanese image-embedded text element** exists in the entire game: the main menu title logo and subtitle (`催の果実 〜目が合えば、いいなり。無人島 孕ませハーレム〜`) embedded directly into the pixels of `gui/main_menu.png`. All action buttons, card frames, dialog backdrops, and HUD meters use blank slice/frame graphics on top of which script text is dynamically rendered.
3. **Extraction Coverage:**  
   GameLingo's context-aware Ren'Py adapter extracted **32 out of 32 (100%)** target UI strings identified across the HUD, menus, and modals, expanding extractable game units from 1,916 to 2,412.

---

## 2. Text Element Classification Matrix

Every visible text element inspected in the game was mapped into one of five mandatory categories:

| Category | Description | Count in Game | Translation Mechanism |
| :--- | :--- | :--- | :--- |
| **1. Static screen-language text** | Explicit string literals in `screen` declarations (`text`, `textbutton`, `label`, `tooltip`, `use`) | 84+ statements | Extracted as UI units $\rightarrow$ `game/tl/<lang>/strings.rpy` |
| **2. Dynamic text (variables / exprs)** | Strings rendered via Python structures (`HUB_TUT_CARDS`, `METER_TIP`, `HYPNO_LIST`), ternary expressions, or `[var]` interpolation | 380+ statements | Extracted from Python data / screen expressions $\rightarrow$ `strings.rpy` (interpolation preserved) |
| **3. Ren'Py built-in interface text** | Standard engine messages & navigational buttons (`巻き戻し`, `スキップ`, `オート`, `セーブ`, `終了`) | 45+ statements | Extracted via marked `_()` strings and engine hooks $\rightarrow$ `strings.rpy` |
| **4. Text embedded in image** | Bitmap/vector artwork containing baked text (`gui/main_menu.png` title logo) | 1 title graphic (plus legacy English button assets) | Visual asset replacement pipeline (separate milestone) |
| **5. Source not yet identified** | Any UI text whose origin could not be located | **0 (None)** | Fully accounted for |

---

## 3. Comprehensive Breakdown by Game Component

### 3.1 Status Labels & HUD Panels

In the game's exploration hub, status indicators display meters, resources, and tooltips.

| Visible Text | Category | Exact Source File & Line | Context & Code | Recommended Mechanism |
| :--- | :--- | :--- | :--- | :--- |
| `採取量` | **1. Static screen** | `game/ui_screens.rpy:33` | `text "採取量"` in `screen ui_status_panel` | Native `strings.rpy` entry |
| `絆` | **1. Static screen** | `game/ui_screens.rpy:43` | `text "絆"` in `screen ui_status_panel` | Native `strings.rpy` entry |
| `✓ 訪問済み` | **1. Static screen** | `game/ui_screens.rpy:72` | `text "✓ 訪問済み"` in `screen ui_house_map` | Native `strings.rpy` entry |
| `[harvest_rate]%` | **2. Dynamic text** | `game/ui_screens.rpy:42` | `text "[harvest_rate]%"` (variable interpolation) | Preserved placeholder `[harvest_rate]%` |
| `[bond]` | **2. Dynamic text** | `game/ui_screens.rpy:52` | `text "[bond]"` (variable interpolation) | Preserved placeholder `[bond]` |
| `果実`, `食料`, `罠`, `侵食`, `バレ`, `脅威`, `防衛` | **1. Static screen** | `game/island_hub.rpy:261-267` | `use stat_ic("ic_fruit", "果実", fruit_stock, "fruit")` in `screen hub_meters` | Extracted via `use` statement literals $\rightarrow$ `strings.rpy` |
| `体力：主人公のHP...` (METER_TIP) | **2. Dynamic text** | `game/island_hub.rpy:181-191` | `METER_TIP = {"hp": "体力：主人公のHP...", ...}` in `init python:` | Extracted from `init python` dictionary $\rightarrow$ `strings.rpy` |
| `完堕ち`, `服従`, `陶酔`, `動揺`, `警戒` | **2. Dynamic text** | `game/island_hub.rpy:48-53` | `def band_name(v): if v >= 90: return "完堕ち" ...` in Python | Extracted from Python expressions $\rightarrow$ `strings.rpy` |
| `今日をどう使う——` / `夜をどう使う——` | **2. Dynamic text** | `game/island_hub.rpy:414` | `text ("今日をどう使う——" if _acts_left else "夜をどう使う——")` | Extracted from ternary expression $\rightarrow$ `strings.rpy` |
| `昼の行動　残り %d / %d` | **2. Dynamic text** | `game/island_hub.rpy:415` | `text ("昼の行動　残り %d / %d" % (_acts_left, day_acts_max))` | Format placeholders preserved in `strings.rpy` |

---

### 3.2 Action Choices & Hub Interaction Cards

The interactive cards in `hub_field` control daytime and nighttime actions:

| Visible Text | Category | Exact Source File & Line | Context & Code | Recommended Mechanism |
| :--- | :--- | :--- | :--- | :--- |
| `探索に出る` | **1. Static screen** | `game/island_hub.rpy:421` | `use hub_card("explore", "card_explore", "探索に出る", ...)` | Screen parameter extraction $\rightarrow$ `strings.rpy` |
| `釣りをする` | **1. Static screen** | `game/island_hub.rpy:422` | `use hub_card("fish", "card_fishing", "釣りをする", ...)` | Screen parameter extraction $\rightarrow$ `strings.rpy` |
| `男を狩る` | **1. Static screen** | `game/island_hub.rpy:423` | `use hub_card("hunt", "card_hunt", "男を狩る", ...)` | Screen parameter extraction $\rightarrow$ `strings.rpy` |
| `側に呼ぶ` | **1. Static screen** | `game/island_hub.rpy:441` | `use hub_pill("night", "側に呼ぶ", ...)` | Screen parameter extraction $\rightarrow$ `strings.rpy` |
| `島の女たちの配置` | **1. Static screen** | `game/island_hub.rpy:443` | `use hub_info_pill("mob", "島の女たちの配置", ...)` | Screen parameter extraction $\rightarrow$ `strings.rpy` |
| `拠点を強化` | **1. Static screen** | `game/island_hub.rpy:445` | `use hub_info_pill("fort", "拠点を強化", ...)` | Screen parameter extraction $\rightarrow$ `strings.rpy` |
| `傷の手当て` | **1. Static screen** | `game/island_hub.rpy:447` | `use hub_pill("heal", "傷の手当て", ...)` | Screen parameter extraction $\rightarrow$ `strings.rpy` |
| `休む` | **1. Static screen** | `game/island_hub.rpy:453` | `use hub_pill("sleep", "休む", ...)` | Screen parameter extraction $\rightarrow$ `strings.rpy` |
| `隣で眠る` | **1. Static screen** | `game/island_hub.rpy:455` | `use hub_pill("sleepside", "隣で眠る", ...)` | Screen parameter extraction $\rightarrow$ `strings.rpy` |
| `物語を進める` | **1. Static screen** | `game/island_hub.rpy:459` | `use hub_pill("story", "物語を進める", ...)` | Screen parameter extraction $\rightarrow$ `strings.rpy` |
| `見つめる（安全に慣らす・覚醒-4）` | **2. Dynamic text** | `game/island_hub.rpy:24` | `HYPNO_LIST = [("見つめる（安全に慣らす・覚醒-4）", ...)]` | Python tuple extraction $\rightarrow$ `strings.rpy` |
| `警戒を解く` | **2. Dynamic text** | `game/island_hub.rpy:25` | `HYPNO_LIST = [..., ("警戒を解く", ...)]` | Python tuple extraction $\rightarrow$ `strings.rpy` |
| `俺を信頼する` | **2. Dynamic text** | `game/island_hub.rpy:26` | `HYPNO_LIST = [..., ("俺を信頼する", ...)]` | Python tuple extraction $\rightarrow$ `strings.rpy` |
| `さらに大物を狙う` / `ここで確定させる` | **1. Static screen** | `game/island_minigames.rpy:366-367`| `use mg_fchoice_card("more", "さらに大物を狙う", ...)` | Screen parameter extraction $\rightarrow$ `strings.rpy` |

---

### 3.3 Tutorial Modals & Instructions

The tutorial popup that explains the island mechanics (`screen hub_tut_guide` and `screen hyp_tut_guide`):

| Visible Text | Category | Exact Source File & Line | Context & Code | Recommended Mechanism |
| :--- | :--- | :--- | :--- | :--- |
| `——島での戦い方——` | **1. Static screen** | `game/island_hub.rpy:401` | `text "——島での戦い方——" size 18 color "#b478e6"` | Static screen extraction $\rightarrow$ `strings.rpy` |
| `HUB_TUT_CARDS[0..4]` (5 full tutorial pages) | **2. Dynamic text** | `game/island_hub.rpy:372-378` | `HUB_TUT_CARDS = ["ここからは、日々を自分で組み立てる...", ...]` | Python list extraction $\rightarrow$ `strings.rpy` |
| `▶ 次へ` / `閉じる` | **2. Dynamic text** | `game/island_hub.rpy:407` | `textbutton ("▶ 次へ" if hub_tut_i + 1 < len(HUB_TUT_CARDS) else "閉じる")` | Ternary expression extraction $\rightarrow$ `strings.rpy` |
| `？ 遊び方` | **1. Static screen** | `game/island_hub.rpy:462` | `textbutton "？ 遊び方" ... action Function(_hub_tut_replay)` | Static button extraction $\rightarrow$ `strings.rpy` |

---

### 3.4 Quit Confirmation Dialog

When the player presses `ESC` or clicks `Quit`:

| Visible Text | Category | Exact Source File & Line | Context & Code | Recommended Mechanism |
| :--- | :--- | :--- | :--- | :--- |
| `ゲームを終了しますか？` | **2. Dynamic text** | `game/zz_island_ui.rpy:50` | `CONFIRM_JP = {"Are you sure you want to quit?": "ゲームを終了しますか？"}` | Python dictionary extraction $\rightarrow$ `strings.rpy` |
| `はい` | **1. Static / Marked** | `game/zz_island_ui.rpy:84` | `textbutton _("はい") style "confirm_btn" action yes_action` | Marked string `_()` extraction $\rightarrow$ `strings.rpy` |
| `いいえ` | **1. Static / Marked** | `game/zz_island_ui.rpy:85` | `textbutton _("いいえ") style "confirm_btn" action no_action` | Marked string `_()` extraction $\rightarrow$ `strings.rpy` |

> [!NOTE]
> **Why the prompt was previously Japanese while buttons were English:**
> In vanilla Ren'Py, `confirm(message, yes_action, no_action)` receives `"Are you sure you want to quit?"` from the core engine. The game author intercepted this in `zz_island_ui.rpy` via `CONFIRM_JP.get(message, message)` to translate it to Japanese for native players.
> In Ren'Py 8, all string expressions in `text <expr>` are automatically routed through `renpy.translation.translate_string(s)` at runtime. Translating `"ゲームを終了しますか？"` back to `"Are you sure you want to quit?"` in `strings.rpy` allows the prompt to cleanly render in English alongside the buttons.

---

### 3.5 Built-in Ren'Py Interface Elements

Default engine navigation strings in `screens.rpy` and `zz_island_ui.rpy`:

| Visible Text | Category | Exact Source File & Line | Context & Code | Recommended Mechanism |
| :--- | :--- | :--- | :--- | :--- |
| `巻き戻し`, `ヒストリー`, `スキップ`, `オート`, `セーブ` | **3. Ren'Py built-in** | `game/screens.rpy:145-149` | `textbutton _("巻き戻し") action Rollback()` in `quick_menu` | Extracted via marked `_()` strings $\rightarrow$ `strings.rpy` |
| `SAVE`, `LOAD`, `CONFIG`, `HIDE` | **1. Static screen** | `game/zz_island_ui.rpy:25-34` | `textbutton "SAVE" action ShowMenu("save")` in custom bar | Native English in script; preserved |
| `スタート`, `つづきから`, `設定`, `島の記憶`, `アルバム` | **1. Static screen** | `game/zz_island_ui.rpy:424-428` | `use island_mm_button("START", "スタート", Start())` | Screen argument extraction $\rightarrow$ `strings.rpy` |

---

### 3.6 Text Embedded in Image Assets

Audit of all 334 image files across `archive.rpa`:

| Image Asset | Resolution | Category | Text Content | Status & Remediation |
| :--- | :--- | :--- | :--- | :--- |
| `gui/main_menu.png` | 1920x1080 | **4. Text in image** | `催の果実 〜目が合えば、いいなり。無人島 孕ませハーレム〜` | **Baked into artwork.** Script translation cannot alter this. Requires image patch or layered GUI text. |
| `gui/button/main_newgame_idle.png` | 396x132 | **4. Text in image** | `"New Game"` (English) | Unused fallback asset; game uses dynamic text via `island_mm_button`. |
| `gui/button/main_load_idle.png` | 396x132 | **4. Text in image** | `"Load"` (English) | Unused fallback asset. |
| `gui/button/main_settings_idle.png` | 396x132 | **4. Text in image** | `"Settings"` (English) | Unused fallback asset. |
| `gui/button/main_gallery_idle.png` | 396x132 | **4. Text in image** | `"Gallery"` (English) | Unused fallback asset. |
| `images/event/title_keyvisual.jpg` | 1920x1080 | **4. Text in image** | `SAIMIN KAJITSU (temp title)` (English) | Background artwork. |
| `images/mg/card_*.png` (6 cards) | 300x104 | **Clean Graphic** | None (pure artwork) | Blank artwork frames; text is rendered by Ren'Py screen `hub_card`. |
| `images/mg/ui_card.png`, `btn.png` | 24x24 / 48x48 | **Clean Graphic** | None (nine-patch frames) | Blank UI textures. |

---

## 4. Source Evidence Summary Table

| UI Element | Source File & Line | Extraction Status in GameLingo | Classification |
| :--- | :--- | :--- | :--- |
| Quit Confirmation Prompt (`ゲームを終了しますか？`) | `game/zz_island_ui.rpy:50` | **Extracted** (`py:0`) | Dynamic (Python dict) |
| Quit Confirmation Buttons (`はい`, `いいえ`) | `game/zz_island_ui.rpy:84-85` | **Extracted** (`screen:confirm:textbutton`) | Static / Marked `_()` |
| Tutorial Title (`——島での戦い方——`) | `game/island_hub.rpy:401` | **Extracted** (`screen:hub_tut_guide:text`) | Static screen text |
| Tutorial Body Pages (`HUB_TUT_CARDS`) | `game/island_hub.rpy:373-377` | **Extracted** (`py:0..4`) | Dynamic (Python list) |
| Tutorial Next Button (`▶ 次へ` / `閉じる`) | `game/island_hub.rpy:407` | **Extracted** (`screen:hub_tut_guide:textbutton`) | Dynamic (ternary expr) |
| Hub Action: `探索に出る` | `game/island_hub.rpy:421` | **Extracted** (`screen:hub_field:use`) | Static screen param |
| Hub Action: `釣りをする` | `game/island_hub.rpy:422` | **Extracted** (`screen:hub_field:use`) | Static screen param |
| Hub Action: `男を狩る` | `game/island_hub.rpy:423` | **Extracted** (`screen:hub_field:use`) | Static screen param |
| Hub Action: `物語を進める` | `game/island_hub.rpy:459` | **Extracted** (`screen:hub_field:use`) | Static screen param |
| Hub Action: `休む` / `隣で眠る` | `game/island_hub.rpy:453, 455`| **Extracted** (`screen:hub_field:use`) | Static screen param |
| Hub Status: `採取量`, `絆` | `game/ui_screens.rpy:33, 43` | **Extracted** (`screen:ui_status_panel:text`) | Static screen text |
| Hub Status: `果実`, `食料`, `防衛`, etc. | `game/island_hub.rpy:261-267` | **Extracted** (`screen:hub_meters:use`) | Static screen param |
| Night Session Actions (`HYPNO_LIST`) | `game/island_hub.rpy:24-32` | **Extracted** (`py:0..8`) | Dynamic (Python list) |
| Main Menu Japanese Sub-labels (`スタート`, etc.) | `game/zz_island_ui.rpy:424-428` | **Extracted** (`screen:main_menu:use`) | Static screen param |
| Main Menu Title Graphic (`催の果実...`) | `gui/main_menu.png` | **Reported in Diagnostic** | Image-embedded text |

---

## 5. Recommended Translation Mechanisms

### 1. Script & Python Data Texts $\rightarrow$ `game/tl/<language>/strings.rpy`
All extracted static screen language strings, marked `_()` / `__()` strings, and Python UI literals (`CONFIRM_JP`, `HUB_TUT_CARDS`, `HYPNO_LIST`, `METER_TIP`) must be compiled into Ren'Py's native string translation table:
```renpy
translate english strings:
    old "ゲームを終了しますか？"
    new "Are you sure you want to quit?"

    old "はい"
    new "Yes"

    old "いいえ"
    new "No"

    old "——島での戦い方——"
    new "——How to Fight on the Island——"

    old "探索に出る"
    new "Go Exploring"
```
Because Ren'Py automatically calls `translate_string(s)` on string expressions at screen draw time, this single standard mechanism cleanly translates screens, choices, and Python UI variables.

### 2. Dynamic Placeholders & Formatting Tags
Ensure interpolation variables (e.g. `[variable]`, `[harvest_rate]%`, `[bond]`) and styling tags (`{size=...}`, `{color=...}`) are preserved verbatim in the translated `new` block without converting dynamic values into hardcoded text.

### 3. Image-Embedded Text $\rightarrow$ Diagnostic Inventory
Image assets containing text cannot be translated via `strings.rpy`. GameLingo provides an automated diagnostic inventory disclosing candidate text-bearing images. For games requiring full visual localization, an optional image-replacement pipeline mapping source assets to translated PNGs under `game/tl/<language>/<asset_path>` can be explored in a dedicated future milestone.

---

## 6. Regression Testing & Verification

- **Live Game Verification (`D:\New folder\island-1.0-win`):**
  - **100% (32/32)** of target elements extracted cleanly.
  - Zero duplicate edit targets.
  - 2,412 translation units extracted without asset path leaks.
- **Unit Test Suite:**
  - Added [test_renpy_ui_extraction.py](file:///e:/GameLingo/tests/unit/test_renpy_ui_extraction.py) with 15 focused tests covering all 5 categories.
  - Test 15 validates extraction of Python data structures (`HUB_TUT_CARDS` tutorial list and `HYPNO_LIST` action tuples).
  - Full test suite: **182 tests passed** (`100%` pass rate).
  - Code formatting and linting: `ruff check` and `ruff format` clean across 78 files.
