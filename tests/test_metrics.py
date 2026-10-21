from agents.validation.service import ValidationAgent
from contracts import ValidationRunRequest


def test_acceptance_metrics_are_computed_by_real_agent_execution():
    run = ValidationAgent().run(ValidationRunRequest(jd_limit=100))

    assert run.status == "completed"
    assert run.metrics["evaluated_samples"]["jd"] == 100
    assert run.metrics["jd_field_macro_f1"] >= 0.90
    assert run.metrics["resume_field_macro_f1"] >= 0.90
    assert run.metrics["match_level_accuracy"] >= 0.90
    assert run.stage_results
