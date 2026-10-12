
# Check for SetMinRowsVisible method in entry.go
import os

workspace = r"task/workspace"
entry_path = os.path.join(workspace, "widget", "entry.go")

with open(entry_path, 'r', encoding='utf-8') as f:
    content = f.read()
    
if 'SetMinRowsVisible' in content:
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'SetMinRowsVisible' in line:
            print(f"Line {i+1}: {line}")
            start = max(0, i-2)
            end = min(len(lines), i+10)
            print("\nContext:")
            for j in range(start, end):
                print(f"{j+1}: {lines[j]}")
            print("\n" + "="*80 + "\n")
else:
    print("❌ SetMinRowsVisible method NOT FOUND in entry.go")
    print("Only the field 'minRowsVisible' was added, but the public method is missing")
