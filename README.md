# Quality Gate Env

Hackathon submission for an OpenEnv-based AI output quality gate.

## Repo Structure

```text
quality-gate-env/
├── inference.py
├── README.md
└── quality_gate_env/
    ├── __init__.py
    ├── models.py
    ├── client.py
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

## Setup

```bash
cd quality_gate_env
pip install -e .
```

## Run Server Locally

```bash
cd quality_gate_env
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

## Validate

```bash
cd quality_gate_env
openenv validate --url http://localhost:8000 --verbose
```

## Deploy to Hugging Face Spaces

```bash
cd quality_gate_env
openenv push --repo-id <your-hf-username>/quality-gate-env
```

## Run Inference

```bash
set HF_TOKEN=<token>
python inference.py
```
