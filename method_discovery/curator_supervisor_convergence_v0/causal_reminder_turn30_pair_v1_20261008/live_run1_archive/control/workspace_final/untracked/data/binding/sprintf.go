package binding

import (
	"fmt"
	"sync"
)

// sprintfBinding is a String binding that formats multiple data items using a format string.
type sprintfBinding struct {
	base
	format string
	sources []DataItem
	
	lock sync.RWMutex
}

// NewSprintf creates a new String binding that formats its value using fmt.Sprintf.
// The format string and data sources are provided, and the binding updates whenever
// any source data changes.
//
// Example:
//   name := binding.NewString()
//   age := binding.NewInt()
//   formatted := binding.NewSprintf("Name: %s, Age: %d", name, age)
//
// Since: 2.2
func NewSprintf(format string, sources ...DataItem) String {
	b := &sprintfBinding{
		format: format,
		sources: sources,
	}
	
	// Listen to all source data items
	for _, source := range sources {
		source.AddListener(b)
	}
	
	return b
}

// DataChanged is called when any of the source data items change.
// It triggers a refresh of the formatted string.
func (b *sprintfBinding) DataChanged() {
	b.trigger()
}

// Get returns the current formatted string value.
func (b *sprintfBinding) Get() (string, error) {
	b.lock.RLock()
	defer b.lock.RUnlock()
	
	// Extract values from all sources
	values := make([]interface{}, len(b.sources))
	for i, source := range b.sources {
		switch s := source.(type) {
		case String:
			if val, err := s.Get(); err == nil {
				values[i] = val
			} else {
				return "", err
			}
		case Int:
			if val, err := s.Get(); err == nil {
				values[i] = val
			} else {
				return "", err
			}
		case Float:
			if val, err := s.Get(); err == nil {
				values[i] = val
			} else {
				return "", err
			}
		case Bool:
			if val, err := s.Get(); err == nil {
				values[i] = val
			} else {
				return "", err
			}
		case Untyped:
			if val, err := s.Get(); err == nil {
				values[i] = val
			} else {
				return "", err
			}
		default:
			// For any other type, try Untyped interface
			if u, ok := source.(Untyped); ok {
				if val, err := u.Get(); err == nil {
					values[i] = val
				} else {
					return "", err
				}
			} else {
				values[i] = nil
			}
		}
	}
	
	return fmt.Sprintf(b.format, values...), nil
}

// Set is not supported for sprintf bindings as they are computed from sources.
func (b *sprintfBinding) Set(string) error {
	return fmt.Errorf("cannot set value on sprintf binding")
}
