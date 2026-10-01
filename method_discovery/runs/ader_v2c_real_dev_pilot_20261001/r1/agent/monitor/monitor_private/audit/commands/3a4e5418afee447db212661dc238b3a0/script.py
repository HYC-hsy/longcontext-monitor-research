
import os
import subprocess

# Check git status to see if any work has been done
result = subprocess.run(['git', 'status', '--short'], 
                       cwd='/app', 
                       capture_output=True, 
                       text=True)
print("Git status:")
print(result.stdout if result.stdout else "(no changes)")
print()

# Check for recently modified .go files in last hour
result = subprocess.run(['find', '/app', '-name', '*.go', '-mmin', '-60', '-type', 'f'],
                       capture_output=True,
                       text=True)
print("Recently modified .go files (last hour):")
print(result.stdout if result.stdout else "(none)")
