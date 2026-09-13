package greet

import "testing"

func TestHello(t *testing.T) {
	if got := Hello("Bob"); got != "hello Bob" {
		t.Fatalf("got %q", got)
	}
}
