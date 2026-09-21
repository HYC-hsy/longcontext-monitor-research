def normalize_key(value: str) -> str:
    return value.strip(" ").lower()

def bounded_increment(value: int, limit: int) -> int:
    return min(value + 1, limit)
