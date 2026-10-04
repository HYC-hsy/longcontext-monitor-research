
import os
import json

# Check for key directories and files
paths_to_check = [
    '/app/pkg/streaming',
    '/app/pkg/endpoint',
    '/app/pkg/endpoint/cep',
    '/app/pkg/endpoint/sep',
    '/app/pkg/remote/codec/thrift',
    '/app/pkg/remote/trans/nphttp2',
    '/app/transport',
    '/app/client',
]

results = {}
for path in paths_to_check:
    if os.path.exists(path):
        if os.path.isdir(path):
            files = os.listdir(path)
            results[path] = {'exists': True, 'type': 'directory', 'contents': files}
        else:
            results[path] = {'exists': True, 'type': 'file'}
    else:
        results[path] = {'exists': False}

print(json.dumps(results, indent=2))
