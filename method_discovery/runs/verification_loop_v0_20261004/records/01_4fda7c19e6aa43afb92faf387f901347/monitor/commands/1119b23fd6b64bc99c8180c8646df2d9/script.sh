
# Verify build actually passes
cd /app
go build ./... 2>&1
echo "Exit code: $?"
