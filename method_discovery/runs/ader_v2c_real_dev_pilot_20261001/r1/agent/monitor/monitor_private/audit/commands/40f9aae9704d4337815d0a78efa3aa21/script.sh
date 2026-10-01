
# Check if test/testapp.go has an App implementation
grep -A 5 "type.*App" /app/test/testapp.go 2>/dev/null || echo "No App type found or file doesn't exist"
