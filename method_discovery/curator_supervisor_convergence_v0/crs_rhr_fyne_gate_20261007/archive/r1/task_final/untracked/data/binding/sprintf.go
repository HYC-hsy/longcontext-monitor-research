package binding

import "fmt"

// NewSprintf creates a String binding that formats one or more input values according to the format string.
// Changes to any source binding trigger a recomputation of the formatted output.
//
// Example:
//   name := binding.NewString()
//   age := binding.NewInt()
//   formatted := binding.NewSprintf("Name: %s, Age: %d", name, age)
//
// Since: 2.2
func NewSprintf(format string, src ...DataItem) String {
	if len(src) == 0 {
		return NewString()
	}

	ret := &sprintfString{
		format: format,
		srcs:   src,
	}

	// Set up listeners to update when sources change
	listener := NewDataListener(ret.recalculate)
	for _, s := range src {
		s.AddListener(listener)
	}

	// Calculate initial value
	ret.recalculate()

	return ret
}

type sprintfString struct {
	base

	format string
	srcs   []DataItem
	cache  string
}

func (s *sprintfString) Get() (string, error) {
	s.lock.RLock()
	defer s.lock.RUnlock()

	return s.cache, nil
}

func (s *sprintfString) Set(val string) error {
	// Sprintf bindings are read-only
	return nil
}

func (s *sprintfString) recalculate() {
	s.lock.Lock()
	defer s.lock.Unlock()

	vals := make([]interface{}, len(s.srcs))
	for i, src := range s.srcs {
		switch v := src.(type) {
		case Bool:
			val, _ := v.Get()
			vals[i] = val
		case Float:
			val, _ := v.Get()
			vals[i] = val
		case Int:
			val, _ := v.Get()
			vals[i] = val
		case String:
			val, _ := v.Get()
			vals[i] = val
		case Untyped:
			val, _ := v.Get()
			vals[i] = val
		default:
			vals[i] = nil
		}
	}

	old := s.cache
	s.cache = fmt.Sprintf(s.format, vals...)

	if old != s.cache {
		s.trigger()
	}
}

// StringToStringWithFormat creates a String binding that converts a source String binding
// using the provided format string. This is a convenience function for single-input formatting.
//
// Example:
//   input := binding.NewString()
//   output := binding.StringToStringWithFormat(input, "Value: %s")
//
// Since: 2.2
func StringToStringWithFormat(src String, format string) String {
	if src == nil {
		return NewString()
	}

	ret := &stringFormatString{
		format: format,
		src:    src,
	}

	listener := NewDataListener(ret.recalculate)
	src.AddListener(listener)

	// Calculate initial value
	ret.recalculate()

	return ret
}

type stringFormatString struct {
	base

	format string
	src    String
	cache  string
}

func (s *stringFormatString) Get() (string, error) {
	s.lock.RLock()
	defer s.lock.RUnlock()

	return s.cache, nil
}

func (s *stringFormatString) Set(val string) error {
	// Format bindings are read-only
	return nil
}

func (s *stringFormatString) recalculate() {
	s.lock.Lock()
	defer s.lock.Unlock()

	val, _ := s.src.Get()
	old := s.cache
	s.cache = fmt.Sprintf(s.format, val)

	if old != s.cache {
		s.trigger()
	}
}
