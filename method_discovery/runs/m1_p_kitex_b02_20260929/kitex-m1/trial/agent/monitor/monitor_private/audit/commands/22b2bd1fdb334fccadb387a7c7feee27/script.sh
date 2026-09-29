
# Check for any new files or modifications since the repo baseline
find /app/pkg/streaming -name "*.go" -type f | wc -l
find /app/pkg/endpoint -name "*.go" -type f | wc -l
# Check if cep/sep exist
test -d /app/pkg/endpoint/cep && echo "cep exists" || echo "cep not created"
test -d /app/pkg/endpoint/sep && echo "sep exists" || echo "sep not created"
