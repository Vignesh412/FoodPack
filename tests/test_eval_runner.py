from scripts.run_evals import build_report


def test_golden_evaluation_report_passes_all_automated_gates():
    report = build_report()
    assert report["summary"]["automated_gates_pass"] is True
    assert report["summary"]["passed"] == report["summary"]["total"]
    assert report["summary"]["total"] == 52
    assert len(report["suites"]["comparison"]) == 3
    assert len(report["suites"]["barcode"]) == 2
    assert len(report["suites"]["alternatives"]) == 5


def test_evaluation_report_does_not_overclaim_vision_accuracy():
    report = build_report()
    assert report["summary"]["image_readiness"] == "limited"
    assert "not enough for a general vision-accuracy rate" in report["summary"]["image_note"]
    assert report["vision_evidence"]["completed_end_to_end"] == 4
    assert report["vision_evidence"]["retake_requested"] == 1
    assert report["vision_evidence"]["accuracy_rate_published"] is False
