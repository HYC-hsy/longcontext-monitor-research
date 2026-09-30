
# Check for AppMetadata struct
grep -n "type AppMetadata" /app/app.go

# Check for Metadata method in App interface
grep -n "Metadata()" /app/app.go
