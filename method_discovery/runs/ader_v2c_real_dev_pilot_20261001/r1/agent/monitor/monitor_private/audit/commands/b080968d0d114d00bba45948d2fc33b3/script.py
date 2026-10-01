
# Check if key files exist at required paths
files_to_check = [
    "/app/app/meta.go",  # Target 1
    "/app/theme/json.go",  # Target 2
    "/app/data/binding/sprintf.go",  # Target 3
    "/app/data/validation/strings.go",  # Target 6
    "/app/driver/desktop/app.go"  # Target 7
]

import os
for f in files_to_check:
    exists = "✓" if os.path.exists(f) else "✗"
    print(f"{exists} {f}")
