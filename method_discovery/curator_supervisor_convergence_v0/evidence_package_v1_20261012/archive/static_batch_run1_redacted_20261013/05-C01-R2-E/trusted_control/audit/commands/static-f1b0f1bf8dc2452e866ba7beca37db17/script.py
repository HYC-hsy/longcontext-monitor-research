
# Search for SetMinRowsVisible method in entry.go
import re
with open(r"E:\fyne_evidence_static_batch_20261012_run1\05-C01-R2-E\app\widget\entry.go", 'r', encoding='utf-8') as f:
    content = f.read()
    
# Find SetMinRowsVisible method
pattern = r'func \(e \*Entry\) SetMinRowsVisible.*?\n.*?\n.*?\n.*?\n}'
matches = re.findall(pattern, content, re.DOTALL)
if matches:
    print("Found SetMinRowsVisible method:")
    print(matches[0][:500])
else:
    print("SetMinRowsVisible method NOT FOUND in Entry")
    
# Check if minRowsVisible field exists
if 'minRowsVisible int' in content:
    print("\n✓ minRowsVisible field exists in Entry struct")
else:
    print("\n✗ minRowsVisible field NOT found in Entry struct")
