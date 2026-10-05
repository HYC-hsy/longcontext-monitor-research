
# Run a full build to check all packages compile
cd /app && go build ./... 2>&1 | head -50
