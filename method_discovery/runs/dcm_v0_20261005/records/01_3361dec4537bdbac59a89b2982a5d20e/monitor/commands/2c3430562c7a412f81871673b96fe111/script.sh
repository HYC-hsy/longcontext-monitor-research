
# Verify Target 7 fix - desktop.App should now have BOTH methods
cd /app
echo "=== Target 7: desktop.App Interface (should have 2 methods) ===" && \
grep -A20 "type App interface" driver/desktop/app.go
