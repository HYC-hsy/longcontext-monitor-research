package counter

import "testing"

func TestClamp(t *testing.T) {
	tests := []struct {
		value, minimum, maximum, want int
	}{
		{-2, 0, 10, 0},
		{5, 0, 10, 5},
		{12, 0, 10, 10},
	}
	for _, test := range tests {
		if got := Clamp(test.value, test.minimum, test.maximum); got != test.want {
			t.Fatalf("Clamp(%d, %d, %d) = %d, want %d", test.value, test.minimum,
				test.maximum, got, test.want)
		}
	}
}

func TestIsEven(t *testing.T) {
	for value, want := range map[int]bool{-3: false, -2: true, 0: true, 3: false, 4: true} {
		if got := IsEven(value); got != want {
			t.Fatalf("IsEven(%d) = %v, want %v", value, got, want)
		}
	}
}
