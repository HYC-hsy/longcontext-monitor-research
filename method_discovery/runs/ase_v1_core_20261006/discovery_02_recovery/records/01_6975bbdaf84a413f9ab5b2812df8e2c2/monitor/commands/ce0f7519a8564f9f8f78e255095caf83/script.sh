
# Run complete build verification
echo "=== COMPLETE BUILD VERIFICATION ==="
cd /app && go build ./... 2>&1 | grep -E "(^#|error)" | head -20
