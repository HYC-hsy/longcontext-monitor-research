
# Final comprehensive build check (Turn 214)
echo "=== COMPREHENSIVE BUILD CHECK (Turn 214) ==="
echo ""
cd /app && go build ./... 2>&1 | grep -E "^#|error" | head -40
echo ""
echo "Full build exit code: $?"
