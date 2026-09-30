
# Check all modified/created files
cd /app && git status --short

# List all new files
cd /app && git ls-files --others --exclude-standard | grep -v "\.monitor"

# Count targets implemented
echo "=== Checking Target implementations ==="
echo "Target 1 - AppMetadata in app.go:" && grep -c "type AppMetadata struct" /app/app.go
echo "Target 1 - app/meta.go exists:" && test -f /app/app/meta.go && echo "yes" || echo "no"
echo "Target 2 - theme/json.go exists:" && test -f /app/theme/json.go && echo "yes" || echo "no"
echo "Target 3 - sprintf.go exists:" && test -f /app/data/binding/sprintf.go && echo "yes" || echo "no"
echo "Target 4 - MenuItem.Icon field:" && grep -c "Icon.*Resource" /app/menu.go
echo "Target 5 - ToolbarAction.SetIcon:" && grep -c "func.*SetIcon" /app/widget/toolbar.go
echo "Target 6 - Container.RemoveAll:" && grep -c "func.*RemoveAll" /app/container.go
echo "Target 7 - desktop/app.go exists:" && test -f /app/driver/desktop/app.go && echo "yes" || echo "no"
