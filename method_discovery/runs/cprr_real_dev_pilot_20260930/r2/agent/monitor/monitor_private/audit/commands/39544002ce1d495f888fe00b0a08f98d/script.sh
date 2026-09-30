
# Check if LoadResourceFromURI exists in the fyne package
grep -r "LoadResourceFromURI" /app --include="*.go" | grep -v "theme/json.go" | head -10

# Check resource.go to see what resource loading functions exist
grep -n "func.*Resource" /app/resource.go
