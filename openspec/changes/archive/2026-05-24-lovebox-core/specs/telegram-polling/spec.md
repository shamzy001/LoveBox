## ADDED Requirements

### Requirement: Continuous polling on Core 1
The system SHALL poll the Telegram Bot API `getUpdates` endpoint on Core 1 every 30 seconds. The polling loop SHALL be the only operation on Core 1 and SHALL run for the lifetime of the device.

#### Scenario: Successful poll with no new messages
- **WHEN** `getUpdates` returns an empty result array
- **THEN** Core 1 SHALL update the offset (unchanged) and sleep 30 seconds before the next poll

#### Scenario: Successful poll with new messages
- **WHEN** `getUpdates` returns one or more updates
- **THEN** Core 1 SHALL parse each update, advance the offset past the last seen update ID, and push parsed message dicts to the shared queue

#### Scenario: Core 1 crash recovery
- **WHEN** Core 1's polling loop raises an unhandled exception
- **THEN** the exception SHALL be caught, logged to UART, and the loop SHALL restart after a 10-second delay
- **AND** a heartbeat timestamp SHALL be updated so Core 0 can detect prolonged failure

### Requirement: Update offset persistence
The system SHALL track the Telegram `update_id` offset so that previously processed messages are not re-delivered after a restart or network error.

#### Scenario: Offset advances correctly
- **WHEN** a batch of updates is successfully parsed
- **THEN** the offset SHALL be set to `max(update_id) + 1` from that batch before the next poll

#### Scenario: Offset not advanced on parse failure
- **WHEN** an update cannot be parsed (malformed JSON, unexpected structure)
- **THEN** the offset SHALL NOT advance, and the update SHALL be logged and skipped

### Requirement: Message type detection and routing
Core 1 SHALL classify each incoming Telegram message and populate a typed message dict before pushing to the queue.

#### Scenario: Plain text message
- **WHEN** an update contains `message.text` that does not start with `/`
- **THEN** the pushed dict SHALL have `type: "text"` and `body: <the text>`

#### Scenario: GIF or animation message
- **WHEN** an update contains `message.animation` or a document with mime_type `image/gif`
- **THEN** the message SHALL be ignored and the offset advanced past it (GIFs are deferred to v2)

#### Scenario: Photo message
- **WHEN** an update contains `message.photo` (array of sizes)
- **THEN** Core 1 SHALL download the largest size to `/sd/cache/current.jpg` before pushing `type: "photo"` to the queue

#### Scenario: Unknown message type
- **WHEN** an update contains a message type not listed above
- **THEN** the update SHALL be silently skipped (no queue push)

### Requirement: Sender filtering
The system SHALL only process messages from Shah's Telegram chat ID. Messages from any other sender SHALL be silently ignored.

#### Scenario: Message from Shah
- **WHEN** `message.from.id` or `message.chat.id` matches `SHAH_CHAT_ID` in `secrets.py`
- **THEN** the message SHALL be parsed and pushed to the queue

#### Scenario: Message from unknown sender
- **WHEN** a message arrives from a chat ID that does not match `SHAH_CHAT_ID`
- **THEN** the message SHALL be ignored and the offset advanced past it

### Requirement: Photo size limit with bot reply
The system SHALL check the photo file size before downloading. If it exceeds 5 MB, Core 1 SHALL reply to Shah and skip the download.

#### Scenario: Photo within size limit
- **WHEN** a photo message is received and the largest size variant has `file_size` ≤ 5 MB
- **THEN** Core 1 SHALL proceed with the chunked download

#### Scenario: Photo exceeds size limit
- **WHEN** a photo message is received and the largest size variant has `file_size` > 5 MB
- **THEN** Core 1 SHALL NOT download and SHALL reply to Shah: "Photo too large (>5 MB) — send a smaller version."

### Requirement: Media download with chunked streaming
The system SHALL download media files from Telegram by streaming them in 4 KB chunks to the SD card, to avoid exhausting PSRAM.

#### Scenario: Successful media download
- **WHEN** a GIF or photo message is received within size limits
- **THEN** Core 1 SHALL call `getFile` to resolve the download URL, open the target SD path for writing, and write the response body in 4 KB chunks until complete

#### Scenario: Download failure mid-stream
- **WHEN** the HTTP connection drops before the file is fully written
- **THEN** the partial file SHALL be deleted, no queue push SHALL occur, and an error SHALL be logged to UART
