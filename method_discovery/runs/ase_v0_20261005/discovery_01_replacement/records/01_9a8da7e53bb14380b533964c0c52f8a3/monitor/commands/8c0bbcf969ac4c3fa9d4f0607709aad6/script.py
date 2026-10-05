
import os
# Check for key directories mentioned in the task
paths_to_check = [
    '/app/pkg/streaming',
    '/app/pkg/endpoint',
    '/app/pkg/endpoint/cep',
    '/app/pkg/endpoint/sep',
    '/app/transport',
    '/app/pkg/transport',
    '/app/pkg/remote/codec/thrift',
    '/app/pkg/remote/trans/nphttp2',
    '/app/client'
]

for path in paths_to_check:
    exists = os.path.exists(path)
    if exists:
        files = os.listdir(path)[:10]  # First 10 files
        print(f"{path}: EXISTS - {len(os.listdir(path))} items, sample: {files}")
    else:
        print(f"{path}: NOT FOUND")
