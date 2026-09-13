## ADDED Requirements

### Requirement: Greeting trims names
Hello SHALL trim surrounding whitespace from the name.

#### Scenario: padded name
- **WHEN** Hello is called with "  Bob "
- **THEN** it returns "hello Bob"

### Requirement: Empty name greets world
Hello SHALL greet the world when the trimmed name is empty.

#### Scenario: empty name
- **WHEN** Hello is called with ""
- **THEN** it returns "hello world"

#### Scenario: blank name
- **WHEN** Hello is called with "   "
- **THEN** it returns "hello world"
