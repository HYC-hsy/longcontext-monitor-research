
# Check if Entry has SetMinRowsVisible
grep -n "SetMinRowsVisible" /app/widget/entry.go 2>&1 || echo "Not found in entry.go"

# Check if Select has SetMinRowsVisible  
grep -n "SetMinRowsVisible" /app/widget/select.go 2>&1 || echo "Not found in select.go"

# Also check for MinRowsVisible field
grep -n "MinRowsVisible" /app/widget/entry.go 2>&1 || echo "No MinRowsVisible field in entry.go"
grep -n "MinRowsVisible" /app/widget/select.go 2>&1 || echo "No MinRowsVisible field in select.go"
