## ADDED Requirements

### Requirement: JPEG slideshow from SD card
The system SHALL display a rotating sequence of JPEG images from `/sd/photos/` when in `IDLE` state. Each image SHALL be shown for a configurable duration (default 30 seconds) before advancing to the next.

#### Scenario: Slideshow starts on boot
- **WHEN** the device enters `IDLE` state for the first time and the SD card is mounted
- **THEN** the first JPEG from `/sd/photos/` (sorted by filename) SHALL be displayed full-screen

#### Scenario: Automatic photo advance
- **WHEN** a photo has been displayed for the configured interval
- **THEN** the system SHALL fade to the next photo in the rotation without user interaction

#### Scenario: Rotation wraps around
- **WHEN** the last photo in the list has been displayed
- **THEN** the rotation SHALL wrap back to the first photo

### Requirement: Photo list loaded at boot, updated dynamically
The photo filename list SHALL be built from `/sd/photos/` at boot and SHALL be updatable at runtime without restarting the slideshow task.

#### Scenario: Photos present at boot
- **WHEN** the SD card contains one or more `.jpg` files in `/sd/photos/` at boot
- **THEN** the slideshow task SHALL build an internal list of those filenames sorted alphabetically

#### Scenario: New photo added via Telegram
- **WHEN** the Telegram message handler saves a new photo to `/sd/photos/<timestamp>.jpg`
- **THEN** the filename SHALL be appended to the in-memory list so it appears in future rotation cycles without a restart

### Requirement: Graceful handling of missing or unreadable SD card
If the SD card is not present or `/sd/photos/` is empty, the slideshow SHALL degrade gracefully rather than crashing.

#### Scenario: SD card absent at boot
- **WHEN** the SD card cannot be mounted on boot
- **THEN** the slideshow task SHALL not start, and the idle screen SHALL display a plain dark background with a subtle "No SD card" indicator

#### Scenario: Photos directory empty
- **WHEN** the SD card is mounted but `/sd/photos/` contains no `.jpg` files
- **THEN** the idle screen SHALL display a plain dark background without error

#### Scenario: Individual JPEG unreadable
- **WHEN** a JPEG in the rotation cannot be decoded
- **THEN** the slideshow SHALL skip that file and log the filename to UART, then advance to the next

### Requirement: Slideshow suspended during message flow
The slideshow SHALL pause while the device is not in `IDLE` state, freeing display resources for message content.

#### Scenario: Slideshow pauses on message arrival
- **WHEN** the state transitions away from `IDLE`
- **THEN** the slideshow task SHALL suspend its advance timer

#### Scenario: Slideshow resumes on return to idle
- **WHEN** the state transitions back to `IDLE`
- **THEN** the slideshow SHALL resume from the photo it was last showing (not restart from the beginning)

### Requirement: Image scaling to fill display
Each JPEG SHALL be scaled and centred to fill the 480×480 display. Images that do not match this aspect ratio SHALL be letterboxed with black bars.

#### Scenario: Square image displayed
- **WHEN** a 480×480 JPEG is displayed
- **THEN** it SHALL fill the entire screen with no bars

#### Scenario: Non-square image displayed
- **WHEN** a JPEG with a non-square aspect ratio is displayed
- **THEN** it SHALL be scaled so the longer dimension fits 480 pixels, centred, with black fill on the shorter axis
