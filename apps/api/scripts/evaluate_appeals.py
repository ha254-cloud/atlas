import argparse
import json
import sys
from pathlib import Path

from app.appeals.evaluation import evaluate_appeal_manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate a local synthetic or deidentified appeal acceptance manifest."
    )
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = evaluate_appeal_manifest(manifest)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
