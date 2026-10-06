
cd /app
# Check if everything still builds
go build . 2>&1 | head -20
echo "---"
echo "Exit code: $?"
