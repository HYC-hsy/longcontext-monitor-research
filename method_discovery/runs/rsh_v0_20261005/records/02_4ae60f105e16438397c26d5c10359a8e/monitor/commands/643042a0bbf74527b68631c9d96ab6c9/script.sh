
# Check if AppMetadata already exists
grep -n "AppMetadata" /app/app.go || echo "AppMetadata not found"

# Check if Metadata() method exists in App interface
grep -n "Metadata()" /app/app.go || echo "Metadata() not found"

# Check MenuItem for Icon and Shortcut fields
grep -n "Icon\|Shortcut" /app/menu.go || echo "Icon/Shortcut not found in menu.go"

# Check if RemoveAll exists in Container
grep -n "RemoveAll" /app/container.go || echo "RemoveAll not found"
