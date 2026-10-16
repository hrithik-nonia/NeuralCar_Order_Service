import uuid

def generate_order_id() -> str:
    unique = uuid.uuid4().hex[:8].upper()
    return f"NC{unique}"
    