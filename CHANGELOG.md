# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog and uses project release tags where available.

## [Unreleased]

- Reserved for upcoming changes before the next tagged release.

## [0.7.4] - 2026-04-20

### Added

- Added hot-reload support for the send workflow so active send cfg changes can be picked up during a running send job.

### Changed

- Kept send-mode port changes restart-safe by detecting them and warning instead of switching the active serial connection mid-run.

## [0.7.3] - 2026-04-20

### Changed

- Expanded the English and German README introductions with clearer purpose, audience fit, and typical workflow overview sections.
- Updated the visible documentation version references to match the current release.

## [0.7.2] - 2026-04-20

### Added

- Added live cfg hot-reload for listen, autoresponder, and send-derived autoresponder settings during listen mode.
- Added listen verbose mode with optional full receive-record output and GUI support for the new flag.
- Added log rotation settings for JSONL activity logs, including configurable size limits and backup counts.

### Changed

- Made verbose receive output visually quieter so it stays secondary to the main receive line.
- Clarified the GUI label for verbose mode so it maps directly to `--verbose-listen`.

## [0.7.1] - 2026-04-20

### Added

- Added autoresponder unicast mode driven by the saved send cfg recipient selection.
- Added templated autoresponder reply text with variables from the triggering message.
- Added start buttons in the cfg GUI for launching send and listen workflows directly.

### Changed

- Made the cfg GUI tabs vertically scrollable so the full form fits on standard screens.
- Improved effective parameter reporting so listen, send, and autoresponder cfg sources are shown explicitly.
- Kept the GUI running commands in a visible console-friendly way so launch errors remain visible.

### Fixed

- Fixed cfg parsing for autoresponder templates that contain percent placeholders.
- Fixed autoresponder handling so routing and ACK packets do not retrigger reply loops.

## [0.7.0] - 2026-04-20

### Changed

- Made `unattended` configurable in both send and listen cfg workflows.
- Added `unattended` to the listen cfg builder UI and persisted listen cfg output.
- Kept runtime and cfg behavior aligned so unattended mode can be stored and reused consistently across both workflows.

## [0.6.1] - 2026-04-20

### Added

- Added a project-local changelog with release notes for tagged versions.
- Added direct links to the changelog from the English and German README files.

### Changed

- Moved visible version handling into a shared module used by CLI, GUI, cfg headers, and documentation.

## [0.6.0] - 2026-04-20

### Added

- Added a shared version module so the project version can be maintained in one place.
- Added visible version output to the CLI via `--version`.
- Added visible version markers to generated cfg files.
- Added visible version text to the GUI window title.
- Added version references to the English and German README files.

### Changed

- Improved autoresponder console output so sent reply text and target channel are shown before the ACK result.

## [0.5.1] - 2026-04-20

### Added

- Added a dedicated autoresponder cfg workflow.
- Added autoresponder support to the listen workflow.
- Added GUI support for send, listen, and autoresponder cfg generation.
- Added automatic loading of existing cfg files in the GUI.

### Changed

- Improved cfg separation between send and listen workflows.
- Improved cfg overwrite warnings for CLI and GUI usage.

### Fixed

- Fixed autoresponder loops caused by routing and ACK packets.
- Fixed listen and send mode handling so mode selection alone does not trigger cfg rewrites.
- Fixed cfg loading and saving so send and listen cfg files are handled independently.

## [0.5-beta] - 2026-04-20

### Added

- Added MIT licensing and copyright headers.
- Added send/listen/history workflows with cfg-based operation.
- Added filtered sending, retries, dry-run support, and local history logging.
- Added listen mode with filters and JSONL logging.

## [0.4.2] - 2026-04-20

### Changed

- Split default history files into separate send and listen history logs.

## [0.4.1] - 2026-04-20

### Fixed

- Fixed cfg separation bugs between send and listen handling.
- Fixed GUI save/load behavior so it applies to the active cfg family only.

## [0.4.0] - 2026-04-20

### Added

- Added platform-neutral documentation and examples.
- Added a GUI cfg generator.
- Added cleaner runtime parameter reporting.
