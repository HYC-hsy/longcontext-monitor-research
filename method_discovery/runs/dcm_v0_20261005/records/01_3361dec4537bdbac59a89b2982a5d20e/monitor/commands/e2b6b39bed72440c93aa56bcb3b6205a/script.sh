
# Verify Target 7 - desktop.App interface (must have BOTH SetSystemTrayMenu AND SetSystemTrayIcon)
cd /app
echo "=== Target 7: desktop.App Interface ===" && \
grep -A15 "type App interface" driver/desktop/app.go
