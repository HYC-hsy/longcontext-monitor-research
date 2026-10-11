
# Check if MinSize method needs updating for minRowsVisible
import subprocess

# Search for MinSize method in entry.go
result = subprocess.run(
    ['grep', '-n', '-A', '5', 'func.*MinSize', '/app/widget/entry.go'],
    capture_output=True, text=True
)
print("=== MinSize methods ===")
print(result.stdout[:1000])

# Search for minRowsVisible usage
result = subprocess.run(
    ['grep', '-n', 'minRowsVisible', '/app/widget/entry.go'],
    capture_output=True, text=True
)
print("\n=== minRowsVisible usage ===")
print(result.stdout)
