
# Check Target 5 return types - should be concrete types, not ToolbarItem
cd /app/widget && grep -E "func NewToolbar(Action|Spacer|Separator)" toolbar.go

# Verify toolbar constructors return the right types
echo "=== Checking if return types match requirements ==="
