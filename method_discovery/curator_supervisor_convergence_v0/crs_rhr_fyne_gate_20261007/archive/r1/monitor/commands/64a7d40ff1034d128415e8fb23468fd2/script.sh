
# Try to build the code to see if there are compilation errors
cd /app && go build -o /tmp/test_build ./... 2>&1 | head -50
