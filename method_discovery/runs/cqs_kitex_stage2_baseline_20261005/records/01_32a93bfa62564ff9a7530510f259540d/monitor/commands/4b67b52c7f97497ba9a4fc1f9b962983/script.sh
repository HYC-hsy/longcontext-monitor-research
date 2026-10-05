
# Check if cep/sep subdirectories already exist in endpoint
ls -la /app/pkg/endpoint/cep 2>&1
echo "---"
ls -la /app/pkg/endpoint/sep 2>&1
echo "---"

# Check transport package for protocol constants
find /app -path "*/transport/*.go" -o -path "*/trans/*.go" | grep -E "(protocol|transport\.go)" | head -10
