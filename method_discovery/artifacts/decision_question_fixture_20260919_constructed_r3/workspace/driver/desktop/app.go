package desktop

import "fyne.io/fyne/v2"

// App defines desktop specific extensions to a fyne.App.
//
// Since: 2.5
type App interface {
	fyne.App

	// SetSystemTrayMenu sets the menu that will be displayed when the system tray icon is right-clicked.
	// On systems that do not support system tray, this will be a no-op.
	SetSystemTrayMenu(menu *fyne.Menu)

	// SetSystemTrayIcon sets the icon that will be displayed in the system tray.
	// If not set, the default application icon will be used.
	// On systems that do not support system tray, this will be a no-op.
	SetSystemTrayIcon(icon fyne.Resource)
}
