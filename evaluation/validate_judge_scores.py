
import json
import math
import sys
from pathlib import Path


def validate_file(path: Path) -> int:
    errors = []
    count = 0

    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            if not line.strip():
                continue

            count += 1

            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"Line {line_no}: invalid JSON ({exc.msg})")
                continue

            if not isinstance(row, dict):
                errors.append(f"Line {line_no}: each row must be an object")
                continue

            for field in ("defense", "vector"):
                if not isinstance(row.get(field), str) or not row[field].strip():
                    errors.append(f"Line {line_no}: missing/invalid '{field}'")

            if not isinstance(row.get("json_valid"), bool):
                errors.append(f"Line {line_no}: 'json_valid' must be boolean")
                continue

            pred = row.get("pred")
            severity = pred.get("severity") if isinstance(pred, dict) else None

            # The official evaluator treats invalid judge records as worst case.
            # A valid record must contain a numeric, finite severity.
            if row["json_valid"]:
                if (
                    isinstance(severity, bool)
                    or not isinstance(severity, (int, float))
                    or not math.isfinite(severity)
                ):
                    errors.append(
                        f"Line {line_no}: valid judge output needs numeric "
                        "'pred.severity'"
                    )

    print(f"Rows checked: {count}")

    if count == 0:
        errors.append("File contains no records")

    if errors:
        print(f"Validation failed: {len(errors)} issue(s)")
        for error in errors[:50]:
            print("-", error)
        if len(errors) > 50:
            print(f"... plus {len(errors) - 50} more")
        return 1

    print("Validation passed.")
    print("This confirms schema only, not judgment accuracy.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            "Usage: python -m evaluation.validate_judge_scores "
            "PATH_TO_JUDGE_SCORES.jsonl"
        )
        raise SystemExit(2)

    raise SystemExit(validate_file(Path(sys.argv[1])))
