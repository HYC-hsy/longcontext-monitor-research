
# Search for types with methods that suggest App interface implementation
cd /app && grep -r "func.*NewWindow.*fyne.Window" --include="*.go" | grep -v vendor | grep -v "^Binary"
