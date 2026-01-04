import types
from examples.rca_engine import RCAEngine


def test_analyze_incident_with_mocks():
    # Create an RCAEngine instance without calling __init__ to avoid real Neo4j connections
    engine = RCAEngine.__new__(RCAEngine)

    # Mock graph
    class MockGraph:
        def annotate_error(self, service, data):
            pass
        def find_error_propagation_path(self, service):
            return [['payment-service', 'db-service']]
        def get_dependencies(self, service):
            return [{'service': 'db-service'}]
        def get_service(self, name):
            return {'error_count': 5, 'source_path': '/tmp'}

    # Mock GitAnalyzer
    class MockGit:
        def get_recent_commits(self, service_path=None, hours=48, limit=5):
            return [{'hash': 'abc123', 'message': 'Fix bug', 'author': 'dev', 'date': '2026-01-01'}]
        def get_deployment_correlation(self, service_name, hours=24):
            return [{'date': '2026-01-01', 'message': 'deployed'}]

    # Mock scorer
    class MockScorer:
        def rank_candidates(self, candidates):
            for c in candidates:
                c['confidence_score'] = 95
                c['score_breakdown'] = {}
            return candidates

    # Mock CodeLocalizer
    class MockLocalizer:
        def localize_from_incident(self, incident_data):
            return {'root_cause_location': {'file': 'PaymentService.java', 'line': 237}, 'recommendations': ['Add null check']}

    # Attach mocks
    engine.graph = MockGraph()
    engine.git_analyzer = MockGit()
    engine.scorer = MockScorer()
    engine.code_localizer = MockLocalizer()

    # Run analysis
    incident = {
        'service': 'payment-service',
        'endpoint': '/pay',
        'error_type': 'NullPointerException',
        'error_message': 'NPE',
        'timestamp': '2026-01-01T10:00:00',
        'severity': 'high',
        'stack_trace': 'at PaymentService.process(PaymentService.java:42)',
        'trace_id': 'trace-abc-123'
    }

    report = engine.analyze_incident(incident)

    assert 'probable_root_causes' in report
    assert len(report['probable_root_causes']) >= 1
    top = report['probable_root_causes'][0]
    assert 'confidence_score' in top and top['confidence_score'] == 95
