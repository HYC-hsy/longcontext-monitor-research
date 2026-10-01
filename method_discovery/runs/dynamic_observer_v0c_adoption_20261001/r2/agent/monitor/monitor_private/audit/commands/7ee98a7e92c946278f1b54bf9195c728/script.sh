
# Find transport package with Protocol constants
find /app -path "*/transport/*.go" -o -path "*/remote/transmeta/*.go" | head -10
echo "---"
# Look specifically for where Protocol type might be defined
grep -r "type Protocol" /app --include="*.go" | head -10
