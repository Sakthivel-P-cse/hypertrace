from examples.post_deployment_verifier import PostDeploymentVerifier


def test_compare_metric_improved_significant():
    deployment_result = {'deployment_id': 'DEP-1', 'baseline_metrics': {}}
    config = {'metrics': ['error_rate'], 'improvement_threshold': 0.05, 'degradation_threshold': 0.05, 'significance_level': 0.1}
    verifier = PostDeploymentVerifier('http://localhost', config, deployment_result)

    comp = verifier._compare_metric('error_rate', 'payment-service', 'production', control_pct=50, treatment_pct=50)

    # In the mock data, treatment is better than control so improvement should be positive
    assert comp.improvement_pct > 0
    assert isinstance(comp.confidence_interval, tuple)
    assert 0.0 <= comp.p_value <= 1.0
