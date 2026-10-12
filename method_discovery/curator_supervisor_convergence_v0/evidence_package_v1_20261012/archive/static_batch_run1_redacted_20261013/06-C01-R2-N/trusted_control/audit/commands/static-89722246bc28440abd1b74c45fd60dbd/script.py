
import os

entry_path = r"E:\fyne_evidence_static_batch_20261012_run1\06-C01-R2-N\app\widget\entry.go"

# Search for SetMinRowsVisible method
with open(entry_path, 'r', encoding='utf-8') as f:
    content = f.read()
    
if 'SetMinRowsVisible' in content:
    # Find the method
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'SetMinRowsVisible' in line:
            print(f"Line {i+1}: {line}")
            # Print context
            start = max(0, i-2)
            end = min(len(lines), i+10)
            print("\nContext:")
            for j in range(start, end):
                print(f"{j+1}: {lines[j]}")
            print("\n" + "="*80 + "\n")
else:
    print("SetMinRowsVisible method NOT FOUND in entry.go")
