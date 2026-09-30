
# Verify SetSystemTrayIcon was added to desktop.App interface
cat /app/driver/desktop/app.go

# Verify build still passes
cd /app && go build ./... 2>&1 | head -10
echo "Build exit code: $?"
