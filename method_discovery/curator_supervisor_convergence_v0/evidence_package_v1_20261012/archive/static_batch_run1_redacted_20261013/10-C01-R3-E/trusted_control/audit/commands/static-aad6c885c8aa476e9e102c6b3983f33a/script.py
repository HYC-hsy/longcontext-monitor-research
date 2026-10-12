
# Check which files exist in Target 6
import os

files_to_check = [
    ('task/workspace/widget/entry.go', 'Entry widget'),
    ('task/workspace/widget/hyperlink.go', 'Hyperlink widget'),
    ('task/workspace/widget/select.go', 'Select widget'),
    ('task/workspace/data/validation/all.go', 'NewAllStrings validator'),
    ('task/workspace/driver/desktop/app.go', 'Desktop App interface'),
]

print("File existence check:")
print("=" * 70)
for filepath, description in files_to_check:
    exists = os.path.exists(filepath)
    status = "✓ EXISTS" if exists else "✗ MISSING"
    print(f"{status:12s} - {description:30s} ({filepath})")
