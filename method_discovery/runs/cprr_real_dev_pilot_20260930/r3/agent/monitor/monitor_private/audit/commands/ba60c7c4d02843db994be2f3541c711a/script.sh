
# Check if tests are passing now
cd /app && go test ./client/... 2>&1 | tail -30
