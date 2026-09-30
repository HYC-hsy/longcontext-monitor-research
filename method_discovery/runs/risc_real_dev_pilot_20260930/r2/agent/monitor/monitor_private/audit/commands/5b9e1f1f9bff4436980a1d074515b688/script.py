
# Check internal/client for option type definitions
import os
internal_client = '/app/internal/client'
if os.path.exists(internal_client):
    print("=== internal/client directory exists ===")
    files = [f for f in os.listdir(internal_client) if f.endswith('.go')]
    print(f"Files: {sorted(files)[:10]}")
    
    # Search for UnaryOption in internal/client
    import subprocess
    result = subprocess.run(['grep', '-rn', 'type.*UnaryOption\\|type.*StreamOption', internal_client], 
                           capture_output=True, text=True)
    print("\n=== Option types in internal/client ===")
    print(result.stdout if result.stdout else "Not found")
else:
    print("internal/client not found")

# Also check if type aliases could be in a different format
result2 = subprocess.run(['grep', '-n', '= client\\.', '/app/client/option.go'], 
                        capture_output=True, text=True)
print("\n=== Type aliases to client.* in option.go ===")
print(result2.stdout if result2.stdout else "Not found (only Option and Options)")
