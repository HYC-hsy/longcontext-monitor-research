package binding

import (
	"fmt"
)

// Sprintf creates a new String binding that formats its content using a format string and multiple data bindings.
// The returned binding will update whenever any of the source bindings change.
// The format parameter follows the same syntax as fmt.Sprintf.
//
// Since: 2.2
func Sprintf(format string, bindings ...DataItem) String {
	s := &boundSprintf{
		format:   format,
		bindings: bindings,
	}
	
	// Listen to all source bindings
	for _, b := range bindings {
		b.AddListener(s)
	}
	
	return s
}

type boundSprintf struct {
	base
	format   string
	bindings []DataItem
}

func (b *boundSprintf) Get() (string, error) {
	values := make([]interface{}, len(b.bindings))
	
	for i, binding := range b.bindings {
		switch v := binding.(type) {
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
			// For any other type, try to get as Untyped
			if u, ok := binding.(Untyped); ok {
				val, err := u.Get()
				if err != nil {
					return "", err
				}
				values[i] = val
			} else {
				values[i] = binding
			}
		}
	}
	
	return fmt.Sprintf(b.format, values...), nil
}

func (b *boundSprintf) Set(string) error {
	// Sprintf bindings are read-only
	return nil
}

// DataChanged is called when one of the source bindings changes
func (b *boundSprintf) DataChanged() {
	b.trigger()
}
