import json
import subprocess
from pathlib import Path

from examples.test_runner import TestRunner, TestImpactAnalyzer


def test_parse_jest_output_average_coverage(tmp_path):
    runner = TestRunner(str(tmp_path))
    data = {
        'numTotalTests': 10,
        'numPassedTests': 9,
        'numFailedTests': 1,
        'coverageMap': {
            'file1.js': {'lines': {'pct': 80}},
            'file2.js': {'lines': {'pct': 60}},
        }
    }
    cp = subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps(data), stderr='')
    res = runner._parse_jest_output(cp)
    assert res.coverage_percentage == 70.0
    assert res.tests_run == 10
    assert res.tests_passed == 9
    assert res.tests_failed == 1


def test_find_affected_tests_direct(tmp_path):
    project = tmp_path
    (project / 'service.py').write_text('def foo(): pass')
    (project / 'test_service.py').write_text('import service\n\ndef test_foo(): assert True')

    analyzer = TestImpactAnalyzer(str(project))
    affected = analyzer.find_affected_tests([str(project / 'service.py')], language='python')
    # Should include the test_service.py path
    assert any('test_service.py' in p or p == 'test_service.py' for p in affected)
