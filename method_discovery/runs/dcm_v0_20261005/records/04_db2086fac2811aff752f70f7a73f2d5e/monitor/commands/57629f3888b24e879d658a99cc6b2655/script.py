
# Check option.go for the required type aliases
import subprocess

result = subprocess.run(
    ['grep', '-n', '-A', '1', 'type.*Option', '/app/client/option.go'],
    capture_output=True,
    text=True
)

print("Type aliases in client/option.go:")
print(result.stdout)

# Also check for TailOption function
result2 = subprocess.run(
    ['grep', '-n', 'func TailOption', '/app/client/option.go'],
    capture_output=True,
    text=True
)

print("\nTailOption function:")
if result2.stdout:
    print(result2.stdout)
else:
    print("NOT FOUND")
