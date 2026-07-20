"""
llm_connection.py

Talks to the Groq API and returns the reply.
The full prompt is built on the caller side using prompts.py, which
already contains the base role and the guard, so this file just sends
that prompt through as is.

Reads the API key from Streamlit secrets first (for Streamlit Cloud),
falling back to the local environment variable so this still works
unchanged when running locally with `streamlit run app.py`.
"""

import os
import json
import requests
import streamlit as st

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.3-70b-versatile"


def get_api_key():
    try:
        return st.secrets["GROQ_API_KEY"]
    except Exception:
        return os.environ.get("GROQ_API_KEY")


def get_time_range_snapshot(records, start_time, end_time):
    return [
        record for record in records
        if start_time <= record.get("timestamp", float("-inf")) <= end_time
    ]


def ask_coach(prompt, context_data=""):
    api_key = get_api_key()
    if not api_key:
        return "Error: GROQ_API_KEY is not set. Add it in Streamlit secrets (cloud) or your local environment (running locally)."

    if context_data and not isinstance(context_data, str):
        context_data = json.dumps(context_data, indent=2)

    user_content = prompt
    if context_data:
        user_content = f"{prompt}\n\nExtra data:\n{context_data}"

    request_body = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "user", "content": user_content},
        ],
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        response = requests.post(
            GROQ_ENDPOINT, headers=headers, json=request_body, timeout=30
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if choices:
            return choices[0]["message"]["content"]
        return "Error: No response from model."
    except requests.exceptions.HTTPError as e:
        return f"Error: {e}\n{response.text}"
    except requests.exceptions.RequestException as e:
        return f"Error: {e}"