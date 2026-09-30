
# Check if build is passing now
cd /app && go build ./... 2>&1 | head -20
