
import os

# Check what was created for Target 2
target2_paths = [
    '/app/pkg/endpoint/cep',
    '/app/pkg/endpoint/sep',
    '/app/pkg/endpoint/deprecated.go'
]

print("=== Target 2 Package Status ===")
for path in target2_paths:
    if os.path.exists(path):
        if os.path.isdir(path):
            files = [f for f in os.listdir(path) if f.endswith('.go')]
            print(f"{path}: EXISTS - {len(files)} files: {files}")
        else:
            print(f"{path}: EXISTS (file)")
    else:
        print(f"{path}: MISSING")

# Check endpoint.go for UnaryEndpoint additions
print("\n=== Checking pkg/endpoint/endpoint.go ===")
with open('/app/pkg/endpoint/endpoint.go', 'r') as f:
    content = f.read()
    has_unary_endpoint = 'type UnaryEndpoint' in content
    has_unary_middleware = 'type UnaryMiddleware' in content
    has_to_middleware = 'ToMiddleware()' in content
    print(f"Has UnaryEndpoint type: {has_unary_endpoint}")
    print(f"Has UnaryMiddleware type: {has_unary_middleware}")
    print(f"Has ToMiddleware() method: {has_to_middleware}")
