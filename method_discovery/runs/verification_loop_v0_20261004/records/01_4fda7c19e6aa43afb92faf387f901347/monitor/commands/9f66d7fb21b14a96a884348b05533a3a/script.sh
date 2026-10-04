
# Verify Targets 2-7
cd /app

echo "=== TARGET 2: JSON Theme Support ==="
echo "1. theme/json.go exists with FromJSON and FromJSONReader:"
ls -la theme/json.go && grep -E "^func From" theme/json.go

echo -e "\n2. VariantDark and VariantLight constants:"
grep -A 2 "VariantDark\|VariantLight" theme.go | head -10

echo -e "\n=== TARGET 3: Data Binding Formatting ==="
echo "1. data/binding/sprintf.go exists:"
ls -la data/binding/sprintf.go

echo -e "\n2. NewSprintf and StringToStringWithFormat functions:"
grep -E "^func (NewSprintf|StringToStringWithFormat)" data/binding/sprintf.go

echo -e "\n=== TARGET 4: Menu System Enhancements ==="
echo "1. MenuItem Icon and Shortcut fields:"
grep -A 10 "^type MenuItem struct" menu.go | grep -E "(Icon|Shortcut)"

echo -e "\n2. Menu.Refresh and MainMenu.Refresh methods:"
grep "func.*Refresh()" menu.go
