// Package desktop provides desktop-specific app functionality.
package desktop

import "fyne.io/fyne/v2"

// App represents a desktop application with extended capabilities
// beyond the standard fyne.App interface.
//
// Since: 2.2
type App interface {
	fyne.App

	// SystemTrayMenu returns the menu that is displayed when the system tray icon is right-clicked.
	// Returns nil if no system tray menu has been set.
	SystemTrayMenu() *fyne.Menu

	// SetSystemTrayMenu sets the menu to be displayed when the system tray icon is right-clicked.
	// Pass nil to remove the system tray menu.
	SetSystemTrayMenu(menu *fyne.Menu)

	// SetSystemTrayIcon sets the icon displayed in the system tray.
	// Pass nil to use the default application icon.
	SetSystemTrayIcon(icon fyne.Resource)
}
