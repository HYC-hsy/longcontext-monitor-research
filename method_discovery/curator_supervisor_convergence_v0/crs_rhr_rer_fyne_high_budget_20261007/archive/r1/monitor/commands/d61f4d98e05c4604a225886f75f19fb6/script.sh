
# Verify all critical signatures and implementations match task specifications
cd /app

echo "=== TARGET 1: App.Metadata() in interface ==="
grep -A 2 "Metadata()" app.go | grep -v "^--$"

echo -e "\n=== TARGET 1: testApp has Metadata() ==="
grep "func (a \*testApp) Metadata()" test/testapp.go

echo -e "\n=== TARGET 2: FromJSON signature (must be string) ==="
grep "^func FromJSON" theme/json.go

echo -e "\n=== TARGET 2: Hex parsing supports 3,4,6,8 digits ==="
grep "case [0-9]:" theme/json.go | head -4

echo -e "\n=== TARGET 3: Set() with Sscanf ==="
grep -A 2 "func (b \*sprintfBinding) Set" data/binding/sprintf.go | head -4

echo -e "\n=== TARGET 3: StringToStringWithFormat exists ==="
grep "^func StringToStringWithFormat" data/binding/sprintf.go

echo -e "\n=== TARGET 4: MenuItem.Icon and MenuItem.Shortcut ==="
grep "Icon\|Shortcut" menu.go | grep -E "^\s+(Icon|Shortcut)" | head -2

echo -e "\n=== TARGET 5: Toolbar constructors return concrete types ==="
grep "^func NewToolbar" widget/toolbar.go | head -3

echo -e "\n=== TARGET 6: Container.RemoveAll exists ==="
grep "^func (c \*Container) RemoveAll" container.go

echo -e "\n=== TARGET 6: Hyperlink.OnTapped field ==="
grep "OnTapped func()" widget/hyperlink.go | head -1

echo -e "\n=== TARGET 6: Entry.SetMinRowsVisible ==="
grep "^func (e \*Entry) SetMinRowsVisible" widget/entry.go

echo -e "\n=== TARGET 6: NewAllStrings in data/validation ==="
grep "^func NewAllStrings" data/validation/all.go

echo -e "\n=== TARGET 7: desktop.App has BOTH methods ==="
grep "SetSystemTray" driver/desktop/app.go | grep "func\|SetSystemTray"
