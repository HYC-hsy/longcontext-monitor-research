
# Check for all Target 2 requirement 3 items in endpoint.go
with open('/app/pkg/endpoint/endpoint.go', 'r') as f:
    content = f.read()

print("=== Checking Target 2 Requirement 3 Items ===\n")

items_to_check = [
    ("UnaryEndpoint type", "type UnaryEndpoint"),
    ("UnaryMiddleware type", "type UnaryMiddleware"),
    ("UnaryMiddlewareBuilder type", "type UnaryMiddlewareBuilder"),
    ("UnaryChain function", "func UnaryChain"),
    ("ToMiddleware method", "ToMiddleware()"),
    ("ToUnaryMiddleware method", "ToUnaryMiddleware()"),
]

for item_name, search_string in items_to_check:
    present = search_string in content
    status = "✓ PRESENT" if present else "❌ MISSING"
    print(f"{status}: {item_name}")

print("\n=== Content Check ===")
if "type UnaryEndpoint" in content:
    for line in content.split('\n'):
        if 'UnaryEndpoint' in line and 'type' in line:
            print(f"Found: {line.strip()}")
            
if "type UnaryMiddleware" in content:
    for line in content.split('\n'):
        if 'UnaryMiddleware' in line and 'type' in line:
            print(f"Found: {line.strip()}")
