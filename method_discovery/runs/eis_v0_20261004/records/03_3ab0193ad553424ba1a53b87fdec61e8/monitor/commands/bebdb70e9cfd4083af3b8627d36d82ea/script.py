
import os
import json

# Check what was created for Target 2
directories = [
    "/app/pkg/endpoint/cep",
    "/app/pkg/endpoint/sep",
    "/app/pkg/endpoint"
]

results = {}
for d in directories:
    if os.path.exists(d):
        files = [f for f in os.listdir(d) if f.endswith('.go')]
        results[d] = files
    else:
        results[d] = "NOT FOUND"

print(json.dumps(results, indent=2))
