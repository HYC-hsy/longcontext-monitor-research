
# Check menu.go for MenuItem Icon and Shortcut fields
cd /app && grep -B 3 -A 15 "type MenuItem struct" menu.go
