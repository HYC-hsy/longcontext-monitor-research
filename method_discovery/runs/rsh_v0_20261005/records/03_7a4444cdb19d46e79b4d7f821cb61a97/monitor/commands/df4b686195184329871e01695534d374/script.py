
import os
import json

# Check Target 2 files exist
base = "/app"
target2_files = [
    "pkg/endpoint/cep/endpoint.go",
    "pkg/endpoint/sep/endpoint.go",
    "pkg/endpoint/deprecated.go",
    "pkg/endpoint/endpoint.go"
]

results = {}
for path in target2_files:
    full_path = os.path.join(base, path)
    results[path] = os.path.exists(full_path)

print("Target 2 File Existence Check:")
print(json.dumps(results, indent=2))

# Quick grep for critical requirements
import subprocess

critical_checks = {
    "cep.EqualsTo_on_StreamRecvEndpoint": "grep -n 'func.*StreamRecvEndpoint.*EqualsTo' /app/pkg/endpoint/cep/endpoint.go",
    "cep.EqualsTo_on_StreamSendEndpoint": "grep -n 'func.*StreamSendEndpoint.*EqualsTo' /app/pkg/endpoint/cep/endpoint.go",
    "cep.DummyDummyMiddleware": "grep -n 'DummyDummyMiddleware' /app/pkg/endpoint/cep/endpoint.go",
    "deprecated.RecvEndpoint": "grep -n 'type RecvEndpoint' /app/pkg/endpoint/deprecated.go",
    "endpoint.UnaryEndpoint": "grep -n 'type UnaryEndpoint' /app/pkg/endpoint/endpoint.go"
}

print("\nCritical Requirement Checks:")
for name, cmd in critical_checks.items():
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            print(f"✓ {name}: FOUND")
        else:
            print(f"✗ {name}: NOT FOUND")
    except:
        print(f"? {name}: ERROR checking")
