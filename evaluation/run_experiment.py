import argparse
import json
import os
import time
from pathlib import Path

from app.dataset_loader import load_split
from app.firewall import Configuration, run_pipeline
from app.guards import inspect_input, validate_output_semantically
from app.model_client import generate_answer, load_local_env


BLOCKED_MESSAGE = (
    "This request was blocked by the security policy and could not be answered."
)


def normalize_contexts(contexts):
    return [
        item if isinstance(item, str)
        else json.dumps(item, ensure_ascii=False)
        for item in contexts
    ]


def load_sample_ids(path):
    """Read sample IDs from an existing JSONL record file."""
    sample_ids = set()
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON in sample ID file at line {line_number}."
                ) from exc
            sample_id = row.get("sample_id") if isinstance(row, dict) else None
            if not isinstance(sample_id, str) or not sample_id:
                raise ValueError(
                    f"Missing sample_id in sample ID file at line {line_number}."
                )
            sample_ids.add(sample_id)
    if not sample_ids:
        raise ValueError("Sample ID file contains no sample IDs.")
    return sample_ids


def run_experiment(data_dir, split, limit, output_path, sample_ids_path=None):
    load_local_env()
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    records = load_split(data_dir / f"{split}.jsonl")
    if sample_ids_path is not None:
        selected_ids = load_sample_ids(sample_ids_path)
        records = [record for record in records if record["sample_id"] in selected_ids]
        missing_ids = selected_ids - {record["sample_id"] for record in records}
        if missing_ids:
            raise ValueError(
                f"{len(missing_ids)} selected sample ID(s) are absent from "
                f"the {split} split."
            )
    if limit is not None:
        records = records[:limit]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    cache_hits = 0
    generation_cache = {}
    validation_counts = {}
    validation_attempts = {}
    validation_errors = {}
    detected_risks = {}

    with output_path.open("w", encoding="utf-8") as out:
        for record in records:
            sample_id = record["sample_id"]
            query = record["user_query"]
            contexts = normalize_contexts(record["contexts"])

            generation_time_ms = None

            def cached_generator(q, c):
                nonlocal generation_time_ms
                if sample_id not in generation_cache:
                    started = time.perf_counter()
                    answer = generate_answer(q, c)
                    generation_time_ms = (
                        time.perf_counter() - started
                    ) * 1000
                    generation_cache[sample_id] = answer
                return generation_cache[sample_id]

            for config in Configuration:
                response_was_cached = sample_id in generation_cache
                started = time.perf_counter()

                result = run_pipeline(
                    query=query,
                    contexts=contexts,
                    configuration=config,
                    generate=cached_generator,
                    input_guard=inspect_input,
                    output_validator=validate_output_semantically,
                )

                validation = result.output_validation
                if validation is not None:
                    validation_key = (
                        f"{validation.method}:{validation.status}:"
                        f"{validation.decision}"
                    )
                    validation_counts[validation_key] = (
                        validation_counts.get(validation_key, 0) + 1
                    )
                    config_name = config.value
                    validation_attempts[config_name] = (
                        validation_attempts.get(config_name, 0) + 1
                    )
                    if validation.status == "error":
                        validation_errors[config_name] = (
                            validation_errors.get(config_name, 0) + 1
                        )
                    elif validation.status == "success" and not validation.allowed:
                        detected_risks[config_name] = (
                            detected_risks.get(config_name, 0) + 1
                        )

                processing_ms = (time.perf_counter() - started) * 1000
                generation_invoked = "generation" in result.stages
                raw_response = generation_cache.get(sample_id)

                # On a cache miss, processing_ms already includes the model
                # call. Add the source generation time only for cache hits,
                # where processing_ms measures the fast lookup instead.
                if (
                    generation_invoked
                    and response_was_cached
                    and generation_time_ms is not None
                ):
                    estimated_total_ms = processing_ms + generation_time_ms
                else:
                    estimated_total_ms = processing_ms

                delivered_response = (
                    result.response if result.allowed else BLOCKED_MESSAGE
                )

                row = {
                    "sample_id": sample_id,
                    "vector": record["vector"],
                    "scenario": record["scenario"],
                    "configuration": config.value,
                    "defense": config.value,
                    "allowed": result.allowed,
                    "reason": result.reason,
                    "stages": list(result.stages),
                    "generation_invoked": generation_invoked,
                    "generation_latency_ms": (
                        round(generation_time_ms, 2)
                        if generation_invoked
                        and generation_time_ms is not None
                        else None
                    ),
                    "pipeline_processing_ms": round(processing_ms, 2),
                    "estimated_end_to_end_ms": round(estimated_total_ms, 2),
                    "provider": "groq",
                    "model": model,
                    "raw_model_response": raw_response,
                    "delivered_response": delivered_response,
                    "model_response_reused_across_configs": True,
                    "output_validation": (
                        validation.to_dict() if validation is not None else None
                    ),
                    "output_validation_error": (
                        validation is not None and validation.status == "error"
                    ),
                    "evaluation_type": "real_model_pilot_not_final_metrics",
                }

                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                total += 1
                if config != Configuration.A:
                    cache_hits += 1

    print(f"Split: {split}")
    print(f"Samples processed: {len(records)}")
    print(f"Configurations: {len(Configuration)}")
    print(f"Pipeline runs: {total}")
    print(f"Cached generation reuse opportunities: {cache_hits}")
    print(f"Results file: {output_path}")
    for validation_key, count in sorted(validation_counts.items()):
        print(f"Output validation {validation_key}: {count}")
    for config_name in sorted(validation_attempts):
        attempts = validation_attempts[config_name]
        errors = validation_errors.get(config_name, 0)
        print(
            f"Validator system error rate {config_name}: "
            f"{errors}/{attempts} ({errors / attempts:.1%}); "
            f"successful risk detections: {detected_risks.get(config_name, 0)}"
        )
    print("These are pilot outputs, not final security metrics.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument(
        "--split",
        choices=("train", "validation", "test"),
        default="validation",
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--sample-ids-from",
        type=Path,
        default=None,
        help="JSONL file whose sample_id values select records from the split.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/real_model_pilot.jsonl"),
    )
    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")

    run_experiment(
        args.data_dir,
        args.split,
        args.limit,
        args.output,
        args.sample_ids_from,
    )


if __name__ == "__main__":
    main()
