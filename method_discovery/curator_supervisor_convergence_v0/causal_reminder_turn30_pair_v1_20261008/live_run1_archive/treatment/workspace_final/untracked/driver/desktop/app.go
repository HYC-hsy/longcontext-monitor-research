// Package desktop provides desktop-specific driver extensions
package desktop

import "fyne.io/fyne/v2"

// App defines the desktop-specific extensions to the standard fyne.App interface.
// Desktop applications can implement this interface to provide additional platform-specific
// features such as system tray integration, dock menu customization, and other
// desktop environment interactions.
//
// Since: 2.2
type App interface {
	fyne.App

	// SetSystemTrayMenu sets the system tray menu for this application.
	// The menu will be shown when the user interacts with the app's system tray icon.
	// Pass nil to remove the system tray menu.
	SetSystemTrayMenu(menu *fyne.Menu)

	// SetSystemTrayIcon sets the icon to display in the system tray.
	// If not set or set to nil, a default icon may be used.
	SetSystemTrayIcon(icon fyne.Resource)
}
