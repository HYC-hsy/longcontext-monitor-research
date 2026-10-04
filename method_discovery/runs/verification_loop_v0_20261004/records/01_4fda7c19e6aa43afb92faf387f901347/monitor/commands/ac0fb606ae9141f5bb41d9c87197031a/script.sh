
# Check if widget/validation.go still exists or was removed
cd /app
ls -la widget/validation.go 2>&1 || echo "REMOVED"
