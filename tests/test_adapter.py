from pathlib import Path

from pw_sdk.testkit import check_directory

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_fixtures_match_expected_output():
    results = check_directory(FIXTURES)
    assert results, "no fixtures found"
    failures = {result.name: result.problems for result in results if not result.passed}
    assert not failures, failures
