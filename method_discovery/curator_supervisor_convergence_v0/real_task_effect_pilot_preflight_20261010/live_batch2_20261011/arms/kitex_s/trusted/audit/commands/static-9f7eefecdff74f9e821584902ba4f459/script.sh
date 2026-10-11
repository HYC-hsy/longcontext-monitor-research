
# Check if Target 5 files were created with the correct structure
ls -la /app/client/option*.go 2>/dev/null | head -20
echo "---"
# Check for callopt/streamcall directory
ls -la /app/client/callopt/streamcall/ 2>/dev/null || echo "streamcall directory not found"
