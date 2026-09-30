
import subprocess
import os

# Search for default protocol configuration
result = subprocess.run(
    ['grep', '-r', 'PurePayload', '--include=*.go', '/app/client', '/app/server', '/app/internal'],
    capture_output=True, text=True, cwd='/app'
)

print("PurePayload references in client/server/internal:")
print(result.stdout[:2000] if result.stdout else "None found")

# Check for default protocol initialization
result2 = subprocess.run(
    ['grep', '-rn', 'SetTransportProtocol\\|TransportProtocol.*=\\|Protocol:.*transport\\.' , '--include=*.go', '/app/internal/client'],
    capture_output=True, text=True, cwd='/app'
)

print("\n\nTransportProtocol settings in internal/client:")
print(result2.stdout[:1500] if result2.stdout else "None found")
