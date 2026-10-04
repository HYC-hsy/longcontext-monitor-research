
# Check what files have been created in endpoint package
ls -la /app/pkg/endpoint/
echo "---"
ls -la /app/pkg/endpoint/cep/ 2>/dev/null || echo "cep not found"
echo "---"
ls -la /app/pkg/endpoint/sep/ 2>/dev/null || echo "sep not found"
