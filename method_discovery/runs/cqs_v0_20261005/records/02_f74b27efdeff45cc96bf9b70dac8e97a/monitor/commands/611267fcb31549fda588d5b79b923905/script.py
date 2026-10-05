
# Check the default protocol in rpcconfig.go
import subprocess
result = subprocess.run(
    ['grep', '-A2', '-B2', 'func.*initialize', '/app/pkg/rpcinfo/rpcconfig.go'],
    capture_output=True, text=True
)
print("=== initialize() function in rpcconfig.go ===")
print(result.stdout)

# Also check for transportProtocol = lines
result2 = subprocess.run(
    ['grep', 'transportProtocol =', '/app/pkg/rpcinfo/rpcconfig.go'],
    capture_output=True, text=True
)
print("\n=== transportProtocol assignments ===")
print(result2.stdout)
