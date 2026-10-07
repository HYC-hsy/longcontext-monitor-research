package desktop

import "fyne.io/fyne/v2"

// App interface extends fyne.App with desktop-specific functionality.
// This interface defines additional methods for desktop platforms such as
// system tray integration.
//
// Since: 2.2
type App interface {
	fyne.App

	// SetSystemTrayMenu sets the system tray menu for the application.
	// This allows the application to add a menu to the system tray/notification area.
	// Pass nil to remove the system tray menu.
	//
	// Since: 2.2
	SetSystemTrayMenu(menu *fyne.Menu)

	// SetSystemTrayIcon sets the system tray icon for the application.
	// This allows the application to display an icon in the system tray/notification area.
	// Pass nil to remove the system tray icon.
	//
	// Since: 2.2
	SetSystemTrayIcon(icon fyne.Resource)
}
