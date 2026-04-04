import requests
import os
from dotenv import load_dotenv
import re
import json

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_MODEL_CANDIDATES = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash"]


class ExtractionServiceError(Exception):
    pass


def _model_candidates():
    explicit_model = os.getenv("GEMINI_MODEL", "").strip()
    if explicit_model:
        return [explicit_model]

    configured = os.getenv("GEMINI_MODEL_CANDIDATES", "").strip()
    if configured:
        models = [m.strip() for m in configured.split(",") if m.strip()]
        if models:
            return models

    return DEFAULT_MODEL_CANDIDATES


def call_gemini(prompt):
    if not API_KEY:
        raise ExtractionServiceError("GEMINI_API_KEY is not set.")

    headers = {"Content-Type": "application/json"}

    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    attempted = []
    last_error = None

    for model_name in _model_candidates():
        attempted.append(model_name)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={API_KEY}"

        try:
            response = requests.post(url, headers=headers, json=data, timeout=60)
            payload = response.json()

            if response.status_code >= 400:
                message = payload.get("error", {}).get("message", "Gemini API request failed")
                last_error = f"{model_name}: {message}"
                # Try next model if this one is unavailable, quota-limited, or temporarily failing.
                if response.status_code in {400, 403, 404, 429, 500, 502, 503}:
                    continue
                raise ExtractionServiceError(last_error)

            if "error" in payload:
                message = payload.get("error", {}).get("message", "Gemini API returned an error")
                last_error = f"{model_name}: {message}"
                continue

            return payload
        except requests.RequestException as e:
            last_error = f"{model_name}: network error: {e}"
            continue
        except ValueError:
            last_error = f"{model_name}: invalid JSON response from API"
            continue

    attempted_text = ", ".join(attempted) if attempted else "none"
    raise ExtractionServiceError(
        f"Gemini request failed for models [{attempted_text}]. Last error: {last_error or 'unknown error'}"
    )


def clean_json_response(text):
    # remove markdown wrappers like ```json ```
    text = re.sub(r"```json|```", "", text).strip()
    return text


def safe_json_load(text):
    try:
        return json.loads(text)
    except Exception as e:
        raise ExtractionServiceError(f"Invalid JSON from Gemini: {e}")


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
    except Exception as e:
        raise ExtractionServiceError(f"Unexpected Gemini response format: {e}")

    cleaned = clean_json_response(raw_text)

    print("\n🧹 CLEANED TEXT:\n", cleaned)  # DEBUG

    parsed = safe_json_load(cleaned)
    if not isinstance(parsed, list):
        raise ExtractionServiceError("Gemini returned non-list JSON for extraction output.")

    print("\n✅ PARSED OUTPUT:\n", parsed)  # DEBUG

    return parsed
