
# Check if Bytes binding type exists anywhere in the binding package
find task/workspace/data/binding -name "*.go" -exec grep -l "type Bytes interface" {} \;
