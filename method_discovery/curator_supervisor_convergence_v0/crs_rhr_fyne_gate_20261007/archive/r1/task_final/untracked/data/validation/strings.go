package validation

import (
	"fyne.io/fyne/v2"
)

// NewAllStrings creates a validator combinator that runs all provided validators in sequence.
// It returns the first error encountered, or nil if all validators pass.
// This enables chaining multiple validators together (e.g., time format validation and regexp validation).
//
// Since: 2.2
func NewAllStrings(validators ...fyne.StringValidator) fyne.StringValidator {
	if len(validators) == 0 {
		return func(text string) error {
			return nil
		}
	}

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
