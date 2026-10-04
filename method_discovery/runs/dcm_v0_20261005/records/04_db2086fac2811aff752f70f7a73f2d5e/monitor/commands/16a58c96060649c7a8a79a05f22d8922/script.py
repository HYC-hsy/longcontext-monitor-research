
# Verify Target 5 requirement 3 - the WithStreamMiddleware functions that use cep types
# Original requirement explicitly says:
# "WithStreamMiddleware(mw cep.StreamMiddleware) StreamOption"
# "WithStreamRecvMiddleware(mw cep.StreamRecvMiddleware) StreamOption"
# etc.

import subprocess

print("=== Checking Target 5 Requirement 3 (Stream options with cep types) ===\n")

# The original requirement lists these specific functions with cep types:
required_functions = [
    'WithStreamMiddleware',
    'WithStreamMiddlewareBuilder', 
    'WithStreamRecvMiddleware',
    'WithStreamRecvMiddlewareBuilder',
    'WithStreamSendMiddleware',
    'WithStreamSendMiddlewareBuilder'
]

print("Checking option_stream.go for these functions:")
for func in required_functions:
    result = subprocess.run(
        ['grep', '-c', f'func {func}', '/app/client/option_stream.go'],
        capture_output=True,
        text=True
    )
    exists = result.returncode == 0 and result.stdout.strip() != '0'
    print(f"  {'✓' if exists else '✗'} {func}")

print("\n=== Checking what functions ARE in option_stream.go ===")
result = subprocess.run(
    ['grep', '^func With', '/app/client/option_stream.go'],
    capture_output=True,
    text=True
)
print(result.stdout if result.stdout else "No With* functions found")

print("\n=== Reading option_stream.go to understand implementation ===")
with open('/app/client/option_stream.go', 'r') as f:
    content = f.read()
    # Count lines
    lines = content.split('\n')
    print(f"File has {len(lines)} lines")
    # Show function signatures
    print("\nFunction signatures in file:")
    for i, line in enumerate(lines, 1):
        if line.startswith('func With'):
            print(f"  Line {i}: {line[:80]}")
