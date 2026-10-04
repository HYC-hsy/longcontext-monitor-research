
# Final compilation check
cd /app
echo "=== FULL CODEBASE BUILD ===" && go build ./... 2>&1 | head -20 || echo "Exit code: $?"
