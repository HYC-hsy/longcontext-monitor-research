# Case: StringToStringWithFormat Missing Identity Optimization

## Specification Requirement

**Target 3, Requirement 2** (task/original_task.txt):
> **`StringToStringWithFormat(str String, format string) String`** — A convenience function that wraps a `String` binding with a format. **If the format is `"%s"` (identity), return the original binding directly (no wrapping).** Otherwise, delegate to `NewSprintf(format, str)`.

Key optimization contract: When format is "%s", return original binding without creating wrapper.

## Source Evidence

### Implementation (data/binding/sprintf.go:201-210)
```go
func StringToStringWithFormat(str String, format string) String {
	b := &stringToStringWithFormat{
		format: format,
		source: str,
	}

	// Listen to source changes
	str.AddListener(b)

	return b
}
```

## Analysis

**Current behavior:** Always creates a new wrapper binding, regardless of format value.
**Required behavior:** Check if `format == "%s"`, and if so, return `str` directly.

The specification requires this optimization to avoid unnecessary wrapper overhead when the format is the identity function. This is a performance and simplicity optimization.

### Expected Implementation
```go
func StringToStringWithFormat(str String, format string) String {
	if format == "%s" {
		return str  // Identity: no wrapping needed
	}
	return NewSprintf(format, str)  // Delegate to NewSprintf
}
```

## Conclusion

The identity optimization is not implemented. Every call creates a wrapper, even when format is "%s" (which would just return the input unchanged).

**Status:** Specification violation - missing required optimization
**Evidence file:** data/binding/sprintf.go lines 201-210
**Receipt:** receipt-220f69fe669845aca0dbbb2df32f0423

## Impact

- Performance: Unnecessary wrapper object and listener registration for identity case
- Specification compliance: Explicit requirement not met
- Function signature exists but behavior differs from spec
