package counter

// Clamp restricts value to the inclusive range [minimum, maximum].
func Clamp(value, minimum, maximum int) int {
	if value < minimum {
		return minimum
	}
	if value > maximum {
		return maximum
	}
	return value
}

// IsEven reports whether value is divisible by two.
func IsEven(value int) bool {
	return value%2 == 0
}
