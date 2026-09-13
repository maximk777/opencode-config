package clampx

import "testing"

func TestClampInside(t *testing.T) {
	if got, err := Clamp(5, 1, 9); err != nil || got != 5 {
		t.Fatalf("got %d, %v", got, err)
	}
}
