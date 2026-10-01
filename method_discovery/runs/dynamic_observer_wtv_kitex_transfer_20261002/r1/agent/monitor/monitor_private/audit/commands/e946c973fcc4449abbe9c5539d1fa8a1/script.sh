
# Find transport protocol files
echo "=== Looking for transport protocol definitions ==="
find /app -path "*/pkg/remote/trans/*" -name "*.go" | grep -E "(protocol|transport)" | head -10

echo -e "\n=== Looking for transport package files ==="
find /app -path "*transport*" -name "*.go" -type f | grep -v test | head -15
