
# Verify all 6 targets - quick compilation check
echo "=== Verifying full build succeeds ==="
cd /app && go build ./... 2>&1 | head -30
