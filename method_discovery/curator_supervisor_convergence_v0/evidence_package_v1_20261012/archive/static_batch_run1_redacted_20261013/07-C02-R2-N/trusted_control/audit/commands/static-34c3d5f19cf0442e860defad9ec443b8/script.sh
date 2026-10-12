
# Check for Menu.Refresh and MainMenu.Refresh methods
cd /app && grep -A 3 "func (m \*Menu) Refresh\|func (m \*MainMenu) Refresh" menu.go
