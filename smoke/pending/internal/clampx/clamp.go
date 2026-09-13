package clampx

func Clamp(v, lo, hi int) (int, error) {
	if v < lo {
		return lo, nil
	}
	if v > hi {
		return hi, nil
	}
	return v, nil
}
