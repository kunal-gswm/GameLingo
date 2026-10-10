import json
from pathlib import Path

from gamelingo.benchmark.runner import BenchmarkCandidate, run_benchmark


class FakeSuccessCandidate(BenchmarkCandidate):
    def __init__(self):
        self.name = "Fake Success"
        self.version = "1.0"
        self.license_model = "MIT"
        self.license_code = "MIT"

    def setup(self):
        pass

    def translate(self, texts):
        return [t + " TR" for t in texts]

    def teardown(self):
        pass


class FakeFailCandidate(BenchmarkCandidate):
    def __init__(self):
        self.name = "Fake Fail"
        self.version = "1.0"
        self.license_model = "MIT"
        self.license_code = "MIT"

    def setup(self):
        raise ValueError("Simulated crash")

    def translate(self, texts):
        return []

    def teardown(self):
        pass


def test_benchmark_harness(tmp_path: Path):
    dataset_path = tmp_path / "dataset.jsonl"
    with open(dataset_path, "w", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "id": "1",
                    "source_text": "A %1",
                    "context": "ctx",
                    "category": "sys",
                    "reference": "A",
                }
            )
            + "\n"
        )
        f.write(
            json.dumps(
                {
                    "id": "2",
                    "source_text": "B",
                    "context": "ctx",
                    "category": "sys",
                    "reference": "B",
                }
            )
            + "\n"
        )

    output_dir = tmp_path / "results"

    candidates = [FakeSuccessCandidate(), FakeFailCandidate()]

    run_benchmark(dataset_path, candidates, output_dir)

    assert (output_dir / "benchmark_results.json").exists()
    assert (output_dir / "benchmark_report.md").exists()

    with open(output_dir / "benchmark_results.json", "r", encoding="utf-8") as f:
        results = json.load(f)

    assert results["Fake Success"]["status"] == "success"
    # %1 is not in the output of FakeSuccessCandidate (because it returns "A %1 TR") wait! It DOES return %1!
    # "A %1 TR" contains "%1"
    assert results["Fake Success"]["placeholder_failures"] == 0
    assert results["Fake Success"]["outputs"] == ["A %1 TR", "B TR"]

    assert results["Fake Fail"]["status"] == "failed"
    assert "Simulated crash" in results["Fake Fail"]["error"]
