// Package desktop provides desktop-specific driver features
package desktop

import "fyne.io/fyne/v2"

// App defines an extension interface to fyne.App that also provides desktop-specific functionality.
// Desktop applications can use this interface to access additional features like system tray menus and icons.
//
// Since: 2.2
type App interface {
	fyne.App

	// SetSystemTrayMenu sets a menu to be displayed when the system tray icon is right-clicked.
	// This is typically used for applications that minimize to the system tray.
	// Passing nil will remove any existing system tray menu.
	SetSystemTrayMenu(menu *fyne.Menu)

	// SetSystemTrayIcon sets a custom icon for the system tray.
	// This allows applications to display a different icon in the system tray
	// than the main application icon.
	SetSystemTrayIcon(icon fyne.Resource)
}
