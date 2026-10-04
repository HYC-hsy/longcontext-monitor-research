
# Comprehensive verification of Target 5 completion against original requirements
import subprocess
import os

print("=== TARGET 5 VERIFICATION ===\n")

# 1. Type aliases in client/option.go
print("1. Type aliases in client/option.go:")
result = subprocess.run(
    ['grep', '-n', 'type.*Option', '/app/client/option.go'],
    capture_output=True,
    text=True
)
for line in result.stdout.strip().split('\n')[:10]:
    print(f"  {line}")

# 2. Check wrapper functions
print("\n2. Wrapper functions:")
wrappers = [
    ('option_unary.go', 'WithUnaryOptions'),
    ('option_stream.go', 'WithStreamOptions'),
    ('option_ttstream.go', 'WithTTHeaderStreamingOptions'),
]
for filename, func_name in wrappers:
    result = subprocess.run(
        ['grep', '-c', f'func {func_name}', f'/app/client/{filename}'],
        capture_output=True,
        text=True
    )
    exists = result.returncode == 0 and result.stdout.strip() != '0'
    print(f"  {'✓' if exists else '✗'} {filename}: {func_name}")

# 3. WithRecvTimeout in streamcall
print("\n3. WithRecvTimeout in streamcall:")
result = subprocess.run(
    ['grep', '-n', 'func WithRecvTimeout', '/app/client/callopt/streamcall/call_options.go'],
    capture_output=True,
    text=True
)
if result.returncode == 0:
    print(f"  ✓ {result.stdout.strip()}")
else:
    print("  ✗ NOT FOUND")

# 4. TailOption function
print("\n4. TailOption function:")
result = subprocess.run(
    ['grep', '-c', 'func TailOption', '/app/client/option.go'],
    capture_output=True,
    text=True
)
exists = result.returncode == 0 and result.stdout.strip() != '0'
print(f"  {'✓' if exists else '✗'} TailOption in option.go")

# 5. Build verification
print("\n5. Build verification:")
result = subprocess.run(
    ['go', 'build', './client/...'],
    cwd='/app',
    capture_output=True,
    text=True,
    timeout=30
)
if result.returncode == 0:
    print("  ✓ go build ./client/... PASSES")
else:
    print(f"  ✗ Build FAILED: {result.stderr[:200]}")

print("\n=== ORIGINAL REQUIREMENT CHECK ===")
print("\nTarget 5 requirement 3 specifies:")
print("- WithStreamMiddleware(mw cep.StreamMiddleware) StreamOption")
print("- WithStreamMiddlewareBuilder(mwb cep.StreamMiddlewareBuilder) StreamOption")
print("\nThese use cep types from pkg/endpoint/cep.")
print("\nChecking if these functions exist:")
result = subprocess.run(
    ['grep', 'WithStreamMiddleware', '/app/client/option_stream.go'],
    capture_output=True,
    text=True
)
if 'cep.Stream' in result.stdout:
    print("  ✓ Uses cep types")
elif result.returncode == 0:
    print(f"  ⚠ Functions exist but may not use cep types: {result.stdout[:100]}")
else:
    print("  ✗ WithStreamMiddleware functions NOT FOUND")
