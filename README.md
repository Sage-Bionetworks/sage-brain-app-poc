# sage-brain-app-poc

Streamlit POC for the [Sage Brain](https://github.com/Sage-Bionetworks-IT/sage-brain-infra) biomedical knowledge graph.

Two tabs:
- **Ask a question** — natural-language interface backed by the Bedrock Strands AI agent (`POST /ask`)
- **SPARQL** — direct query editor that hits the Neptune read API (`POST /query`)

API endpoints are configured via the sidebar (or environment variables).

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Then open [http://localhost:8501](http://localhost:8501) and paste the API URLs from CDK outputs into the sidebar.

## Getting the API URLs

```bash
# Agent endpoint
aws --profile sagebrain cloudformation describe-stacks \
  --stack-name app-dev-neptune-agent \
  --query "Stacks[0].Outputs[?OutputKey=='AgentApiUrl'].OutputValue" \
  --output text

# SPARQL endpoint
aws --profile sagebrain cloudformation describe-stacks \
  --stack-name app-dev-neptune-api \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
  --output text
```

## Environment variables (optional)

You can pre-populate the sidebar fields by setting:

```bash
export ASK_URL="https://….execute-api.us-east-1.amazonaws.com/prod/ask"
export QUERY_URL="https://….execute-api.us-east-1.amazonaws.com/prod/query"
streamlit run app.py
```

## Deploying to Streamlit Community Cloud

1. Push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect the repo.
3. Set `ASK_URL` and `QUERY_URL` as **Secrets** in the app settings (they'll be injected as environment variables at runtime).
4. Deploy — no other configuration needed.
