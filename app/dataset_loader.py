import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "sample_id",
    "vector",
    "user_query",
    "contexts",
    "metadata",
    "scenario",
    "labels",
}


def load_split(path: Path) -> list[dict[str, Any]]:
    """Load and validate an MPIB JSONL split without printing its contents."""
    if not path.is_file():
        raise FileNotFoundError(f"Dataset split not found: {path}")

    records = []
    seen_ids = set()
    vectors = Counter()
    scenarios = Counter()

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON at line {line_number}"
                ) from exc

            if not isinstance(record, dict):
                raise ValueError(
                    f"Expected a JSON object at line {line_number}"
                )

            missing = REQUIRED_FIELDS - record.keys()
            if missing:
                raise ValueError(
                    f"Missing required fields at line {line_number}: "
                    f"{', '.join(sorted(missing))}"
                )

            if not isinstance(record["sample_id"], str) or not record["sample_id"].strip():
                raise ValueError(
                    f"Invalid sample_id at line {line_number}"
                )

            for field in ("vector", "user_query", "scenario"):
                if not isinstance(record[field], str):
                    raise ValueError(
                        f"Invalid type for {field} at line {line_number}"
                    )

            if not isinstance(record["contexts"], list):
                raise ValueError(
                    f"Invalid contexts type at line {line_number}"
                )

            if not isinstance(record["metadata"], dict):
                raise ValueError(
                    f"Invalid metadata type at line {line_number}"
                )

            if not isinstance(record["labels"], dict):
                raise ValueError(
                    f"Invalid labels type at line {line_number}"
                )

            sample_id = record["sample_id"]
            if sample_id in seen_ids:
                raise ValueError(
                    f"Duplicate sample_id at line {line_number}"
                )

            seen_ids.add(sample_id)
            vectors[record["vector"]] += 1
            scenarios[record["scenario"]] += 1
            records.append(record)

    print(f"File: {path.name}")
    print(f"Validated records: {len(records)}")
    print(f"Distinct vectors: {len(vectors)}")
    print(f"Distinct scenarios: {len(scenarios)}")
    print("Validation: PASS")

    return records


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and summarize an MPIB JSONL split."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="Directory containing the MPIB JSONL splits.",
    )
    parser.add_argument(
        "--split",
        choices=("train", "validation", "test"),
        required=True,
    )
    args = parser.parse_args()

    load_split(args.data_dir / f"{args.split}.jsonl")


if __name__ == "__main__":
    main()
