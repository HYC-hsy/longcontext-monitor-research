
import os
import json

# Check workspace structure
key_paths = [
    "/app/app.go",
    "/app/menu.go", 
    "/app/container.go",
    "/app/theme",
    "/app/data/binding",
    "/app/data/validation",
    "/app/widget/toolbar.go",
    "/app/widget/hyperlink.go",
    "/app/widget/entry.go",
    "/app/driver/desktop"
]

results = {}
for path in key_paths:
    if os.path.exists(path):
        if os.path.isdir(path):
            files = os.listdir(path)
            results[path] = f"DIR: {len(files)} files"
        else:
            results[path] = "FILE exists"
    else:
        results[path] = "MISSING"

print(json.dumps(results, indent=2))
