
# Check what new files have been created
ls -la /app/pkg/streaming/*.go
echo "---"
test -d /app/pkg/endpoint/cep && ls -la /app/pkg/endpoint/cep/ || echo "cep not yet created"
test -d /app/pkg/endpoint/sep && ls -la /app/pkg/endpoint/sep/ || echo "sep not yet created"
