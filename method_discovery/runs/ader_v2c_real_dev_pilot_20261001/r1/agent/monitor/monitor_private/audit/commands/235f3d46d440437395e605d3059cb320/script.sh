
# Check if AppMetadata has Icon field (it was cut off in previous grep)
grep -A 12 "type AppMetadata struct" /app/app.go | grep -E "Icon|Build"
