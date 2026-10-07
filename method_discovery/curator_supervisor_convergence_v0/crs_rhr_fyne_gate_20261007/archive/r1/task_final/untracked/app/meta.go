package app

import (
	"sync"

	"fyne.io/fyne/v2"
)

var (
	appMetadata     fyne.AppMetadata
	appMetadataLock sync.RWMutex
)

func init() {
	// Set default metadata
	appMetadata = fyne.AppMetadata{
		ID:      "com.example",
		Name:    "Fyne App",
		Version: "1.0.0",
		Build:   1,
	}
}

// SetMetadata overrides the application metadata at runtime.
// This allows applications to specify their identity, version, and build information.
//
// Since: 2.2
func SetMetadata(m fyne.AppMetadata) {
	appMetadataLock.Lock()
	defer appMetadataLock.Unlock()
	appMetadata = m
}

// GetMetadata returns the current application metadata.
// This is used internally by fyneApp to implement the Metadata() method.
func GetMetadata() fyne.AppMetadata {
	appMetadataLock.RLock()
	defer appMetadataLock.RUnlock()
	return appMetadata
}
