from evals.run_eval import build_cases, evaluate


def test_every_injected_error_is_caught():
    _, summary = evaluate(build_cases())
    assert summary["injected_caught"] == summary["injected_total"]


def test_no_clean_draft_is_falsely_blocked():
    _, summary = evaluate(build_cases())
    assert summary["clean_passed"] == summary["clean_total"]


def test_routing_is_correct():
    _, summary = evaluate(build_cases())
    assert summary["routing_correct"] == summary["routing_total"]


def test_all_cases_match_expectations():
    results, summary = evaluate(build_cases())
    failed = [r.case.case_id for r in results if not r.passed]
    assert failed == []
