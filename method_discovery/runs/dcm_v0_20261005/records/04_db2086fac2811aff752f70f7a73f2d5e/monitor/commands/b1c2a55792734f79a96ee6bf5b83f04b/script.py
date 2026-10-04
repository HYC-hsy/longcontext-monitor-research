
# Check exactly which wrapper functions are present
import subprocess

print("=== Checking specific required wrapper functions ===\n")

required_wrappers = [
    ('option_unary.go', 'WithUnaryOptions'),
    ('option_stream.go', 'WithStreamOptions'),
    ('option_stream.go', 'WithStreamMiddleware'),
    ('option_stream.go', 'WithStreamMiddlewareBuilder'),
    ('option_ttstream.go', 'WithTTHeaderStreamingOptions'),
]

for filename, func_name in required_wrappers:
    result = subprocess.run(
        ['grep', f'func {func_name}', f'/app/client/{filename}'],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print(f"✓ {filename}: {func_name}")
    else:
        print(f"✗ {filename}: {func_name} MISSING")

print("\n=== Checking if middleware uses cep types ===")
result = subprocess.run(
    ['grep', 'cep.StreamMiddleware', '/app/client/option_stream.go'],
    capture_output=True,
    text=True
)
if result.returncode == 0:
    print("✓ option_stream.go uses cep.StreamMiddleware")
else:
    print("✗ option_stream.go does NOT use cep.StreamMiddleware (should be using cep types, not endpoint types)")
