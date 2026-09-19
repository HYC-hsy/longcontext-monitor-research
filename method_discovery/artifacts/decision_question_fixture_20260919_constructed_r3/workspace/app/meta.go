package app

import "fyne.io/fyne/v2"

var metadata = fyne.AppMetadata{
	ID:      "com.example",
	Name:    "Fyne App",
	Version: "1.0.0",
	Build:   1,
}

// SetMetadata sets the application metadata that will be returned by App.Metadata().
// This allows applications to override the default metadata at runtime.
//
// Since: 2.5
func SetMetadata(m fyne.AppMetadata) {
	metadata = m
}
