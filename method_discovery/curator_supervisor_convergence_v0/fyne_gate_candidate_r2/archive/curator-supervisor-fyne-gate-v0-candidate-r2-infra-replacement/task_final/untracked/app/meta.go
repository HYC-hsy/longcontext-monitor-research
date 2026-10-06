package app

import "fyne.io/fyne/v2"

// NewWithMetadata creates a new app instance with the specified metadata.
// The metadata includes application ID, name, version, build number, and icon.
// The ID is used for application preferences and storage paths.
//
// Since: 2.2
func NewWithMetadata(meta fyne.AppMetadata) fyne.App {
	a := NewWithID(meta.ID).(*fyneApp)
	a.metadata = meta
	
	// Set icon from metadata if provided
	if meta.Icon != nil {
		a.SetIcon(meta.Icon)
	}
	
	return a
}

// SetMetadata updates the metadata of the current application at runtime.
// This allows overriding the packaged metadata after the app has been created.
//
// Since: 2.2
func SetMetadata(meta fyne.AppMetadata) {
	app := fyne.CurrentApp()
	if a, ok := app.(*fyneApp); ok {
		a.metadata = meta
		if meta.Icon != nil {
			a.SetIcon(meta.Icon)
		}
	}
}
