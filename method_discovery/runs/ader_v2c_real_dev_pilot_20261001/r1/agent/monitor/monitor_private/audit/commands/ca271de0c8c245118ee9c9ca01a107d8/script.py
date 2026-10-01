
# Check for existence of key files mentioned in requirements
files_to_check = [
    "/app/app/meta.go",
    "/app/theme/json.go",
    "/app/data/binding/sprintf.go",
    "/app/widget/toolbar.go",
    "/app/widget/hyperlink.go",
    "/app/widget/entry.go",
    "/app/data/validation/all.go",
    "/app/driver/desktop/app.go"
]

import os
for f in files_to_check:
    exists = "EXISTS" if os.path.exists(f) else "NOT FOUND"
    print(f"{exists}: {f}")
