def run(input_data):
    name = str((input_data or {}).get("name", "world"))
    return {"result": f"ok:{name}"}
