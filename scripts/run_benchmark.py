from pathlib import Path

from gamelingo.benchmark.models import (
    ArgosTranslateCandidate,
    CTranslate2OPUSCandidate,
    OPUSMTCandidate,
)
from gamelingo.benchmark.runner import run_benchmark

if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    dataset_path = repo_root / "src/gamelingo/benchmark/dataset.jsonl"
    output_dir = repo_root / "src/gamelingo/benchmark/results"

    candidates = [
        OPUSMTCandidate(),
        ArgosTranslateCandidate(),
        CTranslate2OPUSCandidate(),
    ]

    run_benchmark(dataset_path, candidates, output_dir)
