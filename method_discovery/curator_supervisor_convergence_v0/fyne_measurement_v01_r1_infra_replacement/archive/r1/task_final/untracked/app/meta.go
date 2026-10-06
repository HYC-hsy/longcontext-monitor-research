package app

import "fyne.io/fyne/v2"

var appMetadata = fyne.AppMetadata{
	ID:      "com.example",
	Name:    "Fyne App",
	Version: "1.0.0",
	Build:   1,
}

// SetMetadata allows an application to override the default metadata at runtime.
// This is typically called early in the application lifecycle, before the app starts.
//
// Since: 2.2
func SetMetadata(meta fyne.AppMetadata) {
	appMetadata = meta
}
