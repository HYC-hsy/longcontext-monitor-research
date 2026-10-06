
cd /app
# Try to build to see if there are any missing Metadata() implementations
go build -o /tmp/test_build ./app 2>&1 | head -20
echo "Exit code: $?"
