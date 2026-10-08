package desktop

import "fyne.io/fyne/v2"

// App defines the desktop-specific extension to the fyne.App interface.
// This interface adds methods that are specific to desktop platforms like
// system tray integration and window management features.
//
// Since: 2.2
type App interface {
	fyne.App

	// SetSystemTrayMenu sets the menu that appears when the system tray icon is clicked.
	// On platforms that support system trays (Windows, macOS, Linux with appropriate desktop environments),
	// this will create or update the system tray icon and its associated menu.
	//
	// Since: 2.2
	SetSystemTrayMenu(menu *fyne.Menu)

	// SetSystemTrayIcon sets the icon to display in the system tray.
	// If no icon is set, a default icon will be used.
	//
	// Since: 2.2
	SetSystemTrayIcon(icon fyne.Resource)
}
