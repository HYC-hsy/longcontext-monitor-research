
# Check the current state of the option files to see what's present
import subprocess

# Check if the required functions exist (even if there are syntax errors)
print("=== Checking required Target 5 functions ===\n")

# Required functions from original task
required = {
    'option_unary.go': [
        'WithUnaryOptions',
        'WithUnaryRPCTimeout', 
        'WithUnaryMiddleware',
        'WithUnaryMiddlewareBuilder'
    ],
    'option_stream.go': [
        'WithStreamOptions',
        'WithStreamRecvTimeout',
        'WithStreamMiddleware',
        'WithStreamMiddlewareBuilder',
        'WithStreamRecvMiddleware',
        'WithStreamRecvMiddlewareBuilder',
        'WithStreamSendMiddleware',
        'WithStreamSendMiddlewareBuilder'
    ],
    'option_ttstream.go': [
        'WithTTHeaderStreamingOptions',
        'WithTTHeaderStreamingTransportOptions'
    ]
}

for filename, funcs in required.items():
    filepath = f'/app/client/{filename}'
    print(f"{filename}:")
    for func in funcs:
        result = subprocess.run(
            ['grep', '-c', f'func {func}', filepath],
            capture_output=True,
            text=True
        )
        exists = result.returncode == 0 and result.stdout.strip() != '0'
        status = '✓' if exists else '✗'
        print(f"  {status} {func}")
    print()
