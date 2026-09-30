
# Target 2: JSON Theme - verify FromJSON and FromJSONReader exist with correct signatures
grep -n "func FromJSON\|func FromJSONReader" /app/theme/json.go | head -5

# Target 2: Verify hex color parsing function exists
grep -n "func parseHexColor" /app/theme/json.go | head -2

# Target 3: Verify NewSprintf and StringToStringWithFormat exist
grep -n "func NewSprintf\|func StringToStringWithFormat" /app/data/binding/sprintf.go | head -5

# Target 4: Verify MenuItem has Icon and Shortcut fields
grep -n "type MenuItem struct" /app/menu.go -A 15 | grep -E "Icon|Shortcut"

# Target 4: Verify Menu and MainMenu have Refresh methods
grep -n "func.*Menu.*Refresh" /app/menu.go
