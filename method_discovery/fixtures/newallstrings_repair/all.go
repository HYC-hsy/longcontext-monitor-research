// Package validation provides validation for data inside widgets
package validation

import "fyne.io/fyne/v2"

// NewAllStrings creates a validator that runs all provided validators in order.
// It returns the first error encountered, or nil when every validator passes.
func NewAllStrings(validators ...fyne.StringValidator) fyne.StringValidator {
	return func(text string) error {
		for _, validator := range validators {
			if err := validator(text); err != nil {
				return err
			}
		}

		return nil
	}
}
