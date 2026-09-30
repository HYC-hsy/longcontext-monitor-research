
# Search for WithRecvTimeout
import subprocess
result = subprocess.run(['grep', '-rn', 'WithRecvTimeout', '/app/client/'], 
                       capture_output=True, text=True)
print("=== WithRecvTimeout locations ===")
print(result.stdout if result.stdout else "Not found")

# Search for TailOption
result2 = subprocess.run(['grep', '-rn', 'TailOption', '/app/client/'], 
                        capture_output=True, text=True)
print("\n=== TailOption locations ===")
print(result2.stdout if result2.stdout else "Not found")

# Search for type UnaryOption definition
result3 = subprocess.run(['grep', '-rn', 'type UnaryOption', '/app/'], 
                        capture_output=True, text=True)
print("\n=== UnaryOption type definition ===")
print(result3.stdout[:500] if result3.stdout else "Not found")
