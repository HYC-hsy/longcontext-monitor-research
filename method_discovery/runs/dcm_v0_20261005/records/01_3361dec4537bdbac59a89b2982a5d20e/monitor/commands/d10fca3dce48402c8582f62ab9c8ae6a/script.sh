
# Verify Target 7 - desktop.App interface
cd /app
grep -A10 "type App interface" driver/desktop/app.go 2>&1
