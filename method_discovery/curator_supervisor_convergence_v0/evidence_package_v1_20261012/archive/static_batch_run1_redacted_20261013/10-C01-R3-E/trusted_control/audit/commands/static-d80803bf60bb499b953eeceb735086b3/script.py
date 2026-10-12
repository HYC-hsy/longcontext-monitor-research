
import os

# Check specific files mentioned in the spec
workspace = "E:\\fyne_evidence_static_batch_20261012_run1\\10-C01-R3-E\\app"

check_files = [
    "app.go",
    "menu.go", 
    "container.go",
    "app/meta.go",
    "app/app.go",
    "theme/json.go",
    "data/binding/sprintf.go",
    "data/validation/all.go",
    "widget/entry.go",
    "widget/hyperlink.go",
    "widget/toolbar.go",
    "widget/select.go",
    "driver/desktop/app.go"
]

print("File existence check:")
for file in check_files:
    full_path = os.path.join(workspace, file)
    exists = os.path.exists(full_path)
    print(f"{'✓' if exists else '✗'} {file}")
