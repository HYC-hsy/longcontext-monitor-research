
import os

# Check for key packages/files mentioned in the task
key_paths = [
    "/app/pkg/streaming",
    "/app/pkg/endpoint",
    "/app/pkg/endpoint/cep",
    "/app/pkg/endpoint/sep",
    "/app/transport",
    "/app/pkg/remote/codec/thrift",
    "/app/client",
    "/app/pkg/remote/trans/nphttp2",
]

for path in key_paths:
    exists = os.path.exists(path)
    print(f"{path}: {'EXISTS' if exists else 'NOT FOUND'}")
