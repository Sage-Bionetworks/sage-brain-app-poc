"""Sage Brain — Streamlit POC

Talks to the agent API endpoint deployed by sage-brain-infra:
  - POST /ask          — submit question, returns {"job_id": "..."}
  - GET  /ask/{job_id} — poll until status == "complete" | "error"

Set the API URL via environment variable or the sidebar.
"""

import os
import time

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_ASK_URL = os.environ.get("ASK_URL", "")

st.set_page_config(page_title="Sage Brain", page_icon="🧠", layout="wide")
st.title("🧠 Sage Brain")
st.caption("Biomedical knowledge graph explorer powered by Amazon Neptune + Claude Sonnet 4.6")

ask_url = DEFAULT_ASK_URL

# ---------------------------------------------------------------------------
# Ask interface
# ---------------------------------------------------------------------------

st.subheader("Natural-language query")
question = st.text_area(
    "Question",
    placeholder="What types of biological entities are in this knowledge graph?",
    height=80,
)

POLL_INTERVAL = 5   # seconds between status checks
MAX_POLLS     = 60  # 5 minutes total

if st.button("Ask", type="primary", disabled=not ask_url):
    if not question.strip():
        st.warning("Enter a question first.")
    else:
        # --- Step 1: submit job ---
        job_id: str | None = None
        try:
            resp = requests.post(
                ask_url,
                json={"question": question.strip()},
                timeout=30,
            )
            resp.raise_for_status()
            job_id = resp.json()["job_id"]
        except Exception as exc:
            st.error(f"Failed to submit question: {exc}")
            st.stop()

        # --- Step 2: poll for result ---
        poll_url = f"{ask_url.rstrip('/')}/{job_id}"
        status_text = st.empty()
        data: dict | None = None
        for i in range(1, MAX_POLLS + 1):
            status_text.info(f"Waiting for answer… ({i * POLL_INTERVAL}s elapsed)")
            time.sleep(POLL_INTERVAL)
            result: dict | None = None
            try:
                poll_resp = requests.get(poll_url, timeout=30)
                poll_resp.raise_for_status()
                result = poll_resp.json()
            except Exception as exc:
                status_text.empty()
                st.error(f"Polling failed: {exc}")
                st.stop()

            if result is not None and result.get("status") in ("complete", "error"):
                data = result
                break

        status_text.empty()

        if data is None:
            st.error(f"Timed out after {MAX_POLLS * POLL_INTERVAL}s. The job may still be running.")
            st.stop()
        elif data.get("status") == "error":
            st.error(f"Agent error: {data.get('error', 'unknown error')}")
            st.stop()
        else:
            st.markdown("### Answer")
            st.write(data.get("answer", "*(no answer)*"))

        steps = data.get("steps", []) if data else []
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
    st.info("Set the `ASK_URL` environment variable to enable this.")
