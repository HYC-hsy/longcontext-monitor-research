
# Check client option files
ls -la /app/client/ | grep -i option
echo "---"
# Check internal/client for option types
find /app/internal/client -name "*.go" 2>/dev/null | head -5
