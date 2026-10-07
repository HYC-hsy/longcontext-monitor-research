package binding

import (
	"fmt"
	
	"fyne.io/fyne/v2/storage"
)

// stringFormat is a String binding that formats its value using fmt.Sprintf
type stringFormat struct {
	base
	
	format  string
	sources []DataItem
}

// NewSprintf creates a new String binding that formats multiple source bindings using fmt.Sprintf.
// The format string follows the same rules as fmt.Sprintf, and sources are the bindings to be formatted.
// 
// Setting a value will attempt to parse it back using fmt.Sscanf and update the source bindings.
// When any source binding changes, the formatted string is automatically recalculated.
//
// Since: 2.5
func NewSprintf(format string, sources ...DataItem) String {
	s := &stringFormat{
		format:  format,
		sources: sources,
	}
	
	// Listen to all source bindings for changes
	listener := NewDataListener(func() {
		s.trigger()
	})
	
	for _, source := range sources {
		if source != nil {
			source.AddListener(listener)
		}
	}
	
	return s
}

// StringToStringWithFormat creates a formatted String binding from another String binding.
// This is a convenience function for the common case of formatting a single string value.
//
// Since: 2.5
func StringToStringWithFormat(str String, format string) String {
	return NewSprintf(format, str)
}

func (s *stringFormat) Get() (string, error) {
	values := make([]interface{}, 0, len(s.sources))
	
	for _, source := range s.sources {
		if source == nil {
			values = append(values, nil)
			continue
		}
		
		// Type assert to extract the actual value
		switch typed := source.(type) {
		case String:
			if val, err := typed.Get(); err == nil {
				values = append(values, val)
			} else {
				values = append(values, "")
			}
		case Bool:
			if val, err := typed.Get(); err == nil {
				values = append(values, val)
			} else {
				values = append(values, false)
			}
		case Int:
			if val, err := typed.Get(); err == nil {
				values = append(values, val)
			} else {
				values = append(values, 0)
			}
		case Float:
			if val, err := typed.Get(); err == nil {
				values = append(values, val)
			} else {
				values = append(values, 0.0)
			}
		case Rune:
			if val, err := typed.Get(); err == nil {
				values = append(values, val)
			} else {
				values = append(values, rune(0))
			}
		case URI:
			if val, err := typed.Get(); err == nil {
				values = append(values, val.String())
			} else {
				values = append(values, "")
			}
		case Untyped:
			if val, err := typed.Get(); err == nil {
				values = append(values, val)
			} else {
				values = append(values, nil)
			}
		default:
			// Unknown type, use nil
			values = append(values, nil)
		}
	}
	
	return fmt.Sprintf(s.format, values...), nil
}

func (s *stringFormat) Set(value string) error {
	// Attempt to parse the formatted string back to source values
	if len(s.sources) == 0 {
		return fmt.Errorf("no source bindings to set")
	}
	
	// Create temporary variables for scanning
	vars := make([]interface{}, 0, len(s.sources))
	
	for _, source := range s.sources {
		if source == nil {
			return fmt.Errorf("cannot set value with nil source binding")
		}
		
		switch source.(type) {
		case String:
			var str string
			vars = append(vars, &str)
		case Bool:
			var b bool
			vars = append(vars, &b)
		case Int:
			var i int
			vars = append(vars, &i)
		case Float:
			var f float64
			vars = append(vars, &f)
		case Rune:
			var r rune
			vars = append(vars, &r)
		case URI:
			var str string
			vars = append(vars, &str)
		case Untyped:
			var v interface{}
			vars = append(vars, &v)
		default:
			return fmt.Errorf("unsupported binding type for Set")
		}
	}
	
	// Parse using fmt.Sscanf
	n, err := fmt.Sscanf(value, s.format, vars...)
	if err != nil && n == 0 {
		return fmt.Errorf("failed to parse formatted string: %w", err)
	}
	
	// Set the parsed values back to source bindings
	for i, source := range s.sources {
		if i >= len(vars) {
			break
		}
		
		switch typed := source.(type) {
		case String:
			str := *vars[i].(*string)
			// Handle special cases for Bytes and URI
			if u, err := storage.ParseURI(str); err == nil {
				if err := typed.Set(u.String()); err != nil {
					return err
				}
			} else {
				if err := typed.Set(str); err != nil {
					return err
				}
			}
		case Bool:
			if err := typed.Set(*vars[i].(*bool)); err != nil {
				return err
			}
		case Int:
			if err := typed.Set(*vars[i].(*int)); err != nil {
				return err
			}
		case Float:
			if err := typed.Set(*vars[i].(*float64)); err != nil {
				return err
			}
		case Rune:
			if err := typed.Set(*vars[i].(*rune)); err != nil {
				return err
			}
		case URI:
			str := *vars[i].(*string)
			u, err := storage.ParseURI(str)
			if err != nil {
				return fmt.Errorf("failed to parse URI from string: %w", err)
			}
			if err := typed.Set(u); err != nil {
				return err
			}
		case Untyped:
			if err := typed.Set(vars[i]); err != nil {
				return err
			}
		}
	}
	
	return nil
}
