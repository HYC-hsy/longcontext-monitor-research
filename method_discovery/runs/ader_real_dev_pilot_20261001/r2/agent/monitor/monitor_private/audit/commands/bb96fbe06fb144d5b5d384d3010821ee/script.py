
# Search for where default protocol is initialized in RPC config
import subprocess

# Check rpcinfo package for default protocol
result = subprocess.run(
    ['grep', '-rn', 'NewRPCConfig\\|TransportProtocol.*Protocol\\|protocol.*=', '--include=*.go', '/app/pkg/rpcinfo'],
    capture_output=True, text=True
)
print("RPC config initialization:")
print(result.stdout[:2000] if result.stdout else "None")

# Check internal client options initialization
result2 = subprocess.run(
    ['grep', '-A5', '-B5', 'func.*NewOptions\\|Options struct', '/app/internal/client/option.go'],
    capture_output=True, text=True
)
print("\n\nClient Options struct/initialization:")
print(result2.stdout[:2000] if result2.stdout else "None")
