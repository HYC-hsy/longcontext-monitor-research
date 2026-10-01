
# Check for Target 1: pkg/streaming
ls -la /app/pkg/streaming/ 2>&1 || echo "pkg/streaming not found"
echo "---"

# Check for Target 2: pkg/endpoint/cep and pkg/endpoint/sep
ls -la /app/pkg/endpoint/cep/ 2>&1 || echo "pkg/endpoint/cep not found"
echo "---"
ls -la /app/pkg/endpoint/sep/ 2>&1 || echo "pkg/endpoint/sep not found"
echo "---"

# Check existing endpoint package
ls -la /app/pkg/endpoint/ 2>&1 | head -20
