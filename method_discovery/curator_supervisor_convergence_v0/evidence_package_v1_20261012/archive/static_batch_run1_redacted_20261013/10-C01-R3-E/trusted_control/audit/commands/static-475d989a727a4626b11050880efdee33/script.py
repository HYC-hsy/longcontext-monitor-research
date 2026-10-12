
# Check StringToStringWithFormat for "%s" optimization
with open("task/workspace/data/binding/sprintf.go", "r") as f:
    content = f.read()
    
# Find StringToStringWithFormat function
if "StringToStringWithFormat" in content:
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if "func StringToStringWithFormat" in line:
            # Print the function
            start = i
            end = min(len(lines), i+20)
            print(f"Found at line {i+1}:")
            print('\n'.join(f"{j+1}: {lines[j]}" for j in range(start, end)))
            break
else:
    print("StringToStringWithFormat NOT FOUND")
