
# Check if Target 7 (desktop.App) exists
cd /app
ls -la driver/desktop/app.go 2>&1 || echo "NOT FOUND"
