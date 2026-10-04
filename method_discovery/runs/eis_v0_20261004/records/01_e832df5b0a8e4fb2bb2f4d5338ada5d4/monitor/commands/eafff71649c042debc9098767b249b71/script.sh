
# Try to build to see if there are compilation errors
cd /app && go build ./... 2>&1 | head -30
