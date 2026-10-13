"""
Run the suites embedded in the modules themselves, so they count in CI.

krampitz_analyzer and e_verification_service each carry a run_test_suite()
returning (passed, failed). Until October 2026 nothing ran them except a
person at a terminal; a regression there would have shipped green.
"""

import runpy

import pytest

from vera import e_verification_service, krampitz_analyzer


@pytest.mark.parametrize("module,minimum", [
    (krampitz_analyzer, 12),
    (e_verification_service, 10),
])
def test_embedded_suite(module, minimum, capsys):
    passed, failed = module.run_test_suite()
    capsys.readouterr()
    assert failed == 0
    # A suite that silently ran fewer checks is not a pass.
    assert passed >= minimum


def test_pipeline_demo_runs(capsys):
    runpy.run_module("vera.demo_first_query", run_name="__main__")
    assert "5/5 demos produced expected outcomes" in capsys.readouterr().out


def test_example_script_runs(capsys):
    from pathlib import Path
    runpy.run_path(str(Path(__file__).parent.parent / "examples" / "demo_basic.py"),
                   run_name="__main__")
    out = capsys.readouterr().out
    assert out.count("ALLOWED") == 3 and out.count("BLOCKED") == 2
