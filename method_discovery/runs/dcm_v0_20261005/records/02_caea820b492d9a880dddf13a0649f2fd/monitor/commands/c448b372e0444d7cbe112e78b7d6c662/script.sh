cd /app && {
  echo "=== Checking NewAllStrings validator exists ==="
  grep -n "func NewAllStrings" data/validation/string.go 2>&1 || echo "NOT FOUND"
  
  echo -e "\n=== Checking StringToStringWithFormat optimization ==="
  grep -A 5 'func StringToStringWithFormat' data/binding/sprintf.go | head -10
  
  echo -e "\n=== Checking Entry.SetMinRowsVisible implementation ==="
  grep -A 8 'func.*SetMinRowsVisible' widget/entry.go | head -12
  
  echo -e "\n=== Verifying toolbar return types ==="
  grep '^func NewToolbarAction' widget/toolbar.go
  grep '^func NewToolbarSpacer' widget/toolbar.go
  grep '^func NewToolbarSeparator' widget/toolbar.go
}