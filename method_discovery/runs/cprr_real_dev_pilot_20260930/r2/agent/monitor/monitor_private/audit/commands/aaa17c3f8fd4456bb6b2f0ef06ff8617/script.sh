
# Target 5: Verify ToolbarAction.SetIcon exists (critical requirement)
grep -n "func.*ToolbarAction.*SetIcon" /app/widget/toolbar.go

# Target 7: Check complete desktop.App interface - CRITICAL: should have SetSystemTrayIcon too
cat /app/driver/desktop/app.go
