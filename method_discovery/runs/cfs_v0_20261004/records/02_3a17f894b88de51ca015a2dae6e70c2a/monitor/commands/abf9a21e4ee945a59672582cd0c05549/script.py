
# Check the structure and see if key files mentioned in the task exist
import os
import json

base_path = "/app"
key_paths_to_check = [
    "app.go",           # Target 1: AppMetadata struct
    "menu.go",          # Target 4: MenuItem fields
    "container.go",     # Target 6: Container.RemoveAll
    "app/meta.go",      # Target 1: SetMetadata function
    "theme",            # Target 2: theme package
    "data/binding",     # Target 3: binding package
    "data/validation",  # Target 6: validation package
    "widget/toolbar.go", # Target 5: Toolbar enhancements
    "widget/hyperlink.go", # Target 6: Hyperlink.OnTapped
    "widget/entry.go",  # Target 6: Entry.SetMinRowsVisible
    "driver/desktop",   # Target 7: desktop.App interface
]

results = {}
for path in key_paths_to_check:
    full_path = os.path.join(base_path, path)
    if os.path.exists(full_path):
        if os.path.isdir(full_path):
            results[path] = "directory exists"
        else:
            results[path] = "file exists"
    else:
        results[path] = "does not exist"

print(json.dumps(results, indent=2))
