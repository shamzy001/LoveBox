## ADDED Requirements

### Requirement: Wi-Fi initialisation on boot
The system SHALL connect to the configured Wi-Fi network on startup before any other network operation. SSID and password SHALL be read from `secrets.py`. The system SHALL block boot until a connection is established or a timeout of 30 seconds is reached.

#### Scenario: Successful connection on boot
- **WHEN** the device powers on and `secrets.py` contains valid SSID and PASSWORD
- **THEN** the system connects to Wi-Fi within 30 seconds and proceeds to start Telegram polling and the main UI loop

#### Scenario: Connection timeout on boot
- **WHEN** the device cannot connect within 30 seconds
- **THEN** the system SHALL display a Wi-Fi error indicator on screen and retry connection in the background every 15 seconds, allowing the slideshow to run in offline mode

### Requirement: Automatic reconnection on drop
The system SHALL detect Wi-Fi disconnection and automatically attempt to reconnect without user intervention and without crashing Core 0 or Core 1.

#### Scenario: Network drops during operation
- **WHEN** the Wi-Fi link drops while the device is running
- **THEN** Core 1 SHALL detect the failure on the next poll attempt, display a subtle disconnected indicator on Core 0, and retry connection every 15 seconds until restored

#### Scenario: Reconnection restores polling
- **WHEN** Wi-Fi reconnects after a drop
- **THEN** Telegram polling SHALL resume automatically with the correct offset and the disconnected indicator SHALL disappear

### Requirement: Connection status reporting
The system SHALL expose a connection status value readable by both cores so the UI can show or hide a disconnected indicator without polling the hardware directly.

#### Scenario: Status readable cross-core
- **WHEN** Core 1 updates the Wi-Fi connection status
- **THEN** Core 0 SHALL be able to read the current status within the next UI render cycle without acquiring a blocking lock
