
# Check current compilation status
cd /app && go build ./... 2>&1 | head -40
