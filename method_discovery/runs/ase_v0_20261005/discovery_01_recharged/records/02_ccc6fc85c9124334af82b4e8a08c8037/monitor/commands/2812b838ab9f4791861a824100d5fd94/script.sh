
# Check for test files and build setup
ls -la /app/*.go | grep -E "(test|_test)" | head -10
ls -la /app/app/ 2>/dev/null | head -10
ls -la /app/data/binding/ 2>/dev/null | head -10
ls -la /app/theme/ 2>/dev/null | head -10
