
# Search for SetMinRowsVisible in entry.go
with open("task/workspace/widget/entry.go", "r") as f:
    content = f.read()
    
if "SetMinRowsVisible" in content:
    # Find the method
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if "SetMinRowsVisible" in line:
            # Print context around the method
            start = max(0, i-2)
            end = min(len(lines), i+15)
            print(f"Found at line {i+1}:")
            print('\n'.join(f"{j+1}: {lines[j]}" for j in range(start, end)))
            print()
else:
    print("SetMinRowsVisible NOT FOUND in entry.go")
