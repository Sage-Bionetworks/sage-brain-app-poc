"""Sage Brain — Streamlit POC

Talks to two public API endpoints deployed by sage-brain-infra:
  - POST /ask   — natural-language agent (Bedrock Strands + Claude Sonnet 4.6)
  - POST /query — raw SPARQL passthrough

Set API URLs via environment variables or the sidebar.
"""

import os

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_ASK_URL = os.environ.get("ASK_URL", "")
DEFAULT_QUERY_URL = os.environ.get("QUERY_URL", "")

st.set_page_config(page_title="Sage Brain", page_icon="🧠", layout="wide")
st.title("🧠 Sage Brain")
st.caption("Biomedical knowledge graph explorer powered by Amazon Neptune + Claude Sonnet 4.6")

# ---------------------------------------------------------------------------
# Sidebar — endpoint configuration
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("API Endpoints")
    ask_url = st.text_input(
        "Agent URL (POST /ask)",
        value=DEFAULT_ASK_URL,
        placeholder="https://….execute-api.us-east-1.amazonaws.com/prod/ask",
    )
    query_url = st.text_input(
        "SPARQL URL (POST /query)",
        value=DEFAULT_QUERY_URL,
        placeholder="https://….execute-api.us-east-1.amazonaws.com/prod/query",
    )
    st.caption("Get these values from CDK outputs: `AgentApiUrl` and `ApiUrl`.")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_agent, tab_sparql = st.tabs(["Ask a question", "SPARQL"])

# ── Agent tab ──────────────────────────────────────────────────────────────

with tab_agent:
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
        st.info("Set the **Agent URL** in the sidebar to enable this tab.")

# ── SPARQL tab ─────────────────────────────────────────────────────────────

with tab_sparql:
    st.subheader("Direct SPARQL query")

    default_query = """\
SELECT ?type (COUNT(?entity) AS ?count)
WHERE {
  ?entity a ?type .
}
GROUP BY ?type
ORDER BY DESC(?count)
LIMIT 20"""

    sparql = st.text_area("SPARQL", value=default_query, height=200)

    if st.button("Run query", type="primary", disabled=not query_url):
        with st.spinner("Querying Neptune…"):
            try:
                resp = requests.post(
                    query_url,
                    json={"query": sparql},
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.exceptions.Timeout:
                st.error("Request timed out (>30 s).")
                st.stop()
            except Exception as exc:
                st.error(f"Request failed: {exc}")
                st.stop()

        bindings = data.get("results", {}).get("bindings", [])
        if not bindings:
            st.info("Query returned no results.")
        else:
            rows = [{k: v.get("value", "") for k, v in row.items()} for row in bindings]
            st.dataframe(rows, use_container_width=True)
            st.caption(f"{len(rows)} row(s) returned.")

        with st.expander("Raw response"):
            st.json(data)

    if not query_url:
        st.info("Set the **SPARQL URL** in the sidebar to enable this tab.")
