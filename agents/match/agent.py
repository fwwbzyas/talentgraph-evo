import argparse
import json
from pathlib import Path

from contracts import CandidateProfile, JobGraph
from agents.match.service import MatchAgent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-graph", required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    graph = JobGraph(**json.loads(Path(args.job_graph).read_text(encoding="utf-8")))
    profile = CandidateProfile(**json.loads(Path(args.candidate).read_text(encoding="utf-8")))
    result = MatchAgent().run(graph, profile)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
