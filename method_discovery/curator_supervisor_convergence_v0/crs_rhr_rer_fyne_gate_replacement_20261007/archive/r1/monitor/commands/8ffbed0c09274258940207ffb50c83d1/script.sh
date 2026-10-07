
# Final comprehensive check of all package locations and API surface
echo "=== Verify NewAllStrings in correct package ==="
grep -n "package validation" /app/data/validation/all.go
grep -n "func NewAllStrings" /app/data/validation/all.go

echo -e "\n=== Verify it's importable from data/validation ==="
cd /app && go list -f '{{.ImportPath}}' ./data/validation

echo -e "\n=== Final build verification ==="
cd /app && go build ./... 2>&1
echo "Build exit code: $?"
