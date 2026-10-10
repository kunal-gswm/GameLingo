import json
import time
from pathlib import Path
from typing import List


class BenchmarkCandidate:
    name: str
    version: str
    license_model: str
    license_code: str

    def setup(self):
        """Load the model into memory. Measure cold start time."""
        pass

    def translate(self, texts: List[str]) -> List[str]:
        """Translate a batch of strings."""
        pass

    def teardown(self):
        """Free memory."""
        pass


def run_benchmark(
    dataset_path: Path, candidates: List[BenchmarkCandidate], output_dir: Path
):
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load dataset
    dataset = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                dataset.append(json.loads(line))

    source_texts = [d["source_text"] for d in dataset]
    total_chars = sum(len(text) for text in source_texts)

    results = {}

    for candidate in candidates:
        print(f"Benchmarking {candidate.name}...")

        try:
            # Cold start load
            t0 = time.time()
            candidate.setup()
            load_time = time.time() - t0

            # Warm up (run first 5 items)
            candidate.translate(source_texts[:5])

            # Actual run
            t1 = time.time()
            outputs = candidate.translate(source_texts)
            run_time = time.time() - t1

            candidate.teardown()

            # Compare references
            # Simple check for placeholder integrity (e.g., %1)
            placeholder_failures = 0
            for src, out in zip(source_texts, outputs):
                if "%1" in src and "%1" not in out:
                    placeholder_failures += 1
                if "%2" in src and "%2" not in out:
                    placeholder_failures += 1

            results[candidate.name] = {
                "status": "success",
                "version": candidate.version,
                "license_model": candidate.license_model,
                "license_code": candidate.license_code,
                "load_time_seconds": round(load_time, 2),
                "run_time_seconds": round(run_time, 2),
                "strings_per_second": round(len(source_texts) / run_time, 2)
                if run_time > 0
                else 0,
                "chars_per_second": round(total_chars / run_time, 2)
                if run_time > 0
                else 0,
                "placeholder_failures": placeholder_failures,
                "outputs": outputs,
            }
        except Exception as e:
            print(f"Failed to run {candidate.name}: {e}")
            results[candidate.name] = {
                "status": "failed",
                "version": candidate.version,
                "license_model": candidate.license_model,
                "license_code": candidate.license_code,
                "error": str(e),
            }

    # Save machine-readable output
    with open(output_dir / "benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Generate Markdown report
    report = ["# Translation Engine Benchmark Report\n"]
    report.append("## Environment")
    report.append("- Dataset: Synthetic Japanese-English (60 strings)")
    report.append("- Hardware: Detected at runtime")
    report.append("")

    report.append("## Candidates")
    for cand in candidates:
        res = results.get(cand.name, {})
        status = res.get("status", "Not run")
        report.append(f"### {cand.name}")
        report.append(f"- **Status**: {status}")
        report.append(f"- **Version**: {cand.version}")
        report.append(f"- **Model License**: {cand.license_model}")
        report.append(f"- **Code License**: {cand.license_code}")

        if status == "success":
            report.append(f"- **Load Time**: {res['load_time_seconds']}s")
            report.append(
                f"- **Throughput**: {res['strings_per_second']} strings/s ({res['chars_per_second']} chars/s)"
            )
            report.append(f"- **Placeholder Failures**: {res['placeholder_failures']}")
        elif status == "failed":
            report.append(f"- **Error**: {res.get('error')}")
        report.append("")

    with open(output_dir / "benchmark_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print("Benchmark complete!")
