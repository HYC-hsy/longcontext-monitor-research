
import os
import json

# Check for key directories and files mentioned in the task
paths_to_check = [
    "/app/pkg/streaming",
    "/app/pkg/endpoint",
    "/app/pkg/endpoint/cep",
    "/app/pkg/endpoint/sep",
    "/app/transport",
    "/app/pkg/remote/codec/thrift",
    "/app/client",
    "/app/pkg/remote/trans/nphttp2",
    "/app/pkg/remote/trans/nphttp2/grpc/grpcframe"
]

results = {}
for path in paths_to_check:
    if os.path.exists(path):
        if os.path.isdir(path):
            files = os.listdir(path)
            results[path] = {"exists": True, "is_dir": True, "files": files[:10]}
        else:
            results[path] = {"exists": True, "is_dir": False}
    else:
        results[path] = {"exists": False}

print(json.dumps(results, indent=2))
