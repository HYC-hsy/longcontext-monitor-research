
import os
import json

# Find key packages
key_dirs = [
    '/app/pkg/streaming',
    '/app/pkg/endpoint',
    '/app/pkg/endpoint/cep',
    '/app/pkg/endpoint/sep',
    '/app/pkg/remote/codec/thrift',
    '/app/pkg/remote/trans/nphttp2',
    '/app/client',
    '/app/transport'
]

result = {}
for d in key_dirs:
    result[d] = os.path.isdir(d)

print(json.dumps(result, indent=2))
