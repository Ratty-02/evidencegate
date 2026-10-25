from evals.paraphrase_eval import run


def test_controls_are_never_blocked():
    payload = run()
    s = payload["summary"]
    assert s["controls_passed"] == s["controls_total"]


def test_measurement_reports_every_paraphrase():
    payload = run()
    s = payload["summary"]
    assert s["paraphrases_total"] > 0
    assert 0 <= s["paraphrases_blocked"] <= s["paraphrases_total"]
