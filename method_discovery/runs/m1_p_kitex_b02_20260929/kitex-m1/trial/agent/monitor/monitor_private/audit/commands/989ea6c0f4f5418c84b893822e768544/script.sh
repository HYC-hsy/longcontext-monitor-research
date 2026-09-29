
# Check if new files have been created for the targets
ls -la /app/pkg/endpoint/cep 2>/dev/null || echo "cep not created"
ls -la /app/pkg/endpoint/sep 2>/dev/null || echo "sep not created"
find /app/pkg/streaming -name "*.go" -newer /app/pkg/streaming/streaming.go 2>/dev/null | head -5
