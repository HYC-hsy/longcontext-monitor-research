
# Check if the file exists and what methods are in it
grep -n "func\|type\|Set" /app/driver/desktop/app.go 2>/dev/null || echo "File not found or no matches"
