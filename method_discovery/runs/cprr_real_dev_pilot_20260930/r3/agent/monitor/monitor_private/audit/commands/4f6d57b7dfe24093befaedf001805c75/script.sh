
# Verify tests are passing
cd /app && go test ./client/... ./server/... 2>&1 | tail -15
