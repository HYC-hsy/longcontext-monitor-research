
import os
import json

# Check key directories mentioned in the task
base = "/app"
key_paths = [
    "pkg/streaming",
    "pkg/endpoint",
    "pkg/endpoint/cep",
    "pkg/endpoint/sep",
    "transport",
    "pkg/remote/codec/thrift",
    "client",
    "pkg/remote/trans/nphttp2"
]

results = {}
for path in key_paths:
    full_path = os.path.join(base, path)
    if os.path.exists(full_path):
        if os.path.isdir(full_path):
            files = [f for f in os.listdir(full_path) if f.endswith('.go')]
            results[path] = {"exists": True, "type": "directory", "go_files": files[:10]}
        else:
            results[path] = {"exists": True, "type": "file"}
    else:
        results[path] = {"exists": False}

print(json.dumps(results, indent=2))
