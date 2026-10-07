package validation

import "fyne.io/fyne/v2"

// NewAllStrings creates a validator combinator that runs all provided validators in order.
// It returns a StringValidator that validates the input against all validators and returns
// the first error encountered. If all validators pass, it returns nil.
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
