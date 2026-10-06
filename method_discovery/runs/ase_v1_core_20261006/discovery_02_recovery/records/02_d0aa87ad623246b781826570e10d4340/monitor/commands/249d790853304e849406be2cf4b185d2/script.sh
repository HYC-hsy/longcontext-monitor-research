
# Final build verification
cd /app
go build ./... 2>&1
echo "---"
echo "Exit code: $?"
