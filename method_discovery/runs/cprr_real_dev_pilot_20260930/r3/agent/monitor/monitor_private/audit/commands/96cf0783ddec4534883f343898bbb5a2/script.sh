
# Check for recent modifications
echo "=== Most recently modified Go files ==="
find /app -name "*.go" -type f -mtime -1 2>/dev/null | head -20

echo -e "\n=== Check git status ==="
cd /app && git status --short 2>&1 | head -30

echo -e "\n=== Check if pkg/endpoint has cep or sep subdirs ==="
ls -la /app/pkg/endpoint/ 2>&1
