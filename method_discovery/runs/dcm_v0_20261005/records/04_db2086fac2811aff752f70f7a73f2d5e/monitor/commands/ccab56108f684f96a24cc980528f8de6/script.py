
# Check what WithRecvTimeout currently looks like and what the errors are
with open('/app/client/callopt/streamcall/call_options.go', 'r') as f:
    lines = f.readlines()
    
print("=== WithRecvTimeout implementation (around line 51-56) ===")
for i, line in enumerate(lines[45:60], start=46):
    print(f"{i}: {line.rstrip()}")

print("\n=== Current imports ===")
for i, line in enumerate(lines[:30], start=1):
    if 'import' in line or (i > 15 and i < 25):
        print(f"{i}: {line.rstrip()}")
