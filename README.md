<<<<<<< HEAD
﻿# quality-gate-env
=======
# Quality Gate Env
>>>>>>> a9e29bbf18743740e0c60165ce3ab6504d1adf40

OpenEnv hackathon submission for an AI output quality-gate environment with limited review budget.

## Overview

This environment simulates a production quality-control layer for AI-generated outputs. At each step, an agent receives candidate outputs and must choose one action:

- `fast_pass`
- `deep_verify` (uses budget)
- `reject`
- `flag_human`
- `sample_check`

The goal is to maximize reward by balancing correctness and budget usage.

## Tasks

| Task ID | Difficulty | Outputs | Budget |
|---|---|---:|---:|
| `easy_001` | Easy | 5 | 3 |
| `medium_001` | Medium | 10 | 4 |
| `hard_001` | Hard | 15 | 3 |

## Repository Structure

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

## Quick Start

1. Install dependencies.

```bash
cd quality_gate_env
pip install -e .
```

2. Validate environment structure.

```bash
openenv validate --verbose
```

Expected output includes: `[OK] ... Ready for multi-mode deployment`

## Run Locally (No Docker)

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

## API Endpoints

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/health` | Service health check |
| `POST` | `/reset` | Start a new episode |
| `POST` | `/step` | Apply one action |
| `GET` | `/state` | Read current episode state |

## Deploy to Hugging Face Spaces

Run from the environment root (the folder that contains `openenv.yaml`):

```bash
cd quality_gate_env
huggingface-cli login
openenv push --repo-id <your-hf-username>/quality-gate-env
```

Live URL format:

`https://<your-hf-username>-quality-gate-env.hf.space`

## End-to-End Evaluation

Run inference against a running local or hosted server:

```bash
set ENV_BASE_URL=http://localhost:8000
set HF_TOKEN=<your_hf_token>
python inference.py
```

Alternative mode (Docker image launch from script):

```bash
set HF_TOKEN=<your_hf_token>
set IMAGE_NAME=quality-gate-env:latest
python inference.py
```

Expected logs per task:

- `[START]`
- `[STEP]`
- `[END]`

## Common Issues

1. `Not an OpenEnv environment directory` when running `openenv push`.
Run `openenv push` from `quality_gate_env/`, not repo root.

2. `Docker is not available` in `inference.py`.
Either start Docker Desktop or set `ENV_BASE_URL` to an already running server.

3. `Connection refused` to `ws://localhost:8000/ws`.
Server is not running on port `8000`; start it first and verify `/health`.

4. `Unsupported task_id ... data file not found`.
Rebuild image after latest code changes using `--no-cache`.

## Submission Checklist

- [ ] GitHub repo has latest code and README
- [ ] Hugging Face Space is `Running`
- [ ] `/health`, `/reset`, `/step`, `/state` are working on live URL
- [ ] `python inference.py` completes all 3 tasks with `[START]/[STEP]/[END]` logs
- [ ] Repo URL + Space URL ready for dashboard submission
