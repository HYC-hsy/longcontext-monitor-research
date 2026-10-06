package binding

import (
	"fmt"
)

// NewSprintf returns a String binding that formats its content using the format string
// and the values from the provided data bindings.
//
// Example:
//   name := binding.NewString()
//   age := binding.NewInt()
//   formatted := binding.NewSprintf("Name: %s, Age: %d", name, age)
//
// Since: 2.2
func NewSprintf(format string, bindings ...DataItem) String {
	s := &sprintfBinding{
		format:   format,
		bindings: bindings,
		val:      "",
	}
	
	// Listen to all source bindings
	for _, b := range bindings {
		b.AddListener(s)
	}
	
	// Initialize with current values
	s.updateValue()
	
	return s
}

// sprintfBinding implements String binding with formatting
type sprintfBinding struct {
	base
	format   string
	bindings []DataItem
	val      string
}

func (s *sprintfBinding) Get() (string, error) {
	s.lock.RLock()
	defer s.lock.RUnlock()
	
	return s.val, nil
}

func (s *sprintfBinding) Set(string) error {
	// sprintf bindings are read-only
	return fmt.Errorf("sprintf bindings are read-only")
}

// DataChanged is called when any of the source bindings change
func (s *sprintfBinding) DataChanged() {
	s.updateValue()
}

func (s *sprintfBinding) updateValue() {
	s.lock.Lock()
	defer s.lock.Unlock()
	
	// Gather current values from all bindings
	values := make([]interface{}, len(s.bindings))
	for i, b := range s.bindings {
		values[i] = s.getBindingValue(b)
	}
	
	// Format the string
	oldVal := s.val
	s.val = fmt.Sprintf(s.format, values...)
	
	// Trigger change notification if value changed
	if oldVal != s.val {
		s.trigger()
	}
}

func (s *sprintfBinding) getBindingValue(b DataItem) interface{} {
	switch typed := b.(type) {
	case String:
		if v, err := typed.Get(); err == nil {
			return v
		}
	case Int:
		if v, err := typed.Get(); err == nil {
			return v
		}
	case Float:
		if v, err := typed.Get(); err == nil {
			return v
		}
	case Bool:
		if v, err := typed.Get(); err == nil {
			return v
		}
	case Untyped:
		if v, err := typed.Get(); err == nil {
			return v
		}
	}
	return ""
}

// StringToStringWithFormat creates a new String binding that converts from an existing
// String binding using a format string.
//
// Example:
//   source := binding.NewString()
//   source.Set("world")
//   formatted := binding.StringToStringWithFormat(source, "Hello, %s!")
//   // formatted will contain "Hello, world!"
//
// Since: 2.2
func StringToStringWithFormat(source String, format string) String {
	return NewSprintf(format, source)
}
