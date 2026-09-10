"""Reproducible dataset pull via the Kaggle API.

Downloads the Cookie Cats mobile-games A/B experiment into data/raw/.
Raw data is gitignored -- anyone who clones the repo runs this once to
fetch it, so the analysis is reproducible without committing the data.

Prereq: a Kaggle API token at ~/.kaggle/kaggle.json (see README).

Run:  python data/download.py
"""

from pathlib import Path

from kaggle.api.kaggle_api_extended import KaggleApi

# Real mobile-game A/B test: control = gate_30, treatment = gate_40.
# ~90k players, metrics retention_1 / retention_7, near-50/50 allocation.
DATASET = "mursideyarkin/mobile-games-ab-testing-cookie-cats"
RAW_DIR = Path(__file__).resolve().parent / "raw"


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    api = KaggleApi()
    api.authenticate()
    api.dataset_download_files(DATASET, path=str(RAW_DIR), unzip=True)
    print(f"downloaded to {RAW_DIR}")
    for f in sorted(RAW_DIR.iterdir()):
        print(f"  - {f.name}")


if __name__ == "__main__":
    main()
