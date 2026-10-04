
# Check current state of missing components after turns 101-107
import subprocess

print("=== Current state of missing components ===\n")

# 1. Check type aliases in client/option.go
print("1. Type aliases in client/option.go:")
result = subprocess.run(
    ['grep', '-E', 'type (UnaryOption|StreamOption|TTHeaderStreamingOption)', '/app/client/option.go'],
    capture_output=True,
    text=True
)
if result.returncode == 0:
    print(result.stdout)
else:
    print("  ✗ UnaryOption, StreamOption, TTHeaderStreamingOption type aliases NOT FOUND\n")

# 2. Check wrapper functions
print("2. Wrapper functions:")
wrappers = [
    ('option_unary.go', 'WithUnaryOptions'),
    ('option_stream.go', 'WithStreamOptions'),
    ('option_stream.go', 'WithStreamMiddleware'),
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

# 3. Check WithRecvTimeout in streamcall
print("\n3. WithRecvTimeout in streamcall:")
result = subprocess.run(
    ['grep', 'func WithRecvTimeout', '/app/client/callopt/streamcall/call_options.go'],
    capture_output=True,
    text=True
)
status = '✓' if result.returncode == 0 else '✗'
print(f"  {status} WithRecvTimeout in client/callopt/streamcall/call_options.go")

# 4. Check if middleware uses cep types
print("\n4. Middleware type check:")
result = subprocess.run(
    ['grep', 'cep.Stream', '/app/client/option_stream.go'],
    capture_output=True,
    text=True
)
if result.returncode == 0:
    print("  ✓ option_stream.go uses cep types")
else:
    print("  ✗ option_stream.go does NOT use cep types (required: cep.StreamMiddleware)")
