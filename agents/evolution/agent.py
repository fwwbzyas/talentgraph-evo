import argparse
import json
from pathlib import Path

from contracts import JobGraph
from agents.evolution.service import EvolutionAgent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = EvolutionAgent().run(JobGraph(**payload))
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
