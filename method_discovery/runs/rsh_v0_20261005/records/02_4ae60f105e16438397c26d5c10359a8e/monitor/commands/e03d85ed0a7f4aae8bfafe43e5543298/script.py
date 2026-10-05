
# Check if NewAllStrings has been fixed
import os

all_go = '/app/data/validation/all.go'
string_go = '/app/data/validation/string.go'

print("=== NewAllStrings Implementation Status ===")
print(f"all.go exists: {os.path.exists(all_go)}")
print(f"string.go exists: {os.path.exists(string_go)}")

if os.path.exists(all_go):
    print("\n=== Content of all.go ===")
    with open(all_go, 'r') as f:
        print(f.read()[:500])
