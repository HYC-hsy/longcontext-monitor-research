
import os
import json

# Check for key directories mentioned in the task
directories_to_check = [
    "/app/pkg/streaming",
    "/app/pkg/endpoint",
    "/app/pkg/endpoint/cep",
    "/app/pkg/endpoint/sep",
    "/app/transport",
    "/app/client",
    "/app/pkg/remote/codec/thrift",
    "/app/pkg/remote/trans/nphttp2",
]

results = {}
for d in directories_to_check:
    results[d] = {
        "exists": os.path.exists(d),
        "is_dir": os.path.isdir(d) if os.path.exists(d) else False,
        "files": []
    }
    if os.path.isdir(d):
        try:
            files = [f for f in os.listdir(d) if f.endswith('.go')]
            results[d]["files"] = files[:10]  # First 10 .go files
        except:
            pass

print(json.dumps(results, indent=2))
