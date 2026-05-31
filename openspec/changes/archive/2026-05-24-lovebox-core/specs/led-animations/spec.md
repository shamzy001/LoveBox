## ADDED Requirements

### Requirement: Idle ambient LED state
When the device is in `IDLE` state the rear RGB LEDs SHALL display a gentle, low-brightness ambient effect that does not distract from the photo slideshow.

#### Scenario: Idle LEDs on startup
- **WHEN** the device boots and enters `IDLE` state
- **THEN** all 7 rear LEDs SHALL be set to a warm white at ~10% brightness

#### Scenario: Idle LEDs during slideshow
- **WHEN** the slideshow is running and no message has arrived
- **THEN** the LED state SHALL remain unchanged (static ambient, no animation loop running)

### Requirement: Message arrival pulse animation
When the device transitions to `ARRIVED` state the LEDs SHALL play a repeating pulse animation to draw Beth's attention.

#### Scenario: Pulse animation starts on arrival
- **WHEN** the state transitions to `ARRIVED`
- **THEN** the 7 rear LEDs SHALL begin a breathing-pulse animation — smoothly ramping from 0% to 100% brightness and back — at approximately 1 cycle per 2 seconds, in a warm pink/rose colour

#### Scenario: Pulse runs as asyncio task
- **WHEN** the pulse animation is active
- **THEN** it SHALL be implemented as an `asyncio.Task` that yields between each brightness step so the display and touch system remain responsive

#### Scenario: Pulse stops on reveal
- **WHEN** Beth taps the screen and the state transitions away from `ARRIVED`
- **THEN** the pulse animation task SHALL be cancelled and LEDs set to a steady low brightness

### Requirement: LED state synchronised with app state
The LED driver SHALL always reflect the current app state. State transitions SHALL update LED behaviour immediately.

#### Scenario: Return to idle after reply
- **WHEN** the state transitions back to `IDLE` (after Beth sends a reply or dismisses)
- **THEN** the LEDs SHALL return to the ambient idle state within one render cycle

#### Scenario: No LED flicker on state transition
- **WHEN** any state transition occurs
- **THEN** there SHALL be no visible flicker — the transition SHALL be a smooth fade of at most 200 ms

### Requirement: LED driver encapsulation
All LED control SHALL go through a single `led_manager` module. No other module SHALL write to LED hardware directly.

#### Scenario: Single control point
- **WHEN** any module needs to change LED state
- **THEN** it SHALL call a function on `led_manager` (e.g. `set_idle()`, `start_pulse()`, `set_solid(colour)`) rather than writing to hardware registers directly
