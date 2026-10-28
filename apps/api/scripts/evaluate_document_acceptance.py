import argparse
import json
import sys
from pathlib import Path

from app.documents.acceptance import evaluate_acceptance_manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate aggregate OCR and classification acceptance evidence."
    )
    parser.add_argument(
        "manifest",
        type=Path,
        help="Path to a local, de-identified JSON acceptance manifest.",
    )
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = evaluate_acceptance_manifest(manifest)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
