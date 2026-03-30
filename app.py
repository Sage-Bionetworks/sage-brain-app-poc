"""Sage Brain — Streamlit POC

Talks to the agent API endpoint deployed by sage-brain-infra:
  - POST /ask   — natural-language agent (Bedrock Strands + Claude Sonnet 4.6)

Set the API URL via environment variable or the sidebar.
"""

import os

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_ASK_URL = os.environ.get("ASK_URL", "")

st.set_page_config(page_title="Sage Brain", page_icon="🧠", layout="wide")
st.title("🧠 Sage Brain")
st.caption("Biomedical knowledge graph explorer powered by Amazon Neptune + Claude Sonnet 4.6")

# ---------------------------------------------------------------------------
# Sidebar — endpoint configuration
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("API Endpoint")
    ask_url = st.text_input(
        "Agent URL (POST /ask)",
        value=DEFAULT_ASK_URL,
        placeholder="https://….execute-api.us-east-1.amazonaws.com/prod/ask",
    )
    st.caption("Get this value from CDK output: `AgentApiUrl`.")

# ---------------------------------------------------------------------------
# Ask interface
# ---------------------------------------------------------------------------

st.subheader("Natural-language query")
question = st.text_area(
    "Question",
    placeholder="What types of biological entities are in this knowledge graph?",
    height=80,
)

if st.button("Ask", type="primary", disabled=not ask_url):
    if not question.strip():
        st.warning("Enter a question first.")
    else:
        with st.spinner("Thinking…"):
            try:
                resp = requests.post(
                    ask_url,
                    json={"question": question.strip()},
                    timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.exceptions.Timeout:
                st.error("Request timed out (>60 s). The agent may still be running.")
                st.stop()
            except Exception as exc:
                st.error(f"Request failed: {exc}")
                st.stop()

        st.markdown("### Answer")
        st.write(data.get("answer", "*(no answer)*"))

        steps = data.get("steps", [])
        if steps:
            with st.expander(f"Reasoning trace ({len(steps)} steps)"):
                for i, step in enumerate(steps, 1):
                    kind = step.get("type", "")
                    tool = step.get("tool", "")
                    if kind == "tool_call":
                        st.markdown(f"**Step {i} — tool call:** `{tool}`")
                        st.code(step.get("sparql", ""), language="sparql")
                    elif kind == "tool_result":
                        st.markdown(f"**Step {i} — result from:** `{tool}`")
                        st.code(step.get("preview", ""), language="json")
                    else:
                        st.json(step)

if not ask_url:
    st.info("Set the **Agent URL** in the sidebar to enable this.")
