
# Check if build is passing
cd /app && go build ./client/... 2>&1 | tail -10
