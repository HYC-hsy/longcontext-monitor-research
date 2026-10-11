
# Check if Entry MinSize calculation uses minRowsVisible
import subprocess

# Search for minRowsVisible in MinSize or renderer methods
result = subprocess.run(
    ['grep', '-n', '-B', '3', '-A', '10', 'minRowsVisible', '/app/widget/entry.go'],
    capture_output=True, text=True
)
print("=== minRowsVisible usage in entry.go ===")
print(result.stdout)

# Check if it's used in renderer MinSize calculation
result = subprocess.run(
    ['grep', '-n', 'MinSize', '/app/widget/entry.go'],
    capture_output=True, text=True
)
print("\n=== MinSize method locations ===")
print(result.stdout)
