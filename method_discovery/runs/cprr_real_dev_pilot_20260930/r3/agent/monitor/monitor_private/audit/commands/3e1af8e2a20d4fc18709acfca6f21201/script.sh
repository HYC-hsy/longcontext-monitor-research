
# Check current status of Target 5 option files
ls -la /app/client/option_*.go 2>&1
echo -e "\n=== Check for callopt/streamcall ==="
ls -la /app/client/callopt/streamcall/ 2>&1 | head -5
