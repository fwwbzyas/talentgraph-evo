import argparse
import json
from pathlib import Path

from contracts import ImportRequest
from agents.data.service import DataAgent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = DataAgent().run(ImportRequest(**payload))
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
