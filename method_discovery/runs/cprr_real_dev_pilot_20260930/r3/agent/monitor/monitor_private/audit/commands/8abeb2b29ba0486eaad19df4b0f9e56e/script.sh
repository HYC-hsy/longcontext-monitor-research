
# Check final build status
cd /app && go build ./... 2>&1 | head -10
