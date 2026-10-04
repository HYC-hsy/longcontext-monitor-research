
# Find all types that implement the App interface
grep -r "type.*struct" /app/app/*.go | grep -i app
