
# Search for struct types that might implement App
cd /app
grep -r "type.*struct" app/ test/ --include="*.go" | grep -i app | head -30
