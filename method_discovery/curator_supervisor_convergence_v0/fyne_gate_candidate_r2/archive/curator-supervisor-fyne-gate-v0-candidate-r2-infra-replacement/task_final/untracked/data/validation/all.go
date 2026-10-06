package validation

import "fyne.io/fyne/v2"

// NewAllStrings creates a validator that runs multiple validators in sequence.
// It returns the first error encountered, or nil if all validators pass.
// This is useful for combining multiple validation rules that must all be satisfied.
//
// Since: 2.2
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
