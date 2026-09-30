
# Verify the fix was applied
grep -n "LoadResourceFromURI" /app/theme/json.go | head -5

# Check if the code compiles now
cd /app && go build ./... 2>&1 | head -20
