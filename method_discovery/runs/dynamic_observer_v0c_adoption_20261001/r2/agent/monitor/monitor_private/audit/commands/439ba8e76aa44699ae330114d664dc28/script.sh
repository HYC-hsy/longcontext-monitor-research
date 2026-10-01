
# Check if deprecated.go was created and old files removed
ls -la /app/pkg/endpoint/ 2>&1
echo "---"
# Check git status
cd /app && git status --short 2>&1 | head -20
