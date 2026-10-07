package binding

import (
	"fmt"
	"sync"
)

// sprintfBinding is a String binding that formats multiple data items using a format string.
type sprintfBinding struct {
	base
	format  string
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
		format:  format,
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

// Set parses the string back using fmt.Sscanf and sets each source binding to the parsed value.
// The format string is used to extract values which are then set on the corresponding source bindings.
//
// Since: 2.2
func (b *sprintfBinding) Set(str string) error {
	b.lock.Lock()
	defer b.lock.Unlock()

	// Create destination pointers for Sscanf based on source types
	values := make([]interface{}, len(b.sources))
	for i, source := range b.sources {
		switch source.(type) {
		case String:
			var s string
			values[i] = &s
		case Int:
			var n int
			values[i] = &n
		case Float:
			var f float64
			values[i] = &f
		case Bool:
			var bo bool
			values[i] = &bo
		default:
			// For other types, use interface{}
			var v interface{}
			values[i] = &v
		}
	}

	// Parse the string using the format
	n, err := fmt.Sscanf(str, b.format, values...)
	if err != nil {
		return fmt.Errorf("failed to parse sprintf binding value: %w", err)
	}
	if n != len(b.sources) {
		return fmt.Errorf("parsed %d values but expected %d", n, len(b.sources))
	}

	// Set the parsed values back to sources
	for i, source := range b.sources {
		switch s := source.(type) {
		case String:
			if strVal, ok := values[i].(*string); ok {
				if err := s.Set(*strVal); err != nil {
					return err
				}
			}
		case Int:
			if intVal, ok := values[i].(*int); ok {
				if err := s.Set(*intVal); err != nil {
					return err
				}
			}
		case Float:
			if floatVal, ok := values[i].(*float64); ok {
				if err := s.Set(*floatVal); err != nil {
					return err
				}
			}
		case Bool:
			if boolVal, ok := values[i].(*bool); ok {
				if err := s.Set(*boolVal); err != nil {
					return err
				}
			}
		case Untyped:
			if untypedVal, ok := values[i].(*interface{}); ok {
				if err := s.Set(*untypedVal); err != nil {
					return err
				}
			}
		}
	}

	return nil
}

// stringToStringWithFormat is a String binding that applies a format transformation to another String binding.
type stringToStringWithFormat struct {
	base
	format string
	source String

	lock sync.RWMutex
}

// StringToStringWithFormat creates a new String binding that formats another String binding value
// using the provided format string. The format string should contain exactly one %s placeholder.
//
// Example:
//   name := binding.NewString()
//   name.Set("Alice")
//   greeting := binding.StringToStringWithFormat(name, "Hello, %s!")
//   // greeting.Get() returns "Hello, Alice!"
//
// Since: 2.2
func StringToStringWithFormat(str String, format string) String {
	b := &stringToStringWithFormat{
		format: format,
		source: str,
	}

	// Listen to source changes
	str.AddListener(b)

	return b
}

// DataChanged is called when the source string changes.
func (b *stringToStringWithFormat) DataChanged() {
	b.trigger()
}

// Get returns the formatted string value.
func (b *stringToStringWithFormat) Get() (string, error) {
	b.lock.RLock()
	defer b.lock.RUnlock()

	val, err := b.source.Get()
	if err != nil {
		return "", err
	}

	return fmt.Sprintf(b.format, val), nil
}

// Set parses the formatted string back to extract the original value and sets it on the source.
func (b *stringToStringWithFormat) Set(str string) error {
	b.lock.Lock()
	defer b.lock.Unlock()

	var val string
	n, err := fmt.Sscanf(str, b.format, &val)
	if err != nil {
		return fmt.Errorf("failed to parse formatted string: %w", err)
	}
	if n != 1 {
		return fmt.Errorf("expected to parse 1 value but got %d", n)
	}

	return b.source.Set(val)
}
