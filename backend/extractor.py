import requests
import os
from dotenv import load_dotenv
import re
import json

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")


def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"
    headers = {"Content-Type": "application/json"}

    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        return response.json()
    except Exception as e:
        print("API ERROR:", e)
        return {}


def clean_json_response(text):
    # remove markdown wrappers like ```json ```
    text = re.sub(r"```json|```", "", text).strip()
    return text


def safe_json_load(text):
    try:
        return json.loads(text)
    except Exception as e:
        print("JSON LOAD ERROR:", e)
        print("RAW TEXT:", text)
        return []


def extract_requirements(chunk):
    prompt = f"""
    You are an expert system extracting structured requirements from government tender documents.

    Your job:
    Extract ALL hardware and software requirements from the given text.

    Hardware includes:
    - CPU, RAM, storage, servers, network devices

    Software includes:
    - OS, security, firewall, logs, authentication, access control, protocols

    IMPORTANT:
    - Extract even implicit requirements
    - Be exhaustive (do not miss anything)
    - If a requirement has no numeric value, leave value and unit empty

    STRICT RULES:
    - Return ONLY valid JSON
    - No explanations or text outside JSON
    - If nothing found, return []

    Output format:
    [
      {{
        "type": "Hardware" or "Software",
        "component": "",
        "value": "",
        "unit": "",
        "description": "",
        "confidence": 0.0
      }}
    ]

    Text:
    {chunk}
    """

    response = call_gemini(prompt)

    print("\n🔍 RAW GEMINI RESPONSE:\n", response)  # DEBUG

    try:
        raw_text = response['candidates'][0]['content']['parts'][0]['text']
        cleaned = clean_json_response(raw_text)

        print("\n🧹 CLEANED TEXT:\n", cleaned)  # DEBUG

        parsed = safe_json_load(cleaned)

        print("\n✅ PARSED OUTPUT:\n", parsed)  # DEBUG

        return parsed

    except Exception as e:
        print("EXTRACTION ERROR:", e)
        return []
