
# Check current state after turn 47
grep -n "SetMinRowsVisible" /app/widget/entry.go 2>&1 || echo "Not found in entry.go"
grep -n "SetMinRowsVisible" /app/widget/select.go 2>&1 || echo "Not found in select.go"

grep -n "MinRowsVisible" /app/widget/entry.go 2>&1 || echo "No MinRowsVisible field in entry.go"
grep -n "MinRowsVisible" /app/widget/select.go 2>&1 || echo "No MinRowsVisible field in select.go"
