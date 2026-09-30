
# Verify WithRecvTimeout is in streamcall and not in option_stream.go
import subprocess

result = subprocess.run(['grep', '-n', 'WithRecvTimeout', '/app/client/callopt/streamcall/call_options.go'], 
                       capture_output=True, text=True)
print("=== WithRecvTimeout in streamcall ===")
print(result.stdout if result.stdout else "Not found")

result2 = subprocess.run(['grep', '-n', 'WithRecvTimeout', '/app/client/option_stream.go'], 
                        capture_output=True, text=True)
print("\n=== WithRecvTimeout in option_stream.go ===")
print(result2.stdout if result2.stdout else "Not found (correct)")
