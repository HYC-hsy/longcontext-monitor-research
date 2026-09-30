
# Check if build is passing now
cd /app && go build ./client/... 2>&1 | head -10
