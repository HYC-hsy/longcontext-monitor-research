def valid_name(value):
    return bool(value and value.strip()) and len(value) < 1000
