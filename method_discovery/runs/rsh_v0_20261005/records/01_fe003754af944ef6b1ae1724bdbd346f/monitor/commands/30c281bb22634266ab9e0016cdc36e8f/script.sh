
echo "=== Target 2: JSON Theme Support ==="
echo "1. theme/fromjson.go exists:"
ls -la /app/theme/fromjson.go 2>&1 | grep fromjson

echo -e "\n2. FromJSON and FromJSONReader functions:"
grep -n "^func FromJSON" /app/theme/fromjson.go

echo -e "\n=== Target 3: Data Binding Formatting ==="
echo "1. data/binding/sprintf.go exists:"
ls -la /app/data/binding/sprintf.go 2>&1 | grep sprintf

echo -e "\n2. NewSprintf function:"
grep -n "^func NewSprintf" /app/data/binding/sprintf.go

echo -e "\n3. StringToStringWithFormat function:"
grep -n "^func StringToStringWithFormat" /app/data/binding/sprintf.go

echo -e "\n=== Target 4: Menu System Enhancements ==="
echo "1. MenuItem fields (Icon and Shortcut):"
grep -A 2 "Icon.*Resource" /app/menu.go | head -3
grep -A 2 "Shortcut.*Shortcut" /app/menu.go | head -3

echo -e "\n2. Menu.Refresh() method:"
grep -n "func.*Menu.*Refresh" /app/menu.go

echo -e "\n3. MainMenu.Refresh() method:"
grep -n "func.*MainMenu.*Refresh" /app/menu.go
