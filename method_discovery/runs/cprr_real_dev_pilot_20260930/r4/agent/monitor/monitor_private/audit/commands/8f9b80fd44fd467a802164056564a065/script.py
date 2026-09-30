
import os
import json

# Explore key directories
dirs_to_check = [
    '/app/pkg/streaming',
    '/app/pkg/endpoint',
    '/app/pkg/endpoint/cep',
    '/app/pkg/endpoint/sep',
    '/app/client',
    '/app/pkg/remote/codec/thrift',
    '/app/pkg/remote/trans/nphttp2',
    '/app/transport'
]

results = {}
for d in dirs_to_check:
    if os.path.exists(d):
        files = os.listdir(d)
        results[d] = files
    else:
        results[d] = "NOT EXISTS"

print(json.dumps(results, indent=2))
