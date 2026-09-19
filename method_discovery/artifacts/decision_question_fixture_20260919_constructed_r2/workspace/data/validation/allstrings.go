package validation

import (
	"fyne.io/fyne/v2"
)

// NewAllStrings creates a validator that runs all provided validators in order.
// It returns the first error encountered, or nil if all validators pass.
// This enables chaining multiple validators together.
//
// Since: 2.5
func NewAllStrings(validators ...fyne.StringValidator) fyne.StringValidator {
	return func(text string) error {
		for _, validator := range validators {
			if validator == nil {
				continue
			}
			if err := validator(text); err != nil {
				return err
			}
		}
		return nil
	}
}
