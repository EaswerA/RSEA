import json


def normalize_data(data):
    if isinstance(data, list):
        parsed = data
    elif isinstance(data, str):
        try:
            parsed = json.loads(data)
        except Exception:
            return []
    else:
        return []

    cleaned = []

    for item in parsed:
        if not isinstance(item, dict):
            continue

        normalized_item = dict(item)
        normalized_item['component'] = str(normalized_item.get('component', '')).lower()
        normalized_item['type'] = str(normalized_item.get('type', '')).capitalize()

        # simple unit normalization
        if str(normalized_item.get('unit', '')).lower() == 'mb':
            try:
                normalized_item['value'] = float(normalized_item.get('value', 0)) / 1024
                normalized_item['unit'] = 'GB'
            except Exception:
                pass

        cleaned.append(normalized_item)

    return cleaned
