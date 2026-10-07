package desktop

import "fyne.io/fyne/v2"

// App represents a desktop application with extended capabilities beyond the standard fyne.App.
// This interface adds desktop-specific functionality like system tray icon and menu management.
//
// Since: 2.5
type App interface {
	fyne.App
	
	// SetSystemTrayMenu sets the system tray menu for the application.
	// On supported desktop platforms (Windows, macOS, Linux with system tray support),
	// this will create or update a menu in the system tray/notification area.
	// The menu parameter can be nil to remove the system tray menu.
	//
	// Note: Not all desktop environments support system tray menus.
	// On unsupported platforms, this method may have no effect.
	//
	// Since: 2.5
	SetSystemTrayMenu(menu *fyne.Menu)
	
	// SetSystemTrayIcon sets the icon for the system tray.
	// This icon will be displayed in the operating system's system tray/notification area.
	// The icon parameter should be a fyne.Resource containing the icon image data.
	//
	// If called before SetSystemTrayMenu, the icon will be used when the menu is set.
	// If called after SetSystemTrayMenu, it updates the existing tray icon.
	//
	// Note: Not all desktop environments support system tray icons.
	// On unsupported platforms, this method may have no effect.
	//
	// Since: 2.5
	SetSystemTrayIcon(icon fyne.Resource)
}
