import json
import os
from importlib import resources
from pathlib import Path
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment

try:
    from ..models import QualityGateAction, QualityGateObservation, QualityGateState
except ImportError:
    from models import QualityGateAction, QualityGateObservation, QualityGateState


class QualityGateEnvironment(Environment):

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._state = QualityGateState(episode_id=str(uuid4()), step_count=0)
        self._task_data = None
        self._index = 0
        self._budget_used = 0
        self._total_score = 0.0
        self._done = False
        self._task_id = ""

    def reset(self, task_id: str = "easy_001") -> QualityGateObservation:
        self._task_data = self._load(task_id)
        self._index = 0
        self._budget_used = 0
        self._total_score = 0.0
        self._done = False
        self._task_id = task_id
        self._state = QualityGateState(
            episode_id=str(uuid4()),
            step_count=0,
            task_id=task_id,
            budget_used=0,
            total_score=0.0,
            done=False,
        )
        return self._observe(reward=0.0, feedback="Episode started. Review the outputs carefully.")

    def step(self, action: QualityGateAction) -> QualityGateObservation:
        if self._done:
            return self._observe(reward=0.0, feedback="Episode already finished.")

        outputs = self._task_data["outputs"]
        current = outputs[self._index]

        reward, feedback = self._grade(action, current)

        if action.action_type == "deep_verify":
            self._budget_used += 1

        self._total_score += reward
        self._state.step_count += 1
        self._index += 1

        if self._index >= len(outputs):
            self._done = True
        self._state.task_id = self._task_id
        self._state.budget_used = self._budget_used
        self._state.total_score = round(self._total_score, 3)
        self._state.done = self._done

        return self._observe(reward=round(reward, 3), feedback=feedback)

    @property
    def state(self) -> QualityGateState:
        return self._state

    def _load(self, task_id: str) -> dict:
        task_id = (task_id or "").strip().lower()
        difficulty = task_id.split("_")[0] if task_id else ""
        if difficulty not in {"easy", "medium", "hard"}:
            raise ValueError(f"Unsupported task_id '{task_id}'. Expected easy_*, medium_*, or hard_*.")

        filename = f"{difficulty}.json"
        base_dir = Path(__file__).resolve()
        env_data_dir = os.getenv("QUALITY_GATE_DATA_DIR", "").strip()
        candidate_paths = [
            base_dir.parent.parent / "data" / filename,  # quality_gate_env/data
            base_dir.parent / "data" / filename,  # server/data (fallback)
            Path("/app/env/data") / filename,  # docker source tree
            Path.cwd() / "quality_gate_env" / "data" / filename,  # repo root execution
            Path.cwd() / "data" / filename,  # env root execution
        ]
        if env_data_dir:
            candidate_paths.insert(0, Path(env_data_dir) / filename)

        for path in candidate_paths:
            if path.exists():
                with path.open(encoding="utf-8") as f:
                    return json.load(f)

        # Package-resource fallback for installed environments.
        try:
            data_resource = resources.files("quality_gate_env").joinpath("data", filename)
            if data_resource.is_file():
                with data_resource.open("r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass

        searched = ", ".join(str(p) for p in candidate_paths)
        raise ValueError(
            f"Unsupported task_id '{task_id}'. Expected easy_*, medium_*, or hard_*. "
            f"Data file '{filename}' not found. Searched: {searched}"
        )

    def _grade(self, action: QualityGateAction, output: dict):
        score = 0.0
        correct = output["ground_truth"]
        risk = output["risk_signal"]

        if correct == "bad":
            scores = {
                "reject": 0.4,
                "deep_verify": 0.3,
                "flag_human": 0.2,
                "sample_check": 0.1,
                "fast_pass": -0.4
            }
        else:
            scores = {
                "fast_pass": 0.4,
                "sample_check": 0.3,
                "deep_verify": 0.1,
                "flag_human": 0.1,
                "reject": -0.2
            }

        score += scores.get(action.action_type, 0.0)

        # Bonus: agent gave a real reason
        if len(action.reason) > 15:
            score += 0.2

        # Bonus: risk signal alignment
        if risk == "high" and action.action_type in ["deep_verify", "reject", "flag_human"]:
            score += 0.2
        elif risk == "low" and action.action_type == "fast_pass":
            score += 0.2

        # Bonus: budget not exhausted
        budget_total = self._task_data.get("budget", 3)
        if self._budget_used < budget_total:
            score += 0.1

        feedback = (
            f"Output '{output['id']}' was {correct} | "
            f"risk: {risk} | "
            f"you chose: {action.action_type} | "
            f"score: {round(max(0.0, min(1.0, score)), 3)}"
        )

        return max(0.0, min(1.0, score)), feedback

    def _observe(self, reward: float, feedback: str) -> QualityGateObservation:
        outputs = self._task_data["outputs"] if self._task_data else []
        budget_total = self._task_data.get("budget", 3) if self._task_data else 3

        # Show agent next 3 outputs but strip ground_truth
        visible = outputs[self._index:self._index + 3]
        safe = [
            {
                "id": o["id"],
                "content": o["content"],
                "type": o["type"],
                "risk_signal": o["risk_signal"]
            }
            for o in visible
        ]

        return QualityGateObservation(
            task_id=self._task_id,
            outputs_to_review=safe,
            budget_remaining=max(0, budget_total - self._budget_used),
            step=self._state.step_count,
            reward=reward,
            done=self._done,
            feedback=feedback
        )
