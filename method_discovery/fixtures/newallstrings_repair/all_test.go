package validation

import (
	"errors"
	"reflect"
	"testing"
)

func TestNewAllStringsRunsInOrderAndReturnsFirstError(t *testing.T) {
	wantErr := errors.New("second validator failed")
	calls := make([]int, 0, 3)
	validator := NewAllStrings(
		func(string) error {
			calls = append(calls, 1)
			return nil
		},
		func(string) error {
			calls = append(calls, 2)
			return wantErr
		},
		func(string) error {
			calls = append(calls, 3)
			return nil
		},
	)

	if got := validator("value"); got != wantErr {
		t.Fatalf("expected first validator error %v, got %v", wantErr, got)
	}
	if want := []int{1, 2}; !reflect.DeepEqual(calls, want) {
		t.Fatalf("expected calls %v, got %v", want, calls)
	}
}

func TestNewAllStringsReturnsNilWhenAllPass(t *testing.T) {
	validator := NewAllStrings(
		func(string) error { return nil },
		func(string) error { return nil },
	)

	if err := validator("value"); err != nil {
		t.Fatalf("expected nil, got %v", err)
	}
}
