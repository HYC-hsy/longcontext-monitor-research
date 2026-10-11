
# Check Target 2: JSON Theme - should have full theme system
if [ -f /app/theme/json.go ]; then
    echo "=== theme/json.go exists ==="
    grep -n "func FromJSON" /app/theme/json.go | head -5
    grep -n "func FromJSONReader" /app/theme/json.go | head -5
    echo ""
    echo "=== Checking for Sizes, Fonts, Icons support ==="
    grep -E "Sizes|Fonts|Icons" /app/theme/json.go | head -10
else
    echo "ERROR: theme/json.go does NOT exist"
fi
