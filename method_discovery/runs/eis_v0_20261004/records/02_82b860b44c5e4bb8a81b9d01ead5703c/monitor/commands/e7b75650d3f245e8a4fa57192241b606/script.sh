
# Check if test files would compile
cd /app && go test -c ./. 2>&1 | head -20
