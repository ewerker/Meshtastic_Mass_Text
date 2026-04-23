# Meshtastic_Mass_Com

Current version: `0.7.6`

English documentation. German version: [README.de.md](C:\Users\richt\Documents\Codex\Meshtastic_tool\README.de.md)
Release notes: [CHANGELOG.md](C:\Users\richt\Documents\Codex\Meshtastic_tool\CHANGELOG.md)

Copyright (c) 2026 Frank Richter, [w-2.de](https://w-2.de)

Small Python utility for Meshtastic communication workflows: direct messages, group broadcasts, live listening, logging, history, and separate local config files for send and listen workflows.

## Related Project

If you are also looking for a simple viewer that works directly in the browser, take a look at [meshview](https://github.com/ewerker/meshview).

`meshview` focuses on browser-based viewing, while `Meshtastic_Mass_Com` focuses on communication workflows, automation-friendly cfg handling, listening, logging, and autoresponder behavior.

## Overview

Meshtastic_Mass_Com is meant for people who want more control over recurring Meshtastic communication tasks than the standard app or a few one-off CLI commands usually provide.

It is especially useful if you want to:

- send the same message to many known nodes with filtering and retries
- listen continuously with practical filters and local logging
- separate send, listen, and autoresponder behavior into reusable cfg files
- run repeatable field, club, relay, or test workflows without rebuilding commands every time

The tool is probably a good fit if you often think:

- "I want to send to a filtered subset of nodes, not just one."
- "I want a listener with logs, history, and a small autoresponder."
- "I want to tweak behavior in cfg files instead of editing long commands again and again."

The tool is probably not the main thing you need if you only:

- want occasional normal chat in the official Meshtastic app
- send one message manually every now and then
- do not need filtering, logging, history, or reusable automation-like behavior

## Typical Workflows

- Send a direct message to all known or filtered recipients.
- Broadcast once into a channel chat such as a private group or LongFast.
- Run a live listener with channel, sender, scope, and text filtering.
- Keep a local JSONL activity log plus a separate local history/inbox.
- Use cfg-driven autoresponder rules for specific senders or trigger texts.
- Let the listener reload updated cfg files without restarting the whole workflow.

## Features

- Sends to all known nodes or only filtered targets
- Can prefilter and then manually select nodes from a numbered list
- Filters by node ID, short name, or long name
- Supports wildcard filters such as `FR*`
- Can auto-detect serial ports or let you choose one interactively
- Waits for ACK, implicit ACK, or NAK when requested
- Can retry after implicit ACKs or NAKs
- Can listen for incoming packets with sender/channel/scope/content filters
- Can write send and listen activity to a local JSONL log file
- Can send a real group/broadcast message on a selected channel
- Can run in dry-run mode without transmitting
- Can keep a local history/inbox and show recent entries later
- Stores runtime settings in separate send/listen `.cfg` files
- Supports unattended runs without prompts
- Can protect the config from changes or force config updates explicitly

## Requirements

- Python 3.14+
- Any operating system supported by Python and the Meshtastic CLI stack
- Python packages:
  - `meshtastic`
  - `pyserial`

## Installation

```bash
python -m pip install meshtastic pyserial
```

## License

MIT License. See [LICENSE](C:\Users\richt\Documents\Codex\Meshtastic_tool\LICENSE).

## Files

- Script: [meshtastic_mass_com.py](C:\Users\richt\Documents\Codex\Meshtastic_tool\meshtastic_mass_com.py)
- Send config: [meshtastic_mass_com.send.cfg](C:\Users\richt\Documents\Codex\Meshtastic_tool\meshtastic_mass_com.send.cfg)
- Listen config: [meshtastic_mass_com.listen.cfg](C:\Users\richt\Documents\Codex\Meshtastic_tool\meshtastic_mass_com.listen.cfg)
- Default send history: [meshtastic_mass_com.send.history.jsonl](C:\Users\richt\Documents\Codex\Meshtastic_tool\meshtastic_mass_com.send.history.jsonl)
- Default listen history: [meshtastic_mass_com.listen.history.jsonl](C:\Users\richt\Documents\Codex\Meshtastic_tool\meshtastic_mass_com.listen.history.jsonl)
- German documentation: [README.de.md](C:\Users\richt\Documents\Codex\Meshtastic_tool\README.de.md)

## First Run

If no matching config file exists yet, start the script once with parameters so it can create one.

Config selection rules:

- No parameters, or `--mode send`, `--mode broadcast`, `--mode history`
  - Use the send config: `meshtastic_mass_com.send.cfg`
- `--listen` or `--mode listen`
  - Use the listen config: `meshtastic_mass_com.listen.cfg`

Example:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --channel-index 1 --ack --delay 1.5 --timeout 60 --target-mode select --filter "FR*" --selection "1,3" --retry-implicit-ack 1 --retry-nak 1 --message "Test message" --unattended --forcecfg
```

After that, a plain run is usually enough:

```bash
python ./meshtastic_mass_com.py
```

## Config File Behavior

- No active config + parameters passed:
  - The active config can be created from those parameters.
- Existing active config + parameters passed:
  - Parameters are applied for the current run.
  - Whether the active config is updated depends on `--forcecfg` / `--protectcfg`.
- Existing active config + no parameters passed:
  - The script uses the values from the active config.
- No active config + no parameters passed:
  - The script shows an example command.

## Config Control

Use these switches to make config behavior explicit:

- `--forcecfg`
  - Always create or update the active config when parameters are passed.
- `--protectcfg`
  - Never update the active config for this run, even if parameters are passed.
- `--clear`
  - Delete the active config file and exit.

Examples:

- Clear send config:

```bash
python ./meshtastic_mass_com.py --clear
```

- Clear listen config:

```bash
python ./meshtastic_mass_com.py --listen --clear
```

Store send settings in the send config:

```bash
python ./meshtastic_mass_com.py --port <PORT> --channel-index 1 --message "Hello" --forcecfg
```

Store listen settings in the listen config:

```bash
python ./meshtastic_mass_com.py --listen --port <PORT> --listen-filter "FR*" --text-only --forcecfg
```

## Command-Line Parameters

The most useful parameters are grouped below by purpose.

### Workflow Selection

- `--mode send`
  - Send direct messages to selected recipients.
- `--mode listen` or `--listen`
  - Keep the connection open and print matching incoming packets live.
- `--mode broadcast` or `--broadcast`
  - Send one message to a channel chat instead of a direct-message loop.
- `--mode history` or `--history`
  - Show saved local history entries without connecting to the device.

### Device and Channel

- `--port <PORT>`
  - Select the serial port explicitly. If omitted, the script auto-detects ports or asks.
- `--channel-index 0`
  - Select the channel used for direct messages or broadcasts.
- `--list-ports`
  - Show available serial ports and exit.

### Recipient Selection for Send Mode

- `--target-mode all`
  - Send to all known nodes.
- `--target-mode filter --filter "FR*"`
  - Send only to nodes that match the filter.
- `--target-mode select --filter "FR*" --selection "1,3-5"`
  - Prefilter a list and then send only to selected entries.
- `--filter`
  - Match node ID, short name, or long name. Wildcards such as `FR*` and `*mobil*` are supported.
- `--selection`
  - Comma-separated list indexes or ranges from the displayed candidate list.

### Message and Delivery Control

- `--message "Hello"`
  - Set the message text for send or broadcast mode.
- `--ack`
  - Wait for ACK, implicit ACK, or NAK for each direct message.
- `--retry-implicit-ack 1`
  - Retry when a message was sent but not explicitly confirmed.
- `--retry-nak 1`
  - Retry after a NAK result.
- `--delay 1.5`
  - Pause between recipients and retries.
- `--timeout 60`
  - Timeout for connection and ACK waiting.
- `--final-wait 5`
  - Keep the connection open a little longer after the last transmission when `--ack` is not used.
- `--dry-run`
  - Preview recipients, message, and channel without sending packets.

### Listen Filters

- `--listen-filter "FR*"`
  - Only show packets from matching senders.
- `--listen-channel-index 1`
  - Only show packets from one channel.
- `--dm-only`
  - Only show direct messages.
- `--group-only`
  - Only show group or broadcast traffic.
- `--text-only`
  - Only show text packets and hide telemetry, node info, and other packet types.

### Files and Local History

- `--log-file ./meshtastic_log.jsonl`
  - Append JSONL activity records for send and listen mode.
- `--history-file ./meshtastic_history.jsonl`
  - Override the default local inbox/history file.
  - Default without override:
    - send/broadcast/history -> `meshtastic_mass_com.send.history.jsonl`
    - listen -> `meshtastic_mass_com.listen.history.jsonl`
- `--history-filter "Naunhof"`
  - Filter entries shown in history mode.
- `--history-limit 50`
  - Limit how many recent history entries are shown.

### Configuration Handling

- `--forcecfg`
  - Always write current CLI values into the active cfg.
- `--protectcfg`
  - Never change the active cfg for this run.
- `--clear`
  - Delete the active cfg for the selected cfg family and exit.
- `--unattended`
  - Skip prompts. All required values must then come from the CLI or the active cfg.

## Target Selection

The script can send:

- to all known nodes
- to filtered nodes only
- to manually selected nodes from a numbered list, optionally after prefiltering

Interactive mode:

```bash
python ./meshtastic_mass_com.py
```

You will be asked to choose:

- `1` for all known nodes
- `2` for filtered sending
- `3` for manual list selection

Direct parameter examples:

```bash
python ./meshtastic_mass_com.py --target-mode all
python ./meshtastic_mass_com.py --target-mode filter --filter "FR*"
python ./meshtastic_mass_com.py --target-mode filter --filter "!55d8c9dc"
python ./meshtastic_mass_com.py --target-mode filter --filter "Rico"
python ./meshtastic_mass_com.py --target-mode select --filter "FR*"
python ./meshtastic_mass_com.py --target-mode select --filter "FR*" --selection "1,3-4" --unattended
```

Filter rules:

- With wildcards such as `FR*` or `*mobil*`, the filter is treated as a pattern.
- Without wildcards, partial matches are allowed.
- Matching is performed against node ID, short name, and long name.

## Message and Unattended Mode

You can store a default message in the config:

```bash
python ./meshtastic_mass_com.py --message "Hello everyone" --forcecfg
```

Run without prompts:

```bash
python ./meshtastic_mass_com.py --unattended
```

Typical unattended run:

```bash
python ./meshtastic_mass_com.py --port <PORT> --channel-index 1 --ack --target-mode filter --filter "FR*" --message "Hello everyone" --unattended --forcecfg
```

In unattended mode:

- no message prompt
- no target selection prompt
- no send confirmation prompt
- required values must come from parameters or the config

## ACK Handling

With `--ack`, the script waits for a response per message.

Possible outcomes:

- `Received an ACK.`
  - Delivery was acknowledged.
- `Sent, but not confirmed (implicit ACK only).`
  - The packet was sent, but not explicitly confirmed.
- `Received a NAK, error reason: ...`
  - Delivery failed with a negative acknowledgment.
- `Error ... No ACK/NAK ...`
  - Timeout without a response.

Retry controls:

- `--retry-implicit-ack 1`
  - Retry once if a packet only receives an implicit ACK.
- `--retry-nak 1`
  - Retry once if a packet receives a NAK.

Example:

```bash
python ./meshtastic_mass_com.py --port <PORT> --channel-index 1 --ack --delay 1.5 --timeout 60 --retry-implicit-ack 1 --retry-nak 1
```

## Listen Mode

The script can also stay connected and print matching incoming packets live.

Examples:

```bash
python ./meshtastic_mass_com.py --mode listen
python ./meshtastic_mass_com.py --listen --listen-filter "FR*"
python ./meshtastic_mass_com.py --listen --listen-channel-index 1
python ./meshtastic_mass_com.py --listen --dm-only
python ./meshtastic_mass_com.py --listen --group-only --text-only
```

Listen filters:

- `--listen-filter`
  - Matches sender node ID, short name, or long name
- `--listen-channel-index`
  - Only show packets from one channel
- `--dm-only`
  - Only show direct messages
- `--group-only`
  - Only show group/broadcast traffic
- `--text-only`
  - Only show text packets

Stop listen mode with `Ctrl+C`.

## Logging

Use `--log-file` to append JSONL records for send attempts and received packets.

Examples:

```bash
python ./meshtastic_mass_com.py --mode send --log-file ./meshtastic_log.jsonl
python ./meshtastic_mass_com.py --listen --log-file ./meshtastic_log.jsonl
```

## Broadcast Mode

Use broadcast mode to send one message to the selected channel instead of a direct-message loop.

Examples:

```bash
python ./meshtastic_mass_com.py --mode broadcast --port <PORT> --channel-index 0 --message "Hello private group"
python ./meshtastic_mass_com.py --broadcast --port <PORT> --channel-index 1 --message "Hello LongFast"
```

Notes:

- Broadcast mode ignores `--ack`
- Broadcast mode sends once to the selected channel
- This is usually the right mode when you want the message to appear in the group/channel chat

## Dry Run

Use `--dry-run` to preview what would be sent without transmitting any packets.

Examples:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --target-mode select --filter "FR*" --selection "1,3" --message "Preview only" --dry-run
python ./meshtastic_mass_com.py --mode broadcast --port <PORT> --channel-index 1 --message "Preview group post" --dry-run
```

## History

The script stores local history files for received packets and sent messages. You can review them later without connecting to the device.

Default separation:

- send / broadcast / history mode
  - `meshtastic_mass_com.send.history.jsonl`
- listen mode
  - `meshtastic_mass_com.listen.history.jsonl`

Examples:

```bash
python ./meshtastic_mass_com.py --mode history
python ./meshtastic_mass_com.py --history --history-limit 50
python ./meshtastic_mass_com.py --history --history-filter "Naunhof"
python ./meshtastic_mass_com.py --history --history-file ./logs/history.jsonl
```

## Example Workflows

### Quick Everyday Use

Use the script interactively and let it guide you:

```bash
python ./meshtastic_mass_com.py
```

Send a direct message to all known nodes using your selected serial port:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --target-mode all --message "Hello all"
```

Listen using your selected serial port and only show text traffic:

```bash
python ./meshtastic_mass_com.py --listen --port <PORT> --text-only
```

Post once to the channel chat instead of sending DMs:

```bash
python ./meshtastic_mass_com.py --mode broadcast --port <PORT> --channel-index 1 --message "Hello group"
```

### Filtered Send Workflows

Send only to nodes matching a callsign pattern:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --channel-index 1 --target-mode filter --filter "FR*" --message "Net check" --ack
```

Send only to one exact node ID:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --channel-index 1 --target-mode filter --filter "!55d8c9dc" --message "Private test" --ack
```

Prefilter the list, then manually choose recipients:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --channel-index 1 --target-mode select --filter "FR*"
```

Run the same selection unattended with saved indexes:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --channel-index 1 --target-mode select --filter "FR*" --selection "1,3-5" --message "Scheduled ping" --unattended
```

### Reliable Delivery Workflows

Request ACKs and retry once on implicit ACK or NAK:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --channel-index 1 --target-mode filter --filter "FR*" --message "Please confirm" --ack --retry-implicit-ack 1 --retry-nak 1 --delay 1.5 --timeout 60
```

Use channel `0` for a small private group, but do not overwrite the saved cfg:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --channel-index 0 --target-mode select --selection "1-3" --message "Private check-in" --ack --protectcfg
```

### Listen Workflows

Listen only to LongFast traffic on channel `1`:

```bash
python ./meshtastic_mass_com.py --listen --port <PORT> --listen-channel-index 1
```

Listen only to direct messages from nodes matching `FR*`:

```bash
python ./meshtastic_mass_com.py --listen --port <PORT> --listen-filter "FR*" --dm-only --text-only
```

Listen only to group traffic and keep non-text packets visible:

```bash
python ./meshtastic_mass_com.py --listen --port <PORT> --group-only
```

### Logging Workflows

Send with ACK handling and write all attempts to a JSONL log:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --channel-index 1 --target-mode filter --filter "FR*" --message "Logged test" --ack --retry-implicit-ack 1 --retry-nak 1 --log-file ./logs/send_log.jsonl
```

Listen continuously and append all matching packets to a shared log:

```bash
python ./meshtastic_mass_com.py --listen --port <PORT> --text-only --log-file ./logs/listen_log.jsonl
```

Override the default listen history file while listening:

```bash
python ./meshtastic_mass_com.py --listen --port <PORT> --text-only --history-file ./logs/history.jsonl
```

### Config-Centered Workflows

Create or refresh a reusable unattended profile:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --channel-index 1 --target-mode select --filter "FR*" --selection "1,2" --message "Routine message" --ack --retry-implicit-ack 1 --retry-nak 1 --log-file ./logs/routine.jsonl --unattended --forcecfg
```

Run later with only the saved config:

```bash
python ./meshtastic_mass_com.py
```

Listen with temporary settings but keep the saved config untouched:

```bash
python ./meshtastic_mass_com.py --listen --port <PORT> --listen-filter "FR*" --dm-only --text-only --protectcfg
```

Preview a broadcast without changing the config or transmitting:

```bash
python ./meshtastic_mass_com.py --mode broadcast --port <PORT> --channel-index 0 --message "Test group" --dry-run --protectcfg
```

## Help

Use the built-in CLI help for the complete current parameter list:

```bash
python ./meshtastic_mass_com.py --help
```

## Notes

- This tool is intended for controlled direct-message workflows.
- Please respect local radio regulations, duty-cycle limits, and other operators on the mesh.





