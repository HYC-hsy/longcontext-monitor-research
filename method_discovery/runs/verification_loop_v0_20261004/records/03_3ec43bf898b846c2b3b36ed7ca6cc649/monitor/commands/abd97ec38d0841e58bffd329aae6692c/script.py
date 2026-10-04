
import os
import json

# Check key directories mentioned in the requirements
key_dirs = [
    "/app/pkg/streaming",
    "/app/pkg/endpoint",
    "/app/pkg/endpoint/cep",
    "/app/pkg/endpoint/sep",
    "/app/transport",
    "/app/pkg/remote/codec/thrift",
    "/app/client",
    "/app/pkg/remote/trans/nphttp2"
]

results = {}
for dir_path in key_dirs:
    exists = os.path.exists(dir_path)
    results[dir_path] = {
        "exists": exists,
        "files": []
    }
    if exists and os.path.isdir(dir_path):
        try:
            files = [f for f in os.listdir(dir_path) if f.endswith('.go')]
            results[dir_path]["files"] = sorted(files)[:10]  # First 10 files
        except Exception as e:
            results[dir_path]["error"] = str(e)

print(json.dumps(results, indent=2))
