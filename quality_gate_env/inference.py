import asyncio
import json
import os
import sys
from typing import Any

from openai import OpenAI

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from quality_gate_env import QualityGateAction, QualityGateEnv  # noqa: E402


API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")
ENV_BASE_URL = os.getenv("ENV_BASE_URL")
BENCHMARK = "quality-gate-v1"
TASK_IDS = ["easy_001", "medium_001", "hard_001"]
MAX_STEPS = int(os.getenv("MAX_STEPS", "25"))


def log_start(task: str, env: str, model: str) -> None:
    print(json.dumps({"type": "[START]", "task": task, "env": env, "model": model}), flush=True)


def log_step(step: int, action: dict[str, Any], reward: float, done: bool) -> None:
    print(
        json.dumps(
            {"type": "[STEP]", "step": step, "action": action, "reward": round(reward, 3), "done": done}
        ),
        flush=True,
    )


def log_end(task: str, total_reward: float, success: bool, steps: int) -> None:
    print(
        json.dumps(
            {
                "type": "[END]",
                "task": task,
                "total_reward": round(total_reward, 3),
                "success": success,
                "steps": steps,
            }
        ),
        flush=True,
    )


def _safe_json_parse(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if "```" in text:
        blocks = text.split("```")
        if len(blocks) >= 2:
            text = blocks[1].replace("json", "", 1).strip()
    return json.loads(text)


def _fallback_action(observation: Any) -> QualityGateAction:
    first = observation.outputs_to_review[0] if observation.outputs_to_review else {"id": "unknown", "risk_signal": "low"}
    risk_signal = first.get("risk_signal", "low")
    if observation.budget_remaining <= 0 and risk_signal in {"high", "medium"}:
        action_type = "flag_human"
    elif risk_signal == "high" and observation.budget_remaining > 0:
        action_type = "deep_verify"
    elif risk_signal == "medium":
        action_type = "sample_check"
    else:
        action_type = "fast_pass"
    return QualityGateAction(output_id=first["id"], action_type=action_type, reason="fallback policy")


def get_model_action(client: OpenAI, observation: Any, history: list[str]) -> QualityGateAction:
    outputs_text = json.dumps(observation.outputs_to_review, indent=2)
    prompt = f"""You are a quality gate agent for AI-generated outputs.

Budget remaining for deep checks: {observation.budget_remaining}
Current step: {observation.step}
Recent history: {history[-3:] if history else "None"}

Outputs:
{outputs_text}

Allowed actions:
- fast_pass
- deep_verify (costs budget)
- reject
- flag_human
- sample_check

Respond with JSON only:
{{"output_id":"<id>","action_type":"<action>","reason":"<brief reason>"}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=180,
        )
        text = (response.choices[0].message.content or "").strip()
        parsed = _safe_json_parse(text)
        return QualityGateAction(
            output_id=parsed["output_id"],
            action_type=parsed["action_type"],
            reason=parsed.get("reason", "no reason"),
        )
    except Exception:  # pragma: no cover
        return _fallback_action(observation)


async def _create_env_client() -> QualityGateEnv:
    if ENV_BASE_URL:
        return QualityGateEnv(base_url=ENV_BASE_URL)
    if LOCAL_IMAGE_NAME:
        return await QualityGateEnv.from_docker_image(LOCAL_IMAGE_NAME)
    raise RuntimeError("Set ENV_BASE_URL or LOCAL_IMAGE_NAME before running inference.py")


async def run_task(client: OpenAI, task_id: str) -> float:
    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)
    total_reward = 0.0
    steps = 0
    history: list[str] = []

    env_client = await _create_env_client()
    async with env_client as env:
        result = await env.reset(task_id=task_id)
        observation = result.observation

        for step in range(1, MAX_STEPS + 1):
            if result.done or observation.done:
                break

            action = get_model_action(client, observation, history)
            result = await env.step(action)
            observation = result.observation
            reward = float(result.reward if result.reward is not None else observation.reward)

            total_reward += reward
            steps += 1
            log_step(
                step=step,
                action={
                    "output_id": action.output_id,
                    "action_type": action.action_type,
                    "reason": action.reason,
                },
                reward=reward,
                done=observation.done,
            )
            history.append(f"step={step} action={action.action_type} reward={reward:.3f}")

    success = total_reward >= 0.5
    log_end(task=task_id, total_reward=total_reward, success=success, steps=steps)
    return total_reward


async def main() -> None:
    if not HF_TOKEN:
        raise RuntimeError("Set HF_TOKEN before running inference.py")

    client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)
    for task_id in TASK_IDS:
        await run_task(client, task_id)


if __name__ == "__main__":
    asyncio.run(main())
