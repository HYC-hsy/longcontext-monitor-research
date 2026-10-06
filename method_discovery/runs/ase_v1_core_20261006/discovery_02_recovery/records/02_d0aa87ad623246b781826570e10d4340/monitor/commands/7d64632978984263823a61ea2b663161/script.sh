
# Full build to see all errors
cd /app
go build . 2>&1
echo "---"
echo "Exit code: $?"
