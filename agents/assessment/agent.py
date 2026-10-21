import argparse
import json
from pathlib import Path

from agents.assessment.service import AssessmentAgent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    agent = AssessmentAgent()
    result = agent.start(
        candidate_id=payload.get("candidate_id", "candidate_demo"),
        target_job_id=payload.get("target_job_id", "java_后端工程师"),
        resume_text=payload.get("resume_text"),
    )
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
