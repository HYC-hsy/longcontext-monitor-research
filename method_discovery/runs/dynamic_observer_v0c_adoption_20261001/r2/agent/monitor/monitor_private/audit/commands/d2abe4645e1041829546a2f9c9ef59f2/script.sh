
# Check if any new files were created in pkg/streaming, pkg/endpoint/cep, pkg/endpoint/sep
ls -la /app/pkg/streaming/ 2>&1
echo "---"
ls -la /app/pkg/endpoint/cep/ 2>&1
echo "---"
ls -la /app/pkg/endpoint/sep/ 2>&1
echo "---"
# Check git status for any changes
cd /app && git status --short 2>&1 | head -20
