
import os
import json

# Find key directories mentioned in the task
paths_to_check = [
    '/app/pkg/streaming',
    '/app/pkg/endpoint',
    '/app/pkg/endpoint/cep',
    '/app/pkg/endpoint/sep',
    '/app/transport',
    '/app/pkg/transport',
    '/app/client',
    '/app/pkg/client',
    '/app/pkg/remote/codec/thrift',
    '/app/pkg/remote/trans/nphttp2'
]

results = {}
for path in paths_to_check:
    if os.path.exists(path):
        files = []
        for f in os.listdir(path):
            if f.endswith('.go'):
                files.append(f)
        results[path] = {'exists': True, 'go_files': sorted(files)[:10]}  # First 10 files
    else:
        results[path] = {'exists': False}

print(json.dumps(results, indent=2))
