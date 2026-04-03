def normalize_data(data):
    import json

    try:
        parsed = json.loads(data)
    except:
        return []

    cleaned = []

    for item in parsed:
        item['component'] = item.get('component', '').lower()
        item['type'] = item.get('type', '').capitalize()

        # simple unit normalization
        if item.get('unit', '').lower() == 'mb':
            try:
                item['value'] = float(item['value']) / 1024
                item['unit'] = 'GB'
            except:
                pass

        cleaned.append(item)

    return cleaned
