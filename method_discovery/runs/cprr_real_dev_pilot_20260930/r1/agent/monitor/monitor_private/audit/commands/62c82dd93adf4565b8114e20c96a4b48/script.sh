
# Check for AppMetadata struct
grep -n "type AppMetadata" /app/app.go

# Check for Metadata method in App interface
grep -n "Metadata()" /app/app.go

# Check if app/meta.go exists
ls -la /app/app/meta.go 2>&1

# Check for theme JSON support
ls -la /app/theme/json.go 2>&1

# Check for sprintf binding
ls -la /app/data/binding/sprintf.go 2>&1

# Check menu.go for Icon/Shortcut fields
grep -n "type MenuItem" /app/menu.go -A 10

# Check for desktop app interface
ls -la /app/driver/desktop/app.go 2>&1
