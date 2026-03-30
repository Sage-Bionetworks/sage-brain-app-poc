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

        # --- Step 2: poll for result, streaming steps live inside st.status ---
        poll_url = f"{ask_url.rstrip('/')}/{job_id}"
        data: dict | None = None
        prev_step_count = 0

        with st.status("Agent is thinking…", expanded=True) as status_widget:
            for i in range(1, MAX_POLLS + 1):
                time.sleep(POLL_INTERVAL)
                result: dict | None = None
                try:
                    poll_resp = requests.get(poll_url, timeout=30)
                    poll_resp.raise_for_status()
                    result = poll_resp.json()
                except Exception as exc:
                    status_widget.update(label="Polling failed", state="error")
                    st.error(f"Polling failed: {exc}")
                    st.stop()

                steps = result.get("steps", []) if result else []
                for j in range(prev_step_count, len(steps)):
                    step = steps[j]
                    kind = step.get("type", "")
                    tool = step.get("tool", "")
                    if kind == "tool_call":
                        st.markdown(f"**Step {j + 1} — tool call:** `{tool}`")
                        st.code(step.get("sparql", ""), language="sparql")
                    elif kind == "tool_result":
                        st.markdown(f"**Step {j + 1} — result:** `{tool}`")
                        st.code(step.get("preview", ""), language="json")
                    else:
                        st.json(step)
                prev_step_count = len(steps)

                detail = result.get("status_detail", "") if result else ""
                label = detail or f"Agent is thinking… ({i * POLL_INTERVAL}s elapsed)"
                if prev_step_count:
                    label += f" — {prev_step_count} steps"
                status_widget.update(label=label)

                if result is not None and result.get("status") in ("complete", "error"):
                    data = result
                    break

            if data is None:
                status_widget.update(label="Timed out", state="error")
                st.error(f"Timed out after {MAX_POLLS * POLL_INTERVAL}s. The job may still be running.")
                st.stop()
            elif data.get("status") == "error":
                status_widget.update(label="Agent error", state="error")
                st.error(f"Agent error: {data.get('error', 'unknown error')}")
                st.stop()
            else:
                status_widget.update(
                    label=f"Done — {prev_step_count} steps",
                    state="complete",
                    expanded=False,
                )

        if data:
            st.markdown("### Answer")
            st.write(data.get("answer", "*(no answer)*"))

if not ask_url:
    st.info("Set the `ASK_URL` environment variable to enable this.")
