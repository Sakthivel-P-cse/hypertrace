from examples.static_analyzer import StaticAnalyzer, FindingType


def test_complexity_detection(tmp_path):
    file = tmp_path / 'sample.py'
    file.write_text('''def complex():
    if True:
        for i in range(10):
            if i%2==0:
                while i>0:
                    if i%3==0:
                        pass
''')
    analyzer = StaticAnalyzer(str(tmp_path), config={'complexity_threshold': 3, 'fail_on_secrets': False, 'fail_on_unsafe_apis': False})
    result = analyzer.analyze('python', changed_files=['sample.py'], security_scan=False)
    assert result.total_findings >= 1
    assert any(f.finding_type == FindingType.COMPLEXITY for f in result.findings)
