
# Check if testApp actually implements App interface by looking at its usage
grep -n "NewApp\|testApp" /app/test/testapp.go | head -20

# More comprehensive build to see all errors
cd /app && go build ./test 2>&1 | head -20
