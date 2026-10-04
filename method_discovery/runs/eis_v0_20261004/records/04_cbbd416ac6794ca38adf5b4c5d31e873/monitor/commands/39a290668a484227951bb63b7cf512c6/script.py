
import os
import json

# Check for the key directories mentioned in the task
key_paths = [
    '/app/pkg/streaming',
    '/app/pkg/endpoint',
    '/app/pkg/endpoint/cep',
    '/app/pkg/endpoint/sep',
    '/app/transport',
    '/app/pkg/remote/codec/thrift',
    '/app/client',
    '/app/pkg/remote/trans/nphttp2'
]

results = {}
for path in key_paths:
    if os.path.exists(path):
        if os.path.isdir(path):
            files = [f for f in os.listdir(path) if f.endswith('.go')]
            results[path] = {'exists': True, 'is_dir': True, 'files': files[:10]}
        else:
            results[path] = {'exists': True, 'is_dir': False}
    else:
        results[path] = {'exists': False}

print(json.dumps(results, indent=2))
