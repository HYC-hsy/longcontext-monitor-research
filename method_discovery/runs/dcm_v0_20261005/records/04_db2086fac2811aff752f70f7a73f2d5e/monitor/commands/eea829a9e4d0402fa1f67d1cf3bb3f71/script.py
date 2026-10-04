
# Check what functions are defined in the three option files
import subprocess

files = [
    '/app/client/option_unary.go',
    '/app/client/option_stream.go',
    '/app/client/option_ttstream.go'
]

for f in files:
    result = subprocess.run(
        ['grep', '-n', '^func With', f],
        capture_output=True,
        text=True
    )
    
    print(f"\n{f}:")
    if result.stdout:
        print(result.stdout)
    else:
        print("  No exported With* functions found or file has syntax errors")
