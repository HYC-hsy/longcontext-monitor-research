
# Check if WithRecvTimeout exists in streamcall files
import subprocess
import os

streamcall_path = '/app/client/callopt/streamcall'
if os.path.exists(streamcall_path):
    # Search for WithRecvTimeout in streamcall package
    result = subprocess.run(
        ['grep', '-rn', 'WithRecvTimeout', streamcall_path],
        capture_output=True,
        text=True
    )
    
    if result.stdout:
        print("WithRecvTimeout found in streamcall:")
        print(result.stdout)
    else:
        print("WithRecvTimeout NOT found in streamcall package")
        
    # List what functions are exported
    result2 = subprocess.run(
        ['grep', '-rn', '^func With', streamcall_path],
        capture_output=True,
        text=True
    )
    
    if result2.stdout:
        print("\nExported With* functions in streamcall:")
        print(result2.stdout)
else:
    print(f"streamcall path does not exist: {streamcall_path}")
