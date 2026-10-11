
cd /app
# Check App interface has Metadata method
grep -A 30 "type App interface" app.go | grep -E "(Metadata|type App)"
echo "---"
# Check AppMetadata struct exists
grep -A 10 "type AppMetadata struct" app.go
