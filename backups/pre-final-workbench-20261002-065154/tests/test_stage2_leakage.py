from jarvis.leakage import LeakageAuditor
from jarvis.models import OnlinePrediction


def test_leakage_auditor_passes_strict_future_label():
    pred = OnlinePrediction(
        experiment_id="e1", identity_key="base:a:b", model_key="m",
        created_at=100.0, features_frozen_at=100.0,
        features={"age_seconds": 10.0, "log_liquidity": 3.0},
        predicted_probability=0.5, label_due_at=1000.0,
        label=True, label_observed_at=1001.0, learned_at=1002.0,
    )
    result = LeakageAuditor().audit_prediction(pred)
    assert result.passed
    assert result.code == "PASS"


def test_leakage_auditor_blocks_future_feature():
    pred = OnlinePrediction(
        experiment_id="e1", identity_key="base:a:b", model_key="m",
        created_at=100.0, features_frozen_at=100.0,
        features={"future_return": 2.0}, predicted_probability=0.5,
        label_due_at=1000.0, label=True, label_observed_at=1001.0,
    )
    result = LeakageAuditor().audit_prediction(pred)
    assert not result.passed
    assert result.code == "FORBIDDEN_FEATURE"


def test_leakage_auditor_blocks_early_label():
    pred = OnlinePrediction(
        experiment_id="e1", identity_key="base:a:b", model_key="m",
        created_at=100.0, features_frozen_at=100.0,
        features={"age_seconds": 10.0}, predicted_probability=0.5,
        label_due_at=1000.0, label=True, label_observed_at=999.0,
    )
    result = LeakageAuditor().audit_prediction(pred)
    assert not result.passed
    assert result.code == "LABEL_TOO_EARLY"
