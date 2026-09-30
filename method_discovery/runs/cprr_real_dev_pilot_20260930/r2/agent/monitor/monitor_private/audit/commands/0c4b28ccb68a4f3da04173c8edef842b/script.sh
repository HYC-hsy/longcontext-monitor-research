
# Check if AppMetadata exists in app.go
grep -n "AppMetadata" /app/app.go

# Check if app/meta.go exists
ls -la /app/app/meta.go 2>&1 || echo "meta.go does not exist"

# Check menu.go for Icon and Shortcut fields
grep -n "type MenuItem struct" /app/menu.go -A 10

# Check if driver/desktop/app.go exists
ls -la /app/driver/desktop/app.go 2>&1 || echo "desktop/app.go does not exist"
