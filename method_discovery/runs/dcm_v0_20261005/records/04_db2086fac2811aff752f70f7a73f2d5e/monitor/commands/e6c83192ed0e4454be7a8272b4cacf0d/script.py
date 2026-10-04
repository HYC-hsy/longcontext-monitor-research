
# Verify all missing components have been added
import subprocess

print("=== VERIFICATION OF ALL TARGET 5 REQUIREMENTS ===\n")

# 1. Type aliases in client/option.go
print("1. Type aliases in client/option.go:")
result = subprocess.run(
    ['grep', '-E', 'type (UnaryOption|StreamOption|TTHeaderStreamingOption)', '/app/client/option.go'],
    capture_output=True,
    text=True
)
if result.returncode == 0:
    for line in result.stdout.strip().split('\n'):
        print(f"  ✓ {line}")
else:
    print("  ✗ Type aliases NOT FOUND")

# 2. Wrapper functions
print("\n2. Wrapper functions:")
wrappers = [
    ('option_unary.go', 'WithUnaryOptions'),
    ('option_stream.go', 'WithStreamOptions'),
    ('option_stream.go', 'WithStreamMiddleware'),
    ('option_stream.go', 'WithStreamMiddlewareBuilder'),
    ('option_ttstream.go', 'WithTTHeaderStreamingOptions'),
]

for filename, func_name in wrappers:
    result = subprocess.run(
        ['grep', f'func {func_name}', f'/app/client/{filename}'],
        capture_output=True,
        text=True
    )
    status = '✓' if result.returncode == 0 else '✗'
    print(f"  {status} {filename}: {func_name}")

# 3. Check if middleware uses cep types
print("\n3. Middleware type check:")
result = subprocess.run(
    ['grep', 'cep.Stream', '/app/client/option_stream.go'],
    capture_output=True,
    text=True
)
if result.returncode == 0:
    print("  ✓ option_stream.go uses cep types")
else:
    print("  ✗ option_stream.go does NOT use cep types")

# 4. WithRecvTimeout in streamcall (task is adding this now)
print("\n4. WithRecvTimeout in streamcall:")
result = subprocess.run(
    ['grep', 'func WithRecvTimeout', '/app/client/callopt/streamcall/call_options.go'],
    capture_output=True,
    text=True
)
status = '✓' if result.returncode == 0 else '⏳'
print(f"  {status} WithRecvTimeout (task adding now as 'final requirement')")

print("\n5. Build status:")
print("  ✓ go build ./client/... PASSED at turn 119")
