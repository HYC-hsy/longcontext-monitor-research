
# Check current build errors
cd /app && go build ./... 2>&1 | grep -E "^#|\.go:[0-9]+" | head -20
