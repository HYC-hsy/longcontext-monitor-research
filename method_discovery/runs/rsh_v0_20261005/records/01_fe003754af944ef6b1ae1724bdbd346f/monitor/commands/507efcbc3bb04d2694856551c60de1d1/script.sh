
# Target 1: Verify AppMetadata struct fields and App.Metadata() method
echo "=== Target 1: App Metadata System ==="
echo "1. AppMetadata struct fields:"
grep -A 10 "type AppMetadata struct" /app/app.go | head -15

echo -e "\n2. App.Metadata() in interface:"
grep "Metadata()" /app/app.go | head -3

echo -e "\n3. app/meta.go exists with SetMetadata:"
ls -la /app/app/meta.go 2>&1 && grep "func SetMetadata" /app/app/meta.go

echo -e "\n4. Default metadata values:"
grep -A 5 "var appMetadata" /app/app/meta.go
