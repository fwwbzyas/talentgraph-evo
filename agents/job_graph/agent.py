import argparse
import json
from pathlib import Path

from contracts import CleanedDataBatch
from agents.job_graph.service import JobGraphAgent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--target", default="Java 后端工程师")
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = JobGraphAgent().run(CleanedDataBatch(**payload), args.target)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
