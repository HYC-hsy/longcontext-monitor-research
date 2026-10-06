
cd /app
# Check if theme package builds
go build ./theme 2>&1 | head -10
echo "---"
echo "Exit code: $?"
