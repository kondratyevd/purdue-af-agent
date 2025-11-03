# Purdue AF Agent

Minimal LangChain agent with LangGraph setup for forwarding queries to LLM.

## Project Structure

```
.
├── app/                    # Source code
│   ├── agent.py           # LangGraph agent (single node forwarding to LLM)
│   ├── config.py           # Configuration
│   ├── main.py             # FastAPI app
│   ├── utils.py            # Utility functions (timezone, time parsing)
│   └── requirements.txt    # Python dependencies
├── helm/                   # Kubernetes Helm charts
│   └── purdue-af-agent/
├── docker-compose.yml      # Local development
├── Dockerfile              # Agent container
├── deploy-helm.sh          # Deployment script
└── test.py                # Test client

```

## Local Testing

```bash
export OPENAI_API_KEY="your-api-key"
./run_local.sh
```

Or directly:
```bash
docker compose up --build
```

In another terminal:
```bash
python test.py "your query here"
```

## Kubernetes Deployment

```bash
# Deploy agent
./deploy-helm.sh -n cms
```
