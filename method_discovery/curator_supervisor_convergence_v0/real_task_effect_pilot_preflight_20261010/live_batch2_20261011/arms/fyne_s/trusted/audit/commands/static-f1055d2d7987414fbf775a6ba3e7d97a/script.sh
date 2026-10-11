
# Verify Target 1: SetMetadata function exists in app package
echo "=== Target 1: app.SetMetadata function ==="
grep -A 8 "func SetMetadata" app/meta.go
echo ""

# Verify Target 2: JSON theme functions
echo "=== Target 2: FromJSON and FromJSONReader signatures ==="
grep "^func FromJSON" theme/json.go
grep "^func FromJSONReader" theme/json.go
