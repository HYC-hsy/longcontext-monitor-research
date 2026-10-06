
# Check if there are build/test artifacts or error logs
ls -la /app/*.log 2>/dev/null || echo "No log files"
ls -la /app/pkg/endpoint/cep 2>/dev/null || echo "cep package doesn't exist yet"
ls -la /app/pkg/endpoint/sep 2>/dev/null || echo "sep package doesn't exist yet"
