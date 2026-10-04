
# Find where Protocol constants are defined
echo "=== Looking for Protocol type/constants ==="
find /app -name "*.go" -type f | xargs grep -l "type Protocol" | head -10

echo -e "\n=== Check pkg/remote structure ==="
ls -la /app/pkg/remote/ 2>&1 | head -20
