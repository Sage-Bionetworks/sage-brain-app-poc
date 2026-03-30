# sage-brain-app-poc

Streamlit POC for the [Sage Brain](https://github.com/Sage-Bionetworks-IT/sage-brain-infra) biomedical knowledge graph.

Natural-language interface backed by the Bedrock Strands AI agent (`POST /ask`).

The API endpoint is configured via the sidebar (or environment variable).

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Then open [http://localhost:8501](http://localhost:8501) and paste the API URL from CDK outputs into the sidebar.

## Getting the API URL

```bash
aws --profile sagebrain cloudformation describe-stacks \
  --stack-name app-dev-neptune-agent \
  --query "Stacks[0].Outputs[?OutputKey=='AgentApiUrl'].OutputValue" \
  --output text
```

## Environment variable (optional)

You can pre-populate the sidebar by setting:

```bash
export ASK_URL="https://….execute-api.us-east-1.amazonaws.com/prod/ask"
streamlit run app.py
```

## Deploying to Streamlit Community Cloud

1. Push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect the repo.
3. Set `ASK_URL` as a **Secret** in the app settings (it'll be injected as an environment variable at runtime).
4. Deploy — no other configuration needed.
