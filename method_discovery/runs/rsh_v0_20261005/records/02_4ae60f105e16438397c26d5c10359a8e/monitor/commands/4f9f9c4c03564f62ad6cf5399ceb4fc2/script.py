
# Check Target 6 progress - all 5 items
import subprocess

print("=== Target 6: Widget/Container Improvements (5 items) ===\n")

# 1. Container.RemoveAll()
result = subprocess.run(['grep', '-n', 'RemoveAll', '/app/container.go'], 
                       capture_output=True, text=True)
print("1. Container.RemoveAll():", "✓ FOUND" if result.returncode == 0 else "✗ MISSING")
if result.returncode == 0:
    print(result.stdout[:200])

# 2. Container.Add(nil) nil-safe
result = subprocess.run(['grep', '-A', '3', 'func (c \*Container) Add', '/app/container.go'], 
                       capture_output=True, text=True)
print("\n2. Container.Add() nil-safe:", "needs inspection")
if result.returncode == 0:
    print(result.stdout[:300])

# 3. Hyperlink.OnTapped
result = subprocess.run(['grep', '-n', 'OnTapped', '/app/widget/hyperlink.go'], 
                       capture_output=True, text=True)
print("\n3. Hyperlink.OnTapped:", "✓ FOUND" if result.returncode == 0 else "✗ MISSING")
if result.returncode == 0:
    print(result.stdout[:200])

# 4. Entry.SetMinRowsVisible
result = subprocess.run(['grep', '-n', 'SetMinRowsVisible', '/app/widget/entry.go'], 
                       capture_output=True, text=True)
print("\n4. Entry.SetMinRowsVisible():", "✓ FOUND" if result.returncode == 0 else "✗ MISSING")

# 5. validation.NewAllStrings
result = subprocess.run(['grep', '-n', 'NewAllStrings', '/app/data/validation/all.go'], 
                       capture_output=True, text=True)
print("\n5. validation.NewAllStrings():", "✓ FOUND" if result.returncode == 0 else "✗ MISSING")
