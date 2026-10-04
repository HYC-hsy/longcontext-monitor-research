
# Check if the missing components are now present after syntax fixes
import subprocess

print("=== Type aliases in client/option.go ===")
result = subprocess.run(
    ['grep', '-n', 'type.*Option', '/app/client/option.go'],
    capture_output=True,
    text=True
)
print(result.stdout if result.stdout else "None found")

print("\n=== Wrapper functions in option files ===")
for filename in ['option_unary.go', 'option_stream.go', 'option_ttstream.go']:
    result = subprocess.run(
        ['grep', '-c', 'func WithUnary\\|func WithStream\\|func WithTTHeader', f'/app/client/{filename}'],
        capture_output=True,
        text=True
    )
    count = result.stdout.strip() if result.returncode == 0 else "0"
    print(f"{filename}: {count} With* functions")

print("\n=== WithRecvTimeout in streamcall ===")
result = subprocess.run(
    ['grep', 'WithRecvTimeout', '/app/client/callopt/streamcall/call_options.go'],
    capture_output=True,
    text=True
)
print("Found" if result.returncode == 0 else "NOT FOUND")
