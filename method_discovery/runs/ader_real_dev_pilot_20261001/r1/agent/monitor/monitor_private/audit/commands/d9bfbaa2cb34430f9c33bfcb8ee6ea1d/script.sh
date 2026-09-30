
cd /app
# Verify key files exist
echo "=== Target files verification ==="
test -f app/meta.go && echo "✓ app/meta.go" || echo "✗ app/meta.go"
test -f theme/json.go && echo "✓ theme/json.go" || echo "✗ theme/json.go"
test -f data/binding/sprintf.go && echo "✓ data/binding/sprintf.go" || echo "✗ data/binding/sprintf.go"
test -f data/validation/all.go && echo "✓ data/validation/all.go" || echo "✗ data/validation/all.go"
test -f driver/desktop/app.go && echo "✓ driver/desktop/app.go" || echo "✗ driver/desktop/app.go"
