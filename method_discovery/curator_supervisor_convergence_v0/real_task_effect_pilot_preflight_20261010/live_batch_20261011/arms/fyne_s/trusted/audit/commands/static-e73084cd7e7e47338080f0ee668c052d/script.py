
# Search for tap/click handling in Hyperlink
import subprocess

# Search for all methods on Hyperlink
result = subprocess.run(
    ['grep', '-n', 'func.*Hyperlink', '/app/widget/hyperlink.go'],
    capture_output=True, text=True
)
print("=== Hyperlink methods ===")
print(result.stdout)

# Search for Tapped, MouseDown, or other interaction methods
result = subprocess.run(
    ['grep', '-n', '-E', 'func.*Tapped|MouseDown|MouseIn|MouseMoved|Clicked', '/app/widget/hyperlink.go'],
    capture_output=True, text=True
)
print("\n=== Interaction methods ===")
print(result.stdout if result.stdout else "None found")

# Check if there's a renderer file
import os
files = [f for f in os.listdir('/app/widget') if 'hyperlink' in f]
print(f"\n=== Hyperlink-related files ===")
print(files)
