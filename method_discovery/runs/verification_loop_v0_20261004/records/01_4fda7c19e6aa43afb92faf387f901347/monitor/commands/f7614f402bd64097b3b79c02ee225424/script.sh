
# Verify AppMetadata has Build field as int type
cd /app
grep -A 10 "^type AppMetadata struct" app.go | grep Build
