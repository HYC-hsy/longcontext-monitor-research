
# Check if MainMenu.Refresh exists
grep -n "func.*MainMenu.*Refresh" /app/menu.go
echo "---"
# Check if testApp has Metadata
grep -n "func.*testApp.*Metadata" /app/test/testapp.go
