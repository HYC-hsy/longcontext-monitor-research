
# Check current workspace state
cd /app && git status --short

# Check if build succeeds now
cd /app && go build ./... 2>&1 | head -30
