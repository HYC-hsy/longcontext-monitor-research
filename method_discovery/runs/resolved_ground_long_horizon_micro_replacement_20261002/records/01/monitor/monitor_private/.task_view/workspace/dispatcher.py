from wiring import resolve

def handle(path):
    handler = resolve(path)
    return handler()
