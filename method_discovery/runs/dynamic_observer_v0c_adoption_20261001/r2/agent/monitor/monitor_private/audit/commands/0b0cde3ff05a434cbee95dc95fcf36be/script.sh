
# Check what was created for Target 2
ls -la /app/pkg/endpoint/cep/ 2>&1
echo "---"
ls -la /app/pkg/endpoint/sep/ 2>&1
echo "---"
# Check if UnaryEndpoint was added to pkg/endpoint
grep -n "UnaryEndpoint\|UnaryMiddleware" /app/pkg/endpoint/*.go 2>&1 | head -20
