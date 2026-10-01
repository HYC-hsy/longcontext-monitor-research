
# Check if MainMenu has Refresh method
grep -A 3 "type MainMenu struct" /app/menu.go
grep -n "func.*MainMenu.*Refresh" /app/menu.go
