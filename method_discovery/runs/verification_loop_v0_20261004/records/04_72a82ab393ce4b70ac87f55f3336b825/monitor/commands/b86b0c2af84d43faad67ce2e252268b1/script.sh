
# Quick final verification that build is still successful
cd /app
go build ./... 2>&1 | head -5
echo ""
echo "Exit code: $?"
