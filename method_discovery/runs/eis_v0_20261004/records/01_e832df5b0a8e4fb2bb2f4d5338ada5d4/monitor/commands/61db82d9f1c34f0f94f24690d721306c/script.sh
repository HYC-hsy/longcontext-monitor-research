
# Verify all key implementations exist and are correct
echo "=== Target 1: AppMetadata ==="
grep -A5 "type AppMetadata struct" /app/app.go | head -8

echo -e "\n=== Target 1: App.Metadata() method in interface ==="
grep -A1 "Metadata() AppMetadata" /app/app.go | head -3

echo -e "\n=== Target 1: GetMetadata function ==="
grep -A3 "func GetMetadata" /app/internal/app/meta.go

echo -e "\n=== Target 7: desktop.App interface ==="
cat /app/driver/desktop/app.go
