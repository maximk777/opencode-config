## ADDED Requirements

### Requirement: Clamp bounds a value
Clamp SHALL return the value limited to the range from lo to hi and SHALL return ErrInvalidRange when lo is greater than hi.

#### Scenario: value inside the range
- **WHEN** Clamp is called with 5, 1, 9
- **THEN** it returns 5 and no error

#### Scenario: value below the range
- **WHEN** Clamp is called with -3, 1, 9
- **THEN** it returns 1 and no error

#### Scenario: inverted range
- **WHEN** Clamp is called with 5, 9, 1
- **THEN** it returns 0 and ErrInvalidRange
