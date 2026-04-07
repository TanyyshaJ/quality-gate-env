"""Quality Gate environment client."""

from typing import Any

from openenv.core import EnvClient
from openenv.core.client_types import StepResult

from .models import QualityGateAction, QualityGateObservation, QualityGateState


class QualityGateEnv(EnvClient[QualityGateAction, QualityGateObservation, QualityGateState]):
    """Client wrapper for the quality gate environment."""

    def _step_payload(self, action: QualityGateAction) -> dict[str, Any]:
        return {
            "output_id": action.output_id,
            "action_type": action.action_type,
            "reason": action.reason,
        }

    def _parse_result(self, payload: dict[str, Any]) -> StepResult[QualityGateObservation]:
        observation = QualityGateObservation(**payload.get("observation", {}))
        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: dict[str, Any]) -> QualityGateState:
        return QualityGateState(**payload)
