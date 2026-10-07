package app

import (
	"fyne.io/fyne/v2"
)

var appMetadata = fyne.AppMetadata{
	ID:      "com.example",
	Name:    "Fyne App",
	Version: "1.0.0",
	Build:   1,
}

// SetMetadata sets the application metadata that will be returned by App.Metadata().
// This allows overriding the packaged metadata at runtime.
//
// Since: 2.5
func SetMetadata(meta fyne.AppMetadata) {
	appMetadata = meta
}
