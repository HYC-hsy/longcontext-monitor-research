
cd /app
# Check if the build error is fixed
go build . 2>&1
echo "---"
echo "Exit code: $?"
