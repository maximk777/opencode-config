## ADDED Requirements

### Requirement: Sum of empty slice is zero
Sum SHALL return 0 for an empty or nil slice.

#### Scenario: nil slice
- **WHEN** Sum is called with nil
- **THEN** it returns 0

### Requirement: Max returns the largest element
Max SHALL return the largest element and false for an empty slice.

#### Scenario: several elements
- **WHEN** Max is called with [3, 9, 2]
- **THEN** it returns 9 and true

#### Scenario: empty slice
- **WHEN** Max is called with an empty slice
- **THEN** it returns 0 and false
