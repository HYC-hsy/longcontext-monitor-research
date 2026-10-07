
# Verify compilation now succeeds
cd /app && go build ./test 2>&1
echo "Exit code: $?"
