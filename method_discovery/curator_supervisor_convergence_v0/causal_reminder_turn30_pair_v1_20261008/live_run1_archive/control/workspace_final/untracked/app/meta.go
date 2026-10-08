package app

import "fyne.io/fyne/v2"

var appMetadata = fyne.AppMetadata{
	ID:      "com.example",
	Name:    "Fyne App",
	Version: "1.0.0",
	Build:   1,
}

// SetMetadata allows an application to override its build-time metadata at runtime.
// This is typically used to set the app's ID, name, version, and build number
// before calling app.New() or app.NewWithID().
//
// Since: 2.2
func SetMetadata(m fyne.AppMetadata) {
	appMetadata = m
}
