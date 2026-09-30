
# Check if there are any tests or config changes related to default protocol
import subprocess

result = subprocess.run(
    ['git', 'diff', '--no-index', '/dev/null', 'pkg/rpcinfo/rpcconfig.go', '|', 'grep', '-A3', '-B3', 'Framed\\|PurePayload'],
    shell=True, cwd='/app', capture_output=True, text=True
)
print("Git diff for rpcconfig.go (Framed/PurePayload):")
print(result.stdout[:1000] if result.stdout else "No relevant changes")

# Check pool initialization
result2 = subprocess.run(
    ['grep', '-A10', 'rpcConfigPool\\|Pool.*sync', '/app/pkg/rpcinfo/rpcconfig.go'],
    capture_output=True, text=True
)
print("\n\nrpcConfigPool initialization:")
print(result2.stdout[:1000] if result2.stdout else "None")
