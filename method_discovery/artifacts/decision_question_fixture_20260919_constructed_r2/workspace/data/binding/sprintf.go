package binding

import (
	"fmt"
)

// sprintf is a String binding that formats multiple source bindings using fmt.Sprintf.
type sprintf struct {
	base

	format  string
	sources []DataItem
}

// NewSprintf returns a new String binding that formats its value using fmt.Sprintf
// with the given format string and source bindings. The binding updates whenever any
// of the source bindings change.
//
// Example:
//   name := binding.NewString()
//   age := binding.NewInt()
//   formatted := binding.NewSprintf("Name: %s, Age: %d", name, age)
//
// Since: 2.5
func NewSprintf(format string, sources ...DataItem) String {
	s := &sprintf{
		format:  format,
		sources: sources,
	}

	// Listen to all source bindings
	for _, source := range sources {
		source.AddListener(NewDataListener(func() {
			s.trigger()
		}))
	}

	return s
}

func (s *sprintf) Get() (string, error) {
	values := make([]interface{}, len(s.sources))
	
	for i, source := range s.sources {
		switch v := source.(type) {
		case String:
			val, err := v.Get()
			if err != nil {
				return "", err
			}
			values[i] = val
		case Int:
			val, err := v.Get()
			if err != nil {
				return "", err
			}
			values[i] = val
		case Float:
			val, err := v.Get()
			if err != nil {
				return "", err
			}
			values[i] = val
		case Bool:
			val, err := v.Get()
			if err != nil {
				return "", err
			}
			values[i] = val
		case Untyped:
			val, err := v.Get()
			if err != nil {
				return "", err
			}
			values[i] = val
		default:
			// For any other DataItem type, try to get as Untyped
			if u, ok := source.(Untyped); ok {
				val, err := u.Get()
				if err != nil {
					return "", err
				}
				values[i] = val
			} else {
				values[i] = fmt.Sprintf("%v", source)
			}
		}
	}

	return fmt.Sprintf(s.format, values...), nil
}

func (s *sprintf) Set(string) error {
	// sprintf bindings are read-only
	return nil
}

// stringToStringWithFormat creates a String binding that formats another String binding.
type stringToStringWithFormat struct {
	base

	format string
	source String
}

// StringToStringWithFormat creates a binding that converts a string to a formatted string.
// The format string should contain one %s, %v, or similar format verb for the source string.
//
// Example:
//   name := binding.NewString()
//   name.Set("Alice")
//   formatted := binding.StringToStringWithFormat(name, "Hello, %s!")
//   // formatted.Get() returns "Hello, Alice!"
//
// Since: 2.5
func StringToStringWithFormat(source String, format string) String {
	s := &stringToStringWithFormat{
		format: format,
		source: source,
	}

	source.AddListener(NewDataListener(func() {
		s.trigger()
	}))

	return s
}

func (s *stringToStringWithFormat) Get() (string, error) {
	val, err := s.source.Get()
	if err != nil {
		return "", err
	}

	return fmt.Sprintf(s.format, val), nil
}

func (s *stringToStringWithFormat) Set(string) error {
	// Formatted bindings are read-only
	return nil
}
