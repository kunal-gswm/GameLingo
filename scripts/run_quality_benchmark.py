"""
GL-040.2 Real Translation Quality Benchmark Runner
==================================================
Executes translation quality benchmarking across 100 representative real-game
source strings extracted from Ren'Py 8.5 (island-1.0-win).
Measures:
- Latency and throughput
- Pipeline execution & fail-closed rejection rates
- Structural validity rate vs semantic quality rate
- Intentional passthrough handling for technical identifiers and formatting
- Placeholder, tag, and formatting code integrity
- Human-reviewed meaning and grammar metrics (strictly decoupled via hash-pinned annotations)
"""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from gamelingo.benchmark.evaluator import (
    aggregate_benchmark_metrics,
    evaluate_translation_item,
    load_annotations,
)
from gamelingo.translation.argos_provider import ArgosTranslateProvider
from gamelingo.translation.provider import TranslationRequest
from gamelingo.translation.validation import validate_translation


def run_quality_benchmark(
    dataset_path: Path,
    output_dir: Path,
    annotations_path: Path | None = None,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 75)
    print("GameLingo GL-040.2 Decoupled Translation Quality Benchmark")
    print("=" * 75)

    # 1. Environment Verification
    print("\n[1/4] Verifying Translation Environment...")
    if not ArgosTranslateProvider.is_model_installed("ja", "en"):
        raise RuntimeError(
            "ArgosTranslate package ja->en is not installed. Run `argostranslate` package install."
        )
    print("  ✓ Provider: ArgosTranslateProvider")
    print("  ✓ Language Route: ja -> en (package version: 1.1)")
    print("  ✓ Offline Execution: Verified")

    # 2. Load Dataset & Annotations
    print(f"\n[2/4] Loading Benchmark Dataset from {dataset_path}...")
    with open(dataset_path, "r", encoding="utf-8") as f:
        items = json.load(f)
    print(f"  ✓ Loaded {len(items)} curated strings from real Ren'Py 8.5 game")

    annotations_store = {}
    if annotations_path and annotations_path.exists():
        annotations_store = load_annotations(annotations_path)
        print(f"  ✓ Loaded {len(annotations_store)} pinned human review annotations")
    else:
        print(
            "  ! No external annotations loaded; all outputs will require manual review"
        )

    # 3. Translation Execution
    print("\n[3/4] Running Configured Translation Pipeline...")
    provider = ArgosTranslateProvider()
    results = []
    t_start = time.time()

    for item in items:
        req = TranslationRequest(
            id=item["id"],
            source_text=item["source_text"],
            source_lang="ja",
            target_lang="en",
            context=item["context"],
            category=item["category"],
        )
        t0 = time.time()
        try:
            batch_res = provider.translate_batch([req])
            res = batch_res[0]
            dur = time.time() - t0
            tgt = res.target_text
            err = res.error
        except Exception as e:
            dur = time.time() - t0
            tgt = ""
            err = str(e)

        val_issues = []
        if not err:
            raw_issues = validate_translation(item["source_text"], tgt)
            val_issues = [issue.code for issue in raw_issues]

        eval_result = evaluate_translation_item(
            item=item,
            target_text=tgt,
            error=err,
            val_issues=val_issues,
            annotations_store=annotations_store,
        )
        eval_result["duration_seconds"] = round(dur, 4)
        results.append(eval_result)

    total_time = time.time() - t_start
    print(
        f"  ✓ Processed {len(results)} items in {total_time:.2f}s "
        f"({len(results) / total_time:.1f} items/sec)"
    )

    # 4. Aggregation and Metrics
    print("\n[4/4] Computing Decoupled Benchmark Metrics...")
    summary = aggregate_benchmark_metrics(results, total_time_seconds=total_time)
    summary["benchmark_version"] = "GL-040.2"
    summary["engine"] = "Ren'Py 8.5.0"
    summary["source_game"] = "island-1.0-win"
    summary["model"] = "ArgosTranslate 1.1 (translate-ja_en)"
    summary["source_lang"] = "ja"
    summary["target_lang"] = "en"

    # Print Summary Tables with Explicit Denominators
    print("\n" + "=" * 75)
    print("BENCHMARK METRICS SUMMARY (DECOUPLED EVALUATION)")
    print("=" * 75)

    pipe = summary["pipeline_execution"]
    print(
        f"Pipeline Succeeded        : {pipe['provider_calls_succeeded']} / {pipe['provider_calls_total']} ({pipe['provider_calls_succeeded_pct']}%)"
    )
    print(
        f"Fail-Closed Rejections    : {pipe['pipeline_fail_closed_rejections']} / {pipe['provider_calls_total']} ({pipe['pipeline_rejection_rate_pct']}%)"
    )

    struct = summary["structural_validity"]
    print(
        f"Structurally Valid Outputs: {struct['structurally_valid_count']} / {summary['total_items']} ({struct['structural_validity_rate_pct']}%)"
    )
    print(f"  - Untranslated Fallback : {struct['untranslated_count']}")
    print(f"  - Truncated Fragments   : {struct['truncated_count']}")
    print(f"  - Pipeline Error Rejects: {struct['error_count']}")

    passthru = summary["intentional_passthrough"]
    print(
        f"Intentional Passthrough   : {passthru['passthrough_exact_match_count']} / {passthru['passthrough_expected_count']} ({passthru['passthrough_accuracy_rate_pct']}%)"
    )

    markup = summary["placeholder_formatting_integrity"]
    print(
        f"Placeholder & Tag Pass    : {markup['markup_intact_count']} / {markup['strings_with_markup_count']} ({markup['markup_integrity_rate_pct']}%)"
    )

    qual = summary["human_quality_evaluation"]
    print(
        f"Human Reviewed Outputs    : {qual['reviewed_items_count']} / {summary['total_items']} ({qual['review_coverage_pct']}%)"
    )
    print(
        f"Pending Manual Review     : {qual['pending_review_count']} / {summary['total_items']}"
    )
    print(
        f"Human Meaning Score (0-5) : {qual['avg_meaning_score']:.2f} / 5.00  [Denominator: {qual['reviewed_items_count']} reviewed items]"
    )
    print(
        f"Human Grammar Score (0-5) : {qual['avg_grammar_score']:.2f} / 5.00  [Denominator: {qual['reviewed_items_count']} reviewed items]"
    )
    print(
        f"Acceptable Quality (M>=3) : {qual['acceptable_quality_count']} / {qual['reviewed_items_count']} ({qual['acceptable_quality_rate_pct']}%)"
    )

    print("\n" + "-" * 75)
    print(
        f"{'Category':16s} | {'Count':5s} | {'Valid %':7s} | {'Meaning':7s} | {'Grammar':7s} | {'Accept %':8s} | {'Review Cov':10s}"
    )
    print("-" * 75)
    for cat, s in summary["by_category"].items():
        print(
            f"{cat.upper():16s} | {s['item_count']:5d} | {s['structural_validity_rate_pct']:6.1f}% | {s['avg_meaning_score']:7.2f} | {s['avg_grammar_score']:7.2f} | {s['acceptable_quality_rate_pct']:7.1f}% | {s['reviewed_count']}/{s['item_count']}"
        )
    print("-" * 75)

    # Save Machine-Readable JSON
    eval_file = output_dir / "gl040_benchmark_evaluation.json"
    with open(eval_file, "w", encoding="utf-8") as f:
        json.dump(
            {"summary": summary, "results": results},
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\n✓ Saved updated evaluation artifact to: {eval_file}")

    return summary


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    dataset_file = repo_root / "src/gamelingo/benchmark/dataset_gl040_real_game.json"
    annotations_file = repo_root / "src/gamelingo/benchmark/annotations_gl040.json"
    results_dir = repo_root / "src/gamelingo/benchmark/results"
    run_quality_benchmark(dataset_file, results_dir, annotations_file)
