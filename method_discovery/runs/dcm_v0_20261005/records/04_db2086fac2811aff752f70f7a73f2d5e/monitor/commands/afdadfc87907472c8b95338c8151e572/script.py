
# Check current state of required components despite syntax errors
import subprocess
import os

print("=== Checking for required wrapper functions ===\n")

# Check for wrapper functions in option files
checks = [
    ('option_unary.go', 'WithUnaryOptions'),
    ('option_stream.go', 'WithStreamOptions'),
    ('option_stream.go', 'WithStreamMiddleware'),
    ('option_ttstream.go', 'WithTTHeaderStreamingOptions'),
]

for filename, func_name in checks:
    filepath = f'/app/client/{filename}'
    result = subprocess.run(
        ['grep', '-c', f'func {func_name}', filepath],
        capture_output=True,
        text=True
    )
    exists = result.returncode == 0 and result.stdout.strip() != '0'
    status = '✓' if exists else '✗'
    print(f"{status} {filename}: {func_name}")

print("\n=== Checking for type aliases in option.go ===\n")

# Check for type aliases in option.go
type_aliases = [
    'UnaryOption',
    'UnaryOptions',
    'StreamOption',
    'StreamOptions',
    'TTHeaderStreamingOption',
    'TTHeaderStreamingOptions'
]

for alias in type_aliases:
    result = subprocess.run(
        ['grep', '-c', f'type {alias}', '/app/client/option.go'],
        capture_output=True,
        text=True
    )
    exists = result.returncode == 0 and result.stdout.strip() != '0'
    status = '✓' if exists else '✗'
    print(f"{status} type {alias}")

print("\n=== Checking for WithRecvTimeout in streamcall ===\n")

result = subprocess.run(
    ['grep', '-c', 'func WithRecvTimeout', '/app/client/callopt/streamcall/call_options.go'],
    capture_output=True,
    text=True
)
exists = result.returncode == 0 and result.stdout.strip() != '0'
status = '✓' if exists else '✗'
print(f"{status} WithRecvTimeout in streamcall")
