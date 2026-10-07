package desktop

import "fyne.io/fyne/v2"

// App interface extends fyne.App to add desktop-specific functionality.
// Desktop applications can implement this interface to provide system tray support.
//
// Since: 2.2
type App interface {
	fyne.App

	// SetSystemTrayMenu sets the menu to be displayed when the system tray icon is clicked.
	// Pass nil to remove the system tray icon.
	SetSystemTrayMenu(menu *fyne.Menu)

	// SetSystemTrayIcon sets the icon to display in the system tray.
	// This should be called after SetSystemTrayMenu to customize the tray icon.
	SetSystemTrayIcon(icon fyne.Resource)
}
