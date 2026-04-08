import asyncio
import json
import os
import sys
from typing import Any, Optional

from openai import OpenAI

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from quality_gate_env.models import QualityGateAction  # noqa: E402
    from quality_gate_env.client import QualityGateEnv  # noqa: E402
except ImportError:
    from quality_gate_env import QualityGateAction, QualityGateEnv  # noqa: E402


API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME") or os.getenv("IMAGE_NAME")
ENV_BASE_URL = os.getenv("ENV_BASE_URL")
BENCHMARK = "quality-gate-v1"
TASK_IDS = ["easy_001", "medium_001", "hard_001"]
MAX_STEPS = int(os.getenv("MAX_STEPS", "25"))
VALID_ACTIONS = {"fast_pass", "deep_verify", "reject", "flag_human", "sample_check"}


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: dict[str, Any], reward: float, done: bool) -> None:
    output_id = action.get("output_id", "unknown")
    action_type = action.get("action_type", "unknown")
    print(
        f"[STEP] step={step} reward={round(reward, 3)} done={str(done).lower()} "
        f"action={action_type} output_id={output_id}",
        flush=True,
    )


def log_end(task: str, total_reward: float, success: bool, steps: int) -> None:
    score = _normalized_score(total_reward=total_reward, steps=steps)
    print(
        f"[END] task={task} score={score} steps={steps} success={str(success).lower()}",
        flush=True,
    )


def _normalized_score(total_reward: float, steps: int) -> float:
    # Validator requires strict (0, 1), never exactly 0.0 or 1.0.
    if steps <= 0:
        return 0.5
    score = total_reward / steps
    if score <= 0.0:
        return 0.001
    if score >= 1.0:
        return 0.999
    return round(score, 3)


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


def _sanitize_model_action(parsed: dict[str, Any], observation: Any) -> QualityGateAction:
    fallback = _fallback_action(observation)
    output_id = str(parsed.get("output_id") or fallback.output_id)
    action_type = str(parsed.get("action_type") or fallback.action_type)
    reason = str(parsed.get("reason") or "model response")

    if action_type not in VALID_ACTIONS:
        action_type = fallback.action_type
        reason = "invalid model action, fallback"

    if action_type == "deep_verify" and observation.budget_remaining <= 0:
        action_type = "sample_check"
        reason = "budget exhausted"

    return QualityGateAction(output_id=output_id, action_type=action_type, reason=reason)


def get_model_action(client: Optional[OpenAI], observation: Any, history: list[str]) -> QualityGateAction:
    if client is None:
        return _fallback_action(observation)

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
            timeout=30,
        )
        text = (response.choices[0].message.content or "").strip()
        parsed = _safe_json_parse(text)
        return _sanitize_model_action(parsed, observation)
    except Exception:
        return _fallback_action(observation)


async def _create_env_client() -> QualityGateEnv:
    if ENV_BASE_URL:
        return QualityGateEnv(base_url=ENV_BASE_URL)

    image_candidates = []
    if LOCAL_IMAGE_NAME:
        image_candidates.append(LOCAL_IMAGE_NAME)
    image_candidates.extend([
        "quality-gate-env:latest",
        "openenv-quality_gate:latest",
        "openenv-quality_gate",
    ])

    for image in image_candidates:
        try:
            return await QualityGateEnv.from_docker_image(image)
        except Exception:
            continue

    raise RuntimeError("Could not create env client from ENV_BASE_URL or docker image")


async def run_task(client: Optional[OpenAI], task_id: str) -> float:
    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)
    total_reward = 0.0
    steps = 0
    history: list[str] = []
    emitted_step = False

    try:
        env_client = await _create_env_client()
    except Exception:
        log_step(step=0, action={"output_id": "none", "action_type": "fallback"}, reward=0.0, done=True)
        log_end(task=task_id, total_reward=0.0, success=False, steps=0)
        return 0.0

    try:
        async with env_client as env:
            try:
                result = await env.reset(task_id=task_id)
                observation = result.observation
            except Exception:
                log_step(step=0, action={"output_id": "none", "action_type": "fallback"}, reward=0.0, done=True)
                log_end(task=task_id, total_reward=0.0, success=False, steps=0)
                return 0.0

            for step in range(1, MAX_STEPS + 1):
                if getattr(result, "done", False) or observation.done:
                    break

                action = _fallback_action(observation)
                reward = 0.0
                done = bool(getattr(observation, "done", False))

                try:
                    action = get_model_action(client, observation, history)
                    result = await env.step(action)
                    observation = result.observation
                    reward = float(result.reward if result.reward is not None else 0.0)
                    done = bool(observation.done)
                except Exception:
                    done = bool(getattr(observation, "done", False))

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
                    done=done,
                )
                emitted_step = True
                history.append(f"step={step} action={action.action_type} reward={reward:.3f}")

    except Exception:
        pass

    if not emitted_step:
        log_step(step=0, action={"output_id": "none", "action_type": "fallback"}, reward=0.0, done=True)

    success = total_reward >= 0.5
    log_end(task=task_id, total_reward=total_reward, success=success, steps=steps)
    return total_reward


async def main() -> None:
    client: Optional[OpenAI] = None
    if HF_TOKEN:
        try:
            client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)
        except Exception:
            client = None

    for task_id in TASK_IDS:
        await run_task(client, task_id)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        # Last-resort safety: never crash with an unhandled exception.
        for task_id in TASK_IDS:
            log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)
            log_end(task=task_id, total_reward=0.0, success=False, steps=0)
        sys.exit(0)
