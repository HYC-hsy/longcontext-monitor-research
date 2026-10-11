
cd /app

echo "=== Target 2 Investigation - JSON Theme Functions ==="
echo "Looking for JSON theme implementation..."
echo
echo "1. Check theme package directory:"
ls -la theme/ | grep -E "\.(go|json)" | head -10
echo
echo "2. Search for FromJSON function across theme package:"
grep -r "func FromJSON" theme/ 2>&1
echo
echo "3. Search for FromJSONReader function:"
grep -r "func FromJSONReader" theme/ 2>&1
echo
echo "4. Check if functions exist anywhere in codebase:"
find . -name "*.go" -type f -exec grep -l "func FromJSON" {} \; 2>/dev/null | head -5
