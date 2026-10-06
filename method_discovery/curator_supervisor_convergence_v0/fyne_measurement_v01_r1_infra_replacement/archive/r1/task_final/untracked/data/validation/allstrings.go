package validation

import "fyne.io/fyne/v2"

// NewAllStrings creates a validator that combines multiple string validators.
// The returned validator passes only if all the provided validators pass.
// Validators are checked in order and the first error is returned.
//
// Since: 2.2
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
