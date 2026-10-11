
# Search for Bytes binding type definition across entire binding package
grep -r "type Bytes interface" task/workspace/data/binding/ 2>/dev/null || echo "No Bytes interface found"
