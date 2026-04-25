"""Sage Brain — Streamlit POC

Talks to the agent API endpoint deployed by sage-brain-infra:
  - POST /ask          — submit question, returns {"job_id": "..."}
  - GET  /ask/{job_id} — poll until status == "complete" | "error"

Configure via .streamlit/secrets.toml (copy from secrets.toml.example).
"""

import os
import time
import urllib.parse

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ASK_URL = st.secrets.get("ASK_URL") or os.environ.get("ASK_URL", "")

_oauth        = st.secrets.get("synapse_oauth", {})
CLIENT_ID     = _oauth.get("client_id", "")
CLIENT_SECRET = _oauth.get("client_secret", "")
REDIRECT_URI  = _oauth.get("redirect_uri", "")

SYNAPSE_AUTH_URL     = "https://signin.synapse.org"
SYNAPSE_TOKEN_URL    = "https://repo-prod.prod.sagebase.org/auth/v1/oauth2/token"
SYNAPSE_USERINFO_URL = "https://repo-prod.prod.sagebase.org/auth/v1/oauth2/userinfo"

st.set_page_config(page_title="Sage Brain", page_icon="🧠", layout="wide")

# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------

def _auth_url() -> str:
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "openid profile email",
        "prompt": "select_account",
    }
    return f"{SYNAPSE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def _exchange_code(code: str) -> dict:
    resp = requests.post(
        SYNAPSE_TOKEN_URL,
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI},
        auth=(CLIENT_ID, CLIENT_SECRET),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _fetch_userinfo(access_token: str) -> dict:
    resp = requests.get(
        SYNAPSE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()

# ---------------------------------------------------------------------------
# Handle OAuth callback — Synapse redirects here with ?code=...
# ---------------------------------------------------------------------------

if "code" in st.query_params and "access_token" not in st.session_state:
    try:
        token_data = _exchange_code(st.query_params["code"])
        st.session_state["access_token"] = token_data["access_token"]
        st.session_state["userinfo"] = _fetch_userinfo(token_data["access_token"])
    except Exception as exc:
        st.error(f"Login failed: {exc}")
        st.stop()
    st.query_params.clear()
    st.rerun()

# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------

if "access_token" not in st.session_state:
    st.title("🧠 Sage Brain")
    st.caption("Biomedical knowledge graph explorer powered by Amazon Neptune + Claude Sonnet 4.6")
    st.divider()
    st.info("Sign in with your Synapse account to continue.")
    st.link_button("Sign in with Synapse", _auth_url(), type="primary")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar — user info & logout
# ---------------------------------------------------------------------------

userinfo = st.session_state.get("userinfo", {})

with st.sidebar:
    st.markdown("**Signed in as**")
    display_name = userinfo.get("name") or userinfo.get("email") or userinfo.get("sub", "")
    st.write(display_name)
    if email := userinfo.get("email"):
        if email != display_name:
            st.caption(email)
    if st.button("Sign out"):
        st.session_state.pop("access_token", None)
        st.session_state.pop("userinfo", None)
        st.rerun()

# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------

st.title("🧠 Sage Brain")
st.caption("Biomedical knowledge graph explorer powered by Amazon Neptune + Claude Sonnet 4.6")

_api_headers = {"Authorization": f"Bearer {st.session_state['access_token']}"}

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

if st.button("Ask", type="primary", disabled=not ASK_URL):
    if not question.strip():
        st.warning("Enter a question first.")
    else:
        # --- Step 1: submit job ---
        job_id: str | None = None
        try:
            resp = requests.post(
                ASK_URL,
                json={"question": question.strip()},
                headers=_api_headers,
                timeout=30,
            )
            resp.raise_for_status()
            job_id = resp.json()["job_id"]
        except Exception as exc:
            st.error(f"Failed to submit question: {exc}")
            st.stop()

        # --- Step 2: poll for result, streaming steps live inside st.status ---
        poll_url = f"{ASK_URL.rstrip('/')}/{job_id}"
        data: dict | None = None
        prev_step_count = 0

        with st.status("Agent is thinking…", expanded=True) as status_widget:
            for i in range(1, MAX_POLLS + 1):
                time.sleep(POLL_INTERVAL)
                result: dict | None = None
                try:
                    poll_resp = requests.get(poll_url, headers=_api_headers, timeout=30)
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

if not ASK_URL:
    st.info("Set `ASK_URL` in `.streamlit/secrets.toml` or as an environment variable.")
