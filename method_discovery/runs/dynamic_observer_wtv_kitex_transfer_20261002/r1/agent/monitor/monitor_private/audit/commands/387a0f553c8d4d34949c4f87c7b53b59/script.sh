
# Check for cep/sep subdirectories
echo "=== Checking for pkg/endpoint subdirectories ==="
ls -la /app/pkg/endpoint/cep 2>&1
echo ""
ls -la /app/pkg/endpoint/sep 2>&1

echo -e "\n=== Checking transport package location ==="
find /app -type d -name transport | grep -v test
