from __future__ import annotations

from dataclasses import dataclass

from .models import OnlinePrediction


@dataclass(frozen=True, slots=True)
class LeakageAuditResult:
    passed: bool
    code: str
    detail: str = ""


class LeakageAuditor:
    """Hard no-future-information gate used by Online and Scientist."""

    forbidden_feature_fragments = ("future", "label", "mfe", "mae", "forward_return")

    def audit_prediction(self, prediction: OnlinePrediction) -> LeakageAuditResult:
        if prediction.features_frozen_at > prediction.created_at + 1e-9:
            return LeakageAuditResult(False, "FEATURES_AFTER_PREDICTION")
        if prediction.label is not None:
            if prediction.label_observed_at is None:
                return LeakageAuditResult(False, "MISSING_LABEL_TIMESTAMP")
            if prediction.label_observed_at < prediction.label_due_at:
                return LeakageAuditResult(False, "LABEL_TOO_EARLY")
        for key in prediction.features:
            lowered = key.lower()
            if any(fragment in lowered for fragment in self.forbidden_feature_fragments):
                return LeakageAuditResult(False, "FORBIDDEN_FEATURE", key)
        return LeakageAuditResult(True, "PASS")
