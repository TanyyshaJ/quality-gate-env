# quality-gate-env

OpenEnv hackathon submission: an AI output quality-gate environment with constrained review budget.

## What This Project Does

The environment simulates production quality control for AI-generated outputs.  
At each step, an agent chooses one action for an output:

- `fast_pass`
- `deep_verify` (costs budget)
- `reject`
- `flag_human`
- `sample_check`

Three tasks are included:

- `easy_001` (5 outputs, budget 3)
- `medium_001` (10 outputs, budget 4)
- `hard_001` (15 outputs, budget 3)

## Repository Layout

```text
quality-gate-env/
├── inference.py
├── README.md
└── quality_gate_env/
    ├── __init__.py
    ├── models.py
    ├── client.py
    ├── openenv.yaml
    ├── uv.lock
    ├── data/
    │   ├── easy.json
    │   ├── medium.json
    │   └── hard.json
    └── server/
        ├── app.py
        ├── quality_gate_env_environment.py
        └── Dockerfile
```

## Prerequisites

- Python 3.10+
- Docker Desktop (for container build/run)
- Hugging Face account + token
- `openenv-core` installed

## Setup

```bash
cd quality_gate_env
pip install -e .
```

## Local Validation

```bash
cd quality_gate_env
openenv validate --verbose
```

Expected: `[OK] ... Ready for multi-mode deployment`

## Run Locally (Without Docker)

Terminal 1:

```bash
cd quality_gate_env
python -m quality_gate_env.server.app
```

Terminal 2:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/reset -H "Content-Type: application/json" -d "{\"task_id\":\"easy_001\"}"
```

## Run With Docker

```bash
cd quality_gate_env
docker build -t quality-gate-env:latest -f server/Dockerfile .
docker run --rm -p 8000:8000 quality-gate-env:latest
```

## Deploy to Hugging Face Spaces

```bash
cd quality_gate_env
huggingface-cli login
openenv push --repo-id <your-hf-username>/quality-gate-env
```

Live URL format:

`https://<your-hf-username>-quality-gate-env.hf.space`

## Run Inference

Use local/live server:

```bash
set ENV_BASE_URL=http://localhost:8000
set HF_TOKEN=<your_hf_token>
python inference.py
```

Or rely on Docker image startup from `inference.py`:

```bash
set HF_TOKEN=<your_hf_token>
set IMAGE_NAME=quality-gate-env:latest
python inference.py
```

Expected logs per task:

- `[START]`
- `[STEP]`
- `[END]`

## Submission Checklist

- GitHub repo pushed with latest code
- HF Space is `Running`
- `/health`, `/reset`, `/step`, `/state` work on HF Space
- `inference.py` completes all 3 tasks successfully
