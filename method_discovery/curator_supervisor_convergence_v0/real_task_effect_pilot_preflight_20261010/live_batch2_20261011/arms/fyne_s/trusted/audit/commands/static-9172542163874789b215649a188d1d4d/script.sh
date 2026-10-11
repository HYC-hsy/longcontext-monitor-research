
# Verify all other structural targets systematically
echo "=== Target 1: AppMetadata struct ==="
grep -A 10 "type AppMetadata struct" app.go
echo ""
echo "=== Target 1: App.Metadata method in interface ==="
grep -B 2 -A 1 "Metadata()" app.go
echo ""
echo "=== Target 4: MenuItem Icon and Shortcut fields ==="
grep -A 15 "type MenuItem struct" menu.go
