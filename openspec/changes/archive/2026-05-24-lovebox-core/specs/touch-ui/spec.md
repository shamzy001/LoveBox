## ADDED Requirements

### Requirement: Touch input polling
The system SHALL poll the Presto's touchscreen controller on Core 0 within the asyncio event loop and dispatch touch events to the current state handler.

#### Scenario: Touch registered in ARRIVED state
- **WHEN** a tap is registered anywhere on screen while in `ARRIVED` state
- **THEN** the state machine SHALL transition to `REVEALING`

#### Scenario: Touch registered in READING state outside reply buttons
- **WHEN** a tap is registered in `READING` state and the coordinate does not hit any reply button
- **THEN** no reply SHALL be sent and the state SHALL transition to `IDLE`

#### Scenario: Touch registered in READING state on a reply button
- **WHEN** a tap is registered in `READING` state and the coordinate hits a reply button
- **THEN** the corresponding reply SHALL be sent and the state SHALL transition to `IDLE`

#### Scenario: Touch ignored in IDLE state
- **WHEN** a tap is registered while in `IDLE` state
- **THEN** no state transition SHALL occur (idle screen is not interactive in v1)

#### Scenario: Touch during transition animation
- **WHEN** a tap is registered while a transition animation is playing (`REVEALING`)
- **THEN** the tap SHALL be buffered and processed once the animation completes

### Requirement: Arrived screen layout
The `ARRIVED` state SHALL render a single full-screen prompt designed to catch Beth's attention.

#### Scenario: Arrived screen renders correctly
- **WHEN** the device enters `ARRIVED` state
- **THEN** the display SHALL show:
  - A dark (near-black) background
  - The text "Shah sent you something ♥" centred vertically in the upper half
  - The text "Tap to reveal" in a smaller font centred below it
  - No other interactive elements

### Requirement: Preset reply buttons
In `READING` state three reply buttons SHALL be pinned to the bottom of the screen, visible alongside the message content. Tapping one sends the reply and returns to `IDLE`; tapping anywhere else also returns to `IDLE` without sending.

#### Scenario: Reply buttons rendered in READING state
- **WHEN** the device enters `READING` state
- **THEN** three buttons SHALL be displayed in a row pinned to the bottom of the screen:
  - Button 1: "❤️"
  - Button 2: "😂"
  - Button 3: "Call me!"

#### Scenario: Reply sent on button tap
- **WHEN** Beth taps one of the three reply buttons
- **THEN** the corresponding text SHALL be sent to `SHAH_CHAT_ID` via the Telegram `sendMessage` API
- **AND** the state SHALL transition to `IDLE`

#### Scenario: Reply send fails
- **WHEN** the `sendMessage` call fails (network error, timeout)
- **THEN** a brief error toast ("Could not send — try again") SHALL appear for 2 seconds
- **AND** the READING screen SHALL remain so Beth can retry

### Requirement: Inactivity timeout in READING state
If Beth does not interact after the message is revealed, the device SHALL automatically return to `IDLE` after 2 minutes.

#### Scenario: No interaction in READING state
- **WHEN** the device has been in `READING` state for 2 minutes with no touch input
- **THEN** no reply SHALL be sent and the state SHALL transition to `IDLE`

#### Scenario: Timeout resets on touch
- **WHEN** Beth touches the screen while in `READING` state
- **THEN** the inactivity timer SHALL reset

### Requirement: Touch hit testing
The touch handler SHALL map raw touchscreen coordinates to UI elements using bounding-box hit tests. No external UI framework is required.

#### Scenario: Button hit test succeeds
- **WHEN** a tap coordinate falls within the bounding box of a rendered button (±8 px tolerance)
- **THEN** the button's action SHALL fire

#### Scenario: Button hit test fails
- **WHEN** a tap coordinate falls outside all button bounding boxes
- **THEN** no button action SHALL fire; the dismiss behaviour (if applicable) MAY apply
