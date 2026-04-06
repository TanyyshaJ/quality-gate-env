from openenv.core.env_server.types import Action, Observation
from pydantic import Field
from typing import List, Optional

class QualityGateAction(Action):
    """Agent's decision on one AI output."""
    output_id: str = Field(..., description="ID of the output being reviewed")
    action_type: str = Field(..., description="One of: fast_pass, deep_verify, reject, flag_human, sample_check")
    reason: str = Field(..., description="Agent's reasoning for this decision")


class QualityGateObservation(Observation):
    """What the agent sees at each step."""
    task_id: str = Field(default="", description="Current task ID")
    outputs_to_review: List[dict] = Field(default_factory=list, description="AI outputs visible to agent")
    budget_remaining: int = Field(default=0, description="Deep verify budget remaining")
    step: int = Field(default=0, description="Current step number")
    reward: float = Field(default=0.0, description="Reward from last action")
    done: bool = Field(default=False, description="Whether episode is complete")
    feedback: str = Field(default="", description="Feedback on last action")