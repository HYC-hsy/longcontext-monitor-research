
# Check for existing streaming and endpoint packages
cd /app
ls -la pkg/ 2>/dev/null || echo "pkg/ not found"
ls -la pkg/streaming/ 2>/dev/null || echo "pkg/streaming/ not found"
ls -la pkg/endpoint/ 2>/dev/null || echo "pkg/endpoint/ not found"
ls -la pkg/endpoint/cep/ 2>/dev/null || echo "pkg/endpoint/cep/ not found"
ls -la pkg/endpoint/sep/ 2>/dev/null || echo "pkg/endpoint/sep/ not found"
