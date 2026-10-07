
# Check Menu.Refresh and MainMenu.Refresh
cd /app && grep -A 5 "func (m \*Menu) Refresh\|func (m \*MainMenu) Refresh" menu.go
