
# Check if default protocol was changed to Framed
import subprocess
result = subprocess.run(
    ['grep', '-n', 'transportProtocol', '/app/pkg/rpcinfo/rpcconfig.go'],
    capture_output=True, text=True
)
print("=== transportProtocol in rpcconfig.go ===")
print(result.stdout)
