
# Try to build endpoint packages to check current status
cd /app && go build ./pkg/endpoint/cep 2>&1 | head -20
