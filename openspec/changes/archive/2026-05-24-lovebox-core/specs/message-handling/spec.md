## ADDED Requirements

### Requirement: Queue consumption on Core 0
Core 0's asyncio loop SHALL check the shared message queue on each iteration and transition the device state when a new message is found.

#### Scenario: New message in queue while idle
- **WHEN** the device is in `IDLE` state and a message dict is popped from the queue
- **THEN** the device SHALL transition to `ARRIVED` state immediately

#### Scenario: New message in queue while already active
- **WHEN** a second message arrives before Beth has finished with the first (device in ARRIVED, REVEALING, or READING)
- **THEN** the new message SHALL remain in the queue and be processed after the device returns to IDLE

### Requirement: ARRIVED state presentation
In the `ARRIVED` state the system SHALL pulse the rear LEDs and display a prompt screen until Beth taps the display.

#### Scenario: Arrived state renders correctly
- **WHEN** the state transitions to `ARRIVED`
- **THEN** the screen SHALL show "Shah sent you something ♥ Tap to reveal" centered on a dark background
- **AND** the rear LEDs SHALL begin their pulse animation

#### Scenario: Beth taps while in ARRIVED
- **WHEN** the touchscreen registers a tap in `ARRIVED` state
- **THEN** the state SHALL transition to `REVEALING`

### Requirement: REVEALING transition
The system SHALL play a brief transition animation (≤1 second) between `ARRIVED` and `READING`.

#### Scenario: Reveal animation completes
- **WHEN** the reveal animation finishes
- **THEN** the state SHALL automatically transition to `READING` and render the message content with reply buttons

### Requirement: READING state layout
In `READING` state the message content SHALL occupy the upper portion of the screen and the reply buttons SHALL be pinned to the bottom, both visible simultaneously.

#### Scenario: Text message in READING state
- **WHEN** the state is `READING` with `type: "text"`
- **THEN** the message body SHALL be rendered in the upper area of the screen with a comfortable margin; reply buttons SHALL appear at the bottom

#### Scenario: Long text in READING state
- **WHEN** the message body exceeds the available upper area at the chosen font size
- **THEN** the text SHALL be truncated with a scroll indicator; a swipe-up gesture SHALL scroll the text without interfering with the reply buttons

#### Scenario: Photo message in READING state
- **WHEN** the state is `READING` with `type: "photo"`
- **THEN** the JPEG SHALL be displayed scaled to fill the upper area of the screen (above the reply button row), letterboxed if needed; reply buttons SHALL appear at the bottom

#### Scenario: Photo file missing
- **WHEN** the JPEG at `/sd/cache/current.jpg` cannot be opened
- **THEN** a placeholder tile ("Could not load photo") SHALL appear in the upper area and reply buttons SHALL still be shown
