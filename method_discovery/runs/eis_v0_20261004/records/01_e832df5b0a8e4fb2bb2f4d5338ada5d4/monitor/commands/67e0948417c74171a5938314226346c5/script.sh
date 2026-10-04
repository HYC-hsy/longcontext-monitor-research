
# Verify the correction compiles
cd /app && go test -c ./test/ 2>&1 | head -20
