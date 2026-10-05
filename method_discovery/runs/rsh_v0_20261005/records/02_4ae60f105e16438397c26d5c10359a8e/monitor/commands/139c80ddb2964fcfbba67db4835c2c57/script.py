
# Check if all.go exists (the required filename)
import os
all_go_path = '/app/data/validation/all.go'
string_go_path = '/app/data/validation/string.go'

print("all.go exists:", os.path.exists(all_go_path))
print("string.go exists:", os.path.exists(string_go_path))
print("\nExpected file: data/validation/all.go")
print("Actual file: data/validation/string.go" if os.path.exists(string_go_path) else "all.go")
