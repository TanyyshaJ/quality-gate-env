---
title: Quality Gate Environment
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
  - quality-gate
---

# Quality Gate Environment

This OpenEnv environment simulates a quality-control layer for AI-generated outputs.
At each step, the agent chooses one action for the current output:

- `fast_pass`
- `deep_verify` (costs budget)
- `reject`
- `flag_human`
- `sample_check`

Rewards are based on alignment with hidden ground truth (`good`/`bad`), risk signal usage, and budget discipline.

## Task Set

- `easy_001`: 5 outputs, budget 3
- `medium_001`: 10 outputs, budget 4
- `hard_001`: 15 outputs, budget 3

Data files live in:

- `data/easy.json`
- `data/medium.json`
- `data/hard.json`

## Project Layout

```text
quality_gate_env/
├── __init__.py
├── client.py
├── models.py
├── openenv.yaml
├── data/
│   ├── easy.json
│   ├── medium.json
│   └── hard.json
└── server/
    ├── app.py
    ├── quality_gate_env_environment.py
    └── Dockerfile
```

## Local Run

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
```

## Validate

```bash
openenv validate --url http://localhost:8000 --verbose
```

## Build Docker

```bash
docker build -f server/Dockerfile -t quality-gate-env:latest .
docker run -p 8000:8000 quality-gate-env:latest
```

## Deploy to Hugging Face Spaces

```bash
openenv push --repo-id <your-hf-username>/quality-gate-env
```

After deploy, your live URL is:
`https://<your-hf-username>-quality-gate-env.hf.space`
