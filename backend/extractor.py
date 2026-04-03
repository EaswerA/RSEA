import requests
import os
from dotenv import load_dotenv
import re
import json

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")


class ExtractionServiceError(Exception):
    pass


def _local_extract_requirements(chunk):
    hardware_keywords = {
        "cpu": "cpu",
        "processor": "cpu",
        "ram": "ram",
        "memory": "ram",
        "storage": "storage",
        "ssd": "storage",
        "hdd": "storage",
        "server": "server",
        "switch": "network",
        "router": "network",
        "firewall appliance": "network",
    }

    software_keywords = {
        "windows": "os",
        "linux": "os",
        "ubuntu": "os",
        "red hat": "os",
        "firewall": "firewall",
        "antivirus": "security",
        "authentication": "authentication",
        "access control": "access control",
        "log": "logging",
        "audit": "logging",
        "encryption": "security",
        "ssl": "security",
        "tls": "security",
    }

    value_unit_pattern = re.compile(r"(\d+(?:\.\d+)?)\s*(tb|gb|mb|kb|ghz|mhz|cores?)", re.IGNORECASE)

    items = []
    seen = set()
    lines = re.split(r"[\n\r\.]+", chunk)

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        lower_line = line.lower()
        matched = False

        for keyword, component in hardware_keywords.items():
            if keyword in lower_line:
                value = ""
                unit = ""
                match = value_unit_pattern.search(line)
                if match:
                    value = match.group(1)
                    unit = match.group(2).upper()

                key = ("Hardware", component, line)
                if key not in seen:
                    seen.add(key)
                    items.append({
                        "type": "Hardware",
                        "component": component,
                        "value": value,
                        "unit": unit,
                        "description": line,
                        "confidence": 0.35,
                    })
                matched = True
                break

        if matched:
            continue

        for keyword, component in software_keywords.items():
            if keyword in lower_line:
                key = ("Software", component, line)
                if key not in seen:
                    seen.add(key)
                    items.append({
                        "type": "Software",
                        "component": component,
                        "value": "",
                        "unit": "",
                        "description": line,
                        "confidence": 0.35,
                    })
                break

    return items


def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"
    headers = {"Content-Type": "application/json"}

    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        payload = response.json()

        if response.status_code >= 400:
            message = payload.get("error", {}).get("message", "Gemini API request failed")
            raise ExtractionServiceError(message)

        if "error" in payload:
            message = payload.get("error", {}).get("message", "Gemini API returned an error")
            raise ExtractionServiceError(message)

        return payload
    except ExtractionServiceError:
        raise
    except Exception as e:
        raise ExtractionServiceError(f"Gemini request failed: {e}")


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

    fallback_enabled = os.getenv("ALLOW_LOCAL_FALLBACK", "1") in {"1", "true", "True", "yes", "YES"}

    try:
        response = call_gemini(prompt)
    except ExtractionServiceError as e:
        if fallback_enabled:
            print("GEMINI UNAVAILABLE, USING LOCAL FALLBACK:", e)
            return _local_extract_requirements(chunk)
        raise

    print("\n🔍 RAW GEMINI RESPONSE:\n", response)  # DEBUG

    try:
        raw_text = response['candidates'][0]['content']['parts'][0]['text']
        cleaned = clean_json_response(raw_text)

        print("\n🧹 CLEANED TEXT:\n", cleaned)  # DEBUG

        parsed = safe_json_load(cleaned)

        print("\n✅ PARSED OUTPUT:\n", parsed)  # DEBUG

        return parsed

    except Exception as e:
        if fallback_enabled:
            print("INVALID GEMINI FORMAT, USING LOCAL FALLBACK:", e)
            return _local_extract_requirements(chunk)
        raise ExtractionServiceError(f"Unexpected Gemini response format: {e}")
