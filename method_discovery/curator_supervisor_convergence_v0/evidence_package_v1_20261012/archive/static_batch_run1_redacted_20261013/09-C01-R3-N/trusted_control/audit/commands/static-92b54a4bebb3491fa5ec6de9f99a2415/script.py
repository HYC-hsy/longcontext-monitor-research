
import os
import re

hyperlink_path = os.path.join("task", "workspace", "widget", "hyperlink.go")
with open(hyperlink_path, 'r', encoding='utf-8') as f:
    content = f.read()
    
# Find Tapped method
tapped_match = re.search(r'func \(hl \*Hyperlink\) Tapped\([^)]*\)[^{]*\{[^}]*\}', content, re.DOTALL)
if tapped_match:
    print("=== Hyperlink.Tapped() method ===")
    print(tapped_match.group(0)[:500])
else:
    print("Tapped method not found in Hyperlink")
