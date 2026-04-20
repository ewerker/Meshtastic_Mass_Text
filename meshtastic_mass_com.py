"""Meshtastic_Mass_Com.

Copyright (c) 2026 Frank Richter, https://w-2.de
SPDX-License-Identifier: MIT
"""

import argparse
import configparser
import fnmatch
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from meshtastic.serial_interface import SerialInterface
from pubsub import pub
from serial.tools import list_ports
from meshtastic_mass_com_version import APP_NAME, APP_VERSION

SCRIPT_PATH = Path(__file__)
SCRIPT_STEM = SCRIPT_PATH.stem
SEND_CONFIG_PATH = SCRIPT_PATH.with_name(f"{SCRIPT_STEM}.send.cfg")
LISTEN_CONFIG_PATH = SCRIPT_PATH.with_name(f"{SCRIPT_STEM}.listen.cfg")
AUTORESPONDER_CONFIG_PATH = SCRIPT_PATH.with_name(f"{SCRIPT_STEM}.autoresponder.cfg")
SEND_HISTORY_PATH = SCRIPT_PATH.with_name(f"{SCRIPT_STEM}.send.history.jsonl")
LISTEN_HISTORY_PATH = SCRIPT_PATH.with_name(f"{SCRIPT_STEM}.listen.history.jsonl")
CONFIG_SECTION = "settings"
DEFAULT_SETTINGS = {
    "mode": "send",
    "port": "",
    "channel_index": 0,
    "ack": False,
    "include_unmessageable": False,
    "delay": 0.5,
    "timeout": 30,
    "final_wait": 5.0,
    "target_mode": "all",
    "target_filter": "",
    "selection": "",
    "message": "",
    "unattended": False,
    "log_file": "",
    "log_rotate_max_mb": 10,
    "log_rotate_backups": 5,
    "listen_filter": "",
    "listen_channel_index": None,
    "listen_dm_only": False,
    "listen_group_only": False,
    "listen_text_only": False,
    "listen_verbose": False,
    "autoresponder": False,
    "autoresponder_unicast": False,
    "autoresponder_sender_mode": "all",
    "autoresponder_sender_filter": "",
    "autoresponder_message_mode": "filter",
    "autoresponder_message_filter": "!Ping",
    "autoresponder_reply": "Pong",
    "autoresponder_reply_template": "Autoresponder : %shortname%: %message% / Message:  %answer%",
    "retry_implicit_ack": 0,
    "retry_nak": 0,
    "dry_run": False,
    "history_file": "",
    "history_filter": "",
    "history_limit": 20,
}
SETTING_TYPES = {
    "mode": "str",
    "port": "str",
    "channel_index": "int",
    "ack": "bool",
    "include_unmessageable": "bool",
    "delay": "float",
    "timeout": "int",
    "final_wait": "float",
    "target_mode": "str",
    "target_filter": "str",
    "selection": "str",
    "message": "str",
    "unattended": "bool",
    "log_file": "str",
    "log_rotate_max_mb": "int",
    "log_rotate_backups": "int",
    "listen_filter": "str",
    "listen_channel_index": "optional_int",
    "listen_dm_only": "bool",
    "listen_group_only": "bool",
    "listen_text_only": "bool",
    "listen_verbose": "bool",
    "autoresponder": "bool",
    "autoresponder_unicast": "bool",
    "autoresponder_sender_mode": "str",
    "autoresponder_sender_filter": "str",
    "autoresponder_message_mode": "str",
    "autoresponder_message_filter": "str",
    "autoresponder_reply": "str",
    "autoresponder_reply_template": "str",
    "retry_implicit_ack": "int",
    "retry_nak": "int",
    "dry_run": "bool",
    "history_file": "str",
    "history_filter": "str",
    "history_limit": "int",
}
SEND_CONFIG_KEYS = (
    "mode",
    "port",
    "channel_index",
    "ack",
    "include_unmessageable",
    "delay",
    "timeout",
    "final_wait",
    "target_mode",
    "target_filter",
    "selection",
    "message",
    "unattended",
    "log_file",
    "log_rotate_max_mb",
    "log_rotate_backups",
    "retry_implicit_ack",
    "retry_nak",
    "dry_run",
    "history_file",
    "history_filter",
    "history_limit",
)
LISTEN_CONFIG_KEYS = (
    "mode",
    "port",
    "timeout",
    "listen_filter",
    "listen_channel_index",
    "listen_dm_only",
    "listen_group_only",
    "listen_text_only",
    "listen_verbose",
    "unattended",
    "log_file",
    "log_rotate_max_mb",
    "log_rotate_backups",
    "history_file",
    "history_filter",
    "history_limit",
)
AUTORESPONDER_CONFIG_KEYS = (
    "autoresponder",
    "autoresponder_unicast",
    "autoresponder_sender_mode",
    "autoresponder_sender_filter",
    "autoresponder_message_mode",
    "autoresponder_message_filter",
    "autoresponder_reply",
    "autoresponder_reply_template",
)
AUTORESPONDER_SEND_KEYS = (
    "ack",
    "channel_index",
    "include_unmessageable",
    "delay",
    "target_mode",
    "target_filter",
    "selection",
    "timeout",
    "retry_implicit_ack",
    "retry_nak",
)
AUTORESPONDER_SEND_KEY_MAP = {
    "ack": "autoresponder_send_ack",
    "channel_index": "autoresponder_send_channel_index",
    "include_unmessageable": "autoresponder_send_include_unmessageable",
    "delay": "autoresponder_send_delay",
    "target_mode": "autoresponder_send_target_mode",
    "target_filter": "autoresponder_send_target_filter",
    "selection": "autoresponder_send_selection",
    "timeout": "autoresponder_send_timeout",
    "retry_implicit_ack": "autoresponder_send_retry_implicit_ack",
    "retry_nak": "autoresponder_send_retry_nak",
}
LISTEN_HOT_RELOAD_KEYS = (
    "listen_filter",
    "listen_channel_index",
    "listen_dm_only",
    "listen_group_only",
    "listen_text_only",
    "listen_verbose",
    "unattended",
    "log_file",
    "log_rotate_max_mb",
    "log_rotate_backups",
    "history_file",
    "history_filter",
    "history_limit",
)
LISTEN_RESTART_REQUIRED_KEYS = (
    "port",
    "timeout",
)
SEND_PREP_HOT_RELOAD_KEYS = (
    "message",
    "channel_index",
    "ack",
    "include_unmessageable",
    "delay",
    "timeout",
    "final_wait",
    "target_mode",
    "target_filter",
    "selection",
    "unattended",
    "log_file",
    "log_rotate_max_mb",
    "log_rotate_backups",
    "retry_implicit_ack",
    "retry_nak",
    "dry_run",
    "history_file",
    "history_filter",
    "history_limit",
)
SEND_ACTIVE_HOT_RELOAD_KEYS = (
    "channel_index",
    "ack",
    "delay",
    "timeout",
    "final_wait",
    "log_file",
    "log_rotate_max_mb",
    "log_rotate_backups",
    "retry_implicit_ack",
    "retry_nak",
    "history_file",
)
SEND_RESTART_REQUIRED_KEYS = (
    "port",
)

ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_COLORS = {
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
}
LOG_ROTATION_POLICY: dict[str, tuple[int, int]] = {}


def init_console_colors() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        if handle == 0:
            return False
        mode = ctypes.c_uint()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)) == 0:
            return False
        enable_vt = 0x0004
        if mode.value & enable_vt:
            return True
        return kernel32.SetConsoleMode(handle, mode.value | enable_vt) != 0
    except Exception:
        return False


COLOR_ENABLED = init_console_colors()


def colorize(text: str, color: str | None = None, *, bold: bool = False) -> str:
    if not COLOR_ENABLED:
        return text
    parts = []
    if bold:
        parts.append(ANSI_BOLD)
    if color:
        parts.append(ANSI_COLORS[color])
    parts.append(text)
    parts.append(ANSI_RESET)
    return "".join(parts)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} v{APP_VERSION} - communicate with Meshtastic through direct messages, group broadcasts, live listening, logging, and local history."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {APP_VERSION}",
    )
    parser.add_argument(
        "--mode",
        choices=("send", "listen", "broadcast", "history"),
        default=None,
        help="Workflow to run: send direct messages, listen live, broadcast once to a channel, or show local history.",
    )
    parser.add_argument(
        "--listen",
        action="store_true",
        help="Shortcut for --mode listen.",
    )
    parser.add_argument(
        "--autoresponder",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="In listen mode, enable or disable the autoresponder runtime. Detailed autoresponder rules come from the dedicated autoresponder cfg.",
    )
    parser.add_argument(
        "--broadcast",
        action="store_true",
        help="Shortcut for --mode broadcast.",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Shortcut for --mode history.",
    )
    parser.add_argument(
        "--port",
        default=None,
        help="Serial port of the Meshtastic device, for example COM7, /dev/ttyUSB0, or /dev/ttyACM0. If omitted, ports are auto-detected or selected interactively.",
    )
    parser.add_argument(
        "--channel-index",
        type=int,
        default=None,
        help="Channel index for direct messages or broadcasts. Typical values are 0 for a private/primary channel and 1 for LongFast.",
    )
    parser.add_argument(
        "--ack",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="For direct messages, wait for ACK, implicit ACK, or NAK. Broadcast mode ignores this switch.",
    )
    parser.add_argument(
        "--include-unmessageable",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Also include nodes flagged by Meshtastic as unmessageable. Normally these are skipped.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Delay in seconds between recipients and between retries. Useful to avoid sending too fast.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Timeout in seconds for connecting and for waiting on ACK/NAK results.",
    )
    parser.add_argument(
        "--final-wait",
        type=float,
        default=None,
        help="Extra seconds to keep the connection open after the last transmission when --ack is not used.",
    )
    parser.add_argument(
        "--retry-implicit-ack",
        type=int,
        default=None,
        help="How many times to retry after an implicit ACK, meaning sent but not explicitly confirmed.",
    )
    parser.add_argument(
        "--retry-nak",
        type=int,
        default=None,
        help="How many times to retry after a NAK result.",
    )
    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="List available serial ports and exit without connecting.",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete the active cfg file for the current cfg family and exit. Send/broadcast/history use the send cfg; listen uses the listen cfg.",
    )
    cfg_group = parser.add_mutually_exclusive_group()
    cfg_group.add_argument(
        "--forcecfg",
        action="store_true",
        help="Always create or update the active cfg from the current command-line parameters.",
    )
    cfg_group.add_argument(
        "--protectcfg",
        action="store_true",
        help="Never change the active cfg for this run, even when parameters are passed.",
    )
    parser.add_argument(
        "--target-mode",
        choices=("all", "filter", "select"),
        default=None,
        help="Recipient selection for send mode: all known nodes, only filtered matches, or a manual selection from a numbered list.",
    )
    parser.add_argument(
        "--filter",
        dest="target_filter",
        default=None,
        help="Filter for send-mode node selection, for example !55d8c9dc, Rico, Naunhof, or FR*.",
    )
    parser.add_argument(
        "--selection",
        default=None,
        help="Comma-separated 1-based indexes or ranges from the displayed list, for example 1,3-5. Used with --target-mode select.",
    )
    parser.add_argument(
        "--message",
        default=None,
        help="Message text for direct messages or broadcasts. If omitted, the script asks interactively unless a value exists in the cfg.",
    )
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Preview recipients, message, and channel without sending any packets.",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Optional JSONL activity log. Relative paths are resolved next to the script.",
    )
    parser.add_argument(
        "--history-file",
        default=None,
        help="Optional JSONL inbox/history file. Relative paths are resolved next to the script.",
    )
    parser.add_argument(
        "--history-filter",
        default=None,
        help="In history mode, only show entries whose sender, recipient, or text matches this filter.",
    )
    parser.add_argument(
        "--history-limit",
        type=int,
        default=None,
        help="Maximum number of recent entries to show in history mode.",
    )
    parser.add_argument(
        "--listen-filter",
        default=None,
        help="In listen mode, only show packets whose sender matches this filter.",
    )
    parser.add_argument(
        "--listen-channel-index",
        type=int,
        default=None,
        help="In listen mode, only show packets received on this channel index.",
    )
    listen_scope_group = parser.add_mutually_exclusive_group()
    listen_scope_group.add_argument(
        "--dm-only",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="In listen mode, only show direct messages.",
    )
    listen_scope_group.add_argument(
        "--group-only",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="In listen mode, only show group or broadcast traffic.",
    )
    parser.add_argument(
        "--text-only",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="In listen mode, only show text packets and hide telemetry, node info, and other packet types.",
    )
    parser.add_argument(
        "--verbose-listen",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="In listen mode, also print the full received record as JSON, similar to the receive log.",
    )
    parser.add_argument(
        "-u",
        "--unattended",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Run without confirmation prompts. All required values must then come from the CLI or the active cfg.",
    )
    return parser


def example_command() -> str:
    return example_command_for_family("send")


def example_command_for_family(config_family: str) -> str:
    if config_family == "listen":
        return (
            'python ./meshtastic_mass_com.py --listen --port <PORT> --listen-filter "FR*" '
            '--listen-channel-index 1 --dm-only --text-only --verbose-listen --log-file "./listen_log.jsonl" '
            '--history-file "./meshtastic_mass_com.listen.history.jsonl" --unattended --forcecfg'
        )
    if config_family == "autoresponder":
        return (
            'python ./meshtastic_mass_com.py --listen --autoresponder'
        )
    return (
        'python ./meshtastic_mass_com.py --mode send --port <PORT> --channel-index 1 --ack '
        '--delay 1.5 --timeout 60 --target-mode select --filter "FR*" --selection "1,3" '
        '--retry-implicit-ack 1 --retry-nak 1 --message "Test message" --unattended '
        '--history-file "./meshtastic_mass_com.send.history.jsonl" --forcecfg'
    )


def determine_config_family(args: argparse.Namespace) -> str:
    if getattr(args, "listen", False) or getattr(args, "mode", None) == "listen":
        return "listen"
    return "send"


def config_path_for_family(config_family: str) -> Path:
    if config_family == "listen":
        return LISTEN_CONFIG_PATH
    if config_family == "autoresponder":
        return AUTORESPONDER_CONFIG_PATH
    return SEND_CONFIG_PATH


def history_path_for_family(config_family: str) -> Path:
    return LISTEN_HISTORY_PATH if config_family == "listen" else SEND_HISTORY_PATH


def config_keys_for_family(config_family: str) -> tuple[str, ...]:
    if config_family == "listen":
        return LISTEN_CONFIG_KEYS
    if config_family == "autoresponder":
        return AUTORESPONDER_CONFIG_KEYS
    return SEND_CONFIG_KEYS


def defaults_for_family(config_family: str) -> dict:
    settings = DEFAULT_SETTINGS.copy()
    if config_family == "listen":
        settings["mode"] = "listen"
        settings["history_file"] = history_path_for_family(config_family).name
    elif config_family == "send":
        settings["mode"] = "send"
        settings["history_file"] = history_path_for_family(config_family).name
    return settings


def persistable_settings(settings: dict, config_family: str) -> dict:
    persisted = defaults_for_family(config_family)
    for key in config_keys_for_family(config_family):
        persisted[key] = settings.get(key, persisted[key])
    if config_family in {"send", "listen"} and not persisted.get("history_file"):
        persisted["history_file"] = history_path_for_family(config_family).name
    if config_family == "listen":
        persisted["mode"] = "listen"
    elif persisted["mode"] == "listen":
        persisted["mode"] = "send"
    return persisted


def load_config(config_path: Path, config_family: str | None = None) -> dict:
    settings, _sources = load_config_with_sources(config_path, config_family)
    return settings


def parse_config_value(section: configparser.SectionProxy, key: str, value_type: str):
    if value_type == "bool":
        return section.getboolean(key)
    if value_type == "int":
        return section.getint(key)
    if value_type == "float":
        return section.getfloat(key)
    if value_type == "optional_int":
        raw = section.get(key, fallback="")
        return int(raw) if raw else None
    return section.get(key)


def load_config_with_sources(config_path: Path, config_family: str | None = None) -> tuple[dict, dict]:
    resolved_family = config_family or (
        "listen" if config_path == LISTEN_CONFIG_PATH else "autoresponder" if config_path == AUTORESPONDER_CONFIG_PATH else "send"
    )
    settings = defaults_for_family(resolved_family)
    sources = {key: "default" for key in DEFAULT_SETTINGS}
    if not config_path.exists():
        return settings, sources

    parser = configparser.ConfigParser(interpolation=None)
    parser.read(config_path, encoding="utf-8")
    if not parser.has_section(CONFIG_SECTION):
        return settings, sources

    section = parser[CONFIG_SECTION]
    for key in config_keys_for_family(resolved_family):
        value_type = SETTING_TYPES[key]
        if section.get(key, fallback=None) is None:
            continue
        settings[key] = parse_config_value(section, key, value_type)
        sources[key] = f"{resolved_family}_cfg"
    return settings, sources


def format_source_label(source: str) -> str:
    colors = {
        "cmd": "cyan",
        "send_cfg": "green",
        "listen_cfg": "green",
        "autoresponder_cfg": "green",
        "default": "yellow",
        "auto": "magenta",
        "prompt": "blue",
    }
    return colorize(f"[{source}]", colors.get(source, "white"), bold=True)


def format_effective_value(value) -> str:
    if value is None or value == "":
        return "<empty>"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def print_effective_parameters(settings: dict, mode_label: str, fields: list[tuple[str, object]]) -> None:
    print()
    print(colorize(f"Effective parameters for {mode_label}:", "cyan", bold=True))
    config_path = settings.get("__config_path")
    config_family = settings.get("__config_family")
    if config_path:
        config_label = f"{config_family} cfg file" if config_family else "cfg file"
        print(f"  {config_label}: {config_path}")
    autoresponder_config_path = settings.get("__autoresponder_config_path")
    if autoresponder_config_path:
        print(f"  autoresponder cfg file: {autoresponder_config_path}")
    send_config_path = settings.get("__send_config_path")
    if send_config_path:
        print(f"  send cfg file: {send_config_path}")
    for field in fields:
        if len(field) == 3:
            source_key, display_key, value = field
        else:
            source_key, value = field
            display_key = source_key
        source = settings.get("__sources", {}).get(source_key, "default")
        print(f"  {format_source_label(source)} {display_key} = {format_effective_value(value)}")


def config_file_values(settings: dict, config_family: str) -> dict[str, str]:
    settings = persistable_settings(settings, config_family)
    return {
        "mode": settings["mode"] or "send",
        "port": settings["port"] or "",
        "channel_index": str(settings["channel_index"]),
        "ack": str(settings["ack"]).lower(),
        "include_unmessageable": str(settings["include_unmessageable"]).lower(),
        "delay": str(settings["delay"]),
        "timeout": str(settings["timeout"]),
        "final_wait": str(settings["final_wait"]),
        "target_mode": settings["target_mode"] or "all",
        "target_filter": settings["target_filter"] or "",
        "selection": settings["selection"] or "",
        "message": settings["message"] or "",
        "unattended": str(settings["unattended"]).lower(),
        "log_file": settings["log_file"] or "",
        "log_rotate_max_mb": str(settings["log_rotate_max_mb"]),
        "log_rotate_backups": str(settings["log_rotate_backups"]),
        "listen_filter": settings["listen_filter"] or "",
        "listen_channel_index": "" if settings["listen_channel_index"] is None else str(settings["listen_channel_index"]),
        "listen_dm_only": str(settings["listen_dm_only"]).lower(),
        "listen_group_only": str(settings["listen_group_only"]).lower(),
        "listen_text_only": str(settings["listen_text_only"]).lower(),
        "listen_verbose": str(settings["listen_verbose"]).lower(),
        "autoresponder": str(settings["autoresponder"]).lower(),
        "autoresponder_unicast": str(settings["autoresponder_unicast"]).lower(),
        "autoresponder_sender_mode": settings["autoresponder_sender_mode"] or "all",
        "autoresponder_sender_filter": settings["autoresponder_sender_filter"] or "",
        "autoresponder_message_mode": settings["autoresponder_message_mode"] or "filter",
        "autoresponder_message_filter": settings["autoresponder_message_filter"] or "",
        "autoresponder_reply": settings["autoresponder_reply"] or "",
        "autoresponder_reply_template": settings["autoresponder_reply_template"] or "",
        "retry_implicit_ack": str(settings["retry_implicit_ack"]),
        "retry_nak": str(settings["retry_nak"]),
        "dry_run": str(settings["dry_run"]).lower(),
        "history_file": settings["history_file"] or "",
        "history_filter": settings["history_filter"] or "",
        "history_limit": str(settings["history_limit"]),
    }


def render_config_text(settings: dict, config_family_or_path) -> str:
    if isinstance(config_family_or_path, Path):
        if config_family_or_path == LISTEN_CONFIG_PATH:
            config_family = "listen"
        elif config_family_or_path == AUTORESPONDER_CONFIG_PATH:
            config_family = "autoresponder"
        else:
            config_family = "send"
    else:
        config_family = str(config_family_or_path)
    values = config_file_values(settings, config_family)
    active_modes = "listen" if config_family == "listen" else "autoresponder" if config_family == "autoresponder" else "send, broadcast, history"
    family_title = "Listen workflow" if config_family == "listen" else "Autoresponder" if config_family == "autoresponder" else "Send workflow"
    example = example_command_for_family(config_family)

    lines = [
        f"# Meshtastic_Mass_Com - {family_title} configuration",
        f"# Version: {APP_VERSION}",
        "# Copyright (c) 2026 Frank Richter, https://w-2.de",
        "# SPDX-License-Identifier: MIT",
        "#",
        f"# This file is the default cfg for: {active_modes}",
        "# It is created or updated by the script when parameters are passed without --protectcfg,",
        "# or explicitly when --forcecfg is used.",
        "# The CLI parameter names map directly to the keys below.",
        "# Boolean values use true / false.",
        "# Empty values mean: use built-in defaults or ask interactively when needed.",
        "# Relative paths are resolved next to the script.",
        "# Example command that creates or updates this cfg:",
        f"# {example}",
        "# Key parameter groups:",
        "# --mode / --listen / --broadcast / --history select the workflow.",
        "# --port and --channel-index select device and channel.",
        "# --target-mode / --filter / --selection control send-mode recipients.",
        "# --ack / --retry-implicit-ack / --retry-nak control delivery handling.",
        "# --listen-filter / --listen-channel-index / --dm-only / --group-only / --text-only / --verbose-listen control listen-mode filtering and output.",
        "# --log-file plus log rotation settings control JSONL log growth.",
        "# --log-file / --history-file / --history-filter / --history-limit control local files and history output.",
        "# --forcecfg / --protectcfg / --clear control cfg handling.",
        "# Notes for this cfg family:",
    ]

    if config_family == "listen":
        lines.extend(
            [
                "# - This cfg is used by --listen or --mode listen.",
                "# - Only listen-related keys are persisted here.",
                "# - Send-mode parameters passed on the CLI affect only the current run and are not written to this cfg.",
            ]
        )
    elif config_family == "autoresponder":
        lines.extend(
            [
                "# - This cfg controls autoresponder behavior for listen mode.",
                "# - The CLI only toggles autoresponder on or off; matching rules and reply text come from this cfg.",
            ]
        )
    else:
        lines.extend(
            [
                "# - This cfg is used by default runs and by --mode send, --mode broadcast, and --mode history.",
                "# - Only send/broadcast/history-related keys are persisted here.",
                "# - Listen-mode parameters passed on the CLI affect only the current run and are not written to this cfg.",
            ]
        )

    lines.extend(["", f"[{CONFIG_SECTION}]", ""])
    if config_family == "listen":
        lines.extend(
            [
                "# Workflow",
                "# Stored mode for this cfg family. This file is always listen-focused.",
                "# Allowed values here: listen",
                "mode = listen",
                "",
                "# Connection",
                "# Serial port such as COM7, /dev/ttyUSB0, or /dev/ttyACM0. Leave empty to auto-detect or ask.",
                f"port = {values['port']}",
                "# Timeout in seconds for the connection attempt.",
                f"timeout = {values['timeout']}",
                "",
                "# Listen filters",
                "# Sender filter for receive mode, for example FR* or !55d8c9dc.",
                f"listen_filter = {values['listen_filter']}",
                "# Only show received packets for this channel index. Empty = all channels.",
                f"listen_channel_index = {values['listen_channel_index']}",
                "# true shows only direct messages while listening.",
                f"listen_dm_only = {values['listen_dm_only']}",
                "# true shows only group or broadcast traffic while listening.",
                f"listen_group_only = {values['listen_group_only']}",
                "# true shows only text packets while listening.",
                f"listen_text_only = {values['listen_text_only']}",
                "# true also prints the full received record as JSON, similar to the receive log.",
                f"listen_verbose = {values['listen_verbose']}",
                "",
                "# Runtime",
                "# true skips interactive prompts such as serial port selection.",
                f"unattended = {values['unattended']}",
                "",
                "# Files",
                "# Optional JSONL log file for listen activity.",
                f"log_file = {values['log_file']}",
                "# Maximum size in MB before the log file rotates to .1, .2, ...",
                f"log_rotate_max_mb = {values['log_rotate_max_mb']}",
                "# Number of rotated log files to keep. 0 disables rotation.",
                f"log_rotate_backups = {values['log_rotate_backups']}",
                "# Optional JSONL history or inbox file for listen/history workflows.",
                f"history_file = {values['history_file']}",
                "# Filter applied by history mode when showing saved entries.",
                f"history_filter = {values['history_filter']}",
                "# Number of recent history entries to show in history mode.",
                f"history_limit = {values['history_limit']}",
                "",
            ]
        )
    elif config_family == "autoresponder":
        lines.extend(
            [
                "# Workflow",
                "# true enables the autoresponder in listen mode by default.",
                f"autoresponder = {values['autoresponder']}",
                "# true sends direct replies to the recipients selected by the send cfg instead of only back to the triggering sender.",
                f"autoresponder_unicast = {values['autoresponder_unicast']}",
                "",
                "# Sender matching",
                "# all = accept every sender, filter = only matching senders.",
                f"autoresponder_sender_mode = {values['autoresponder_sender_mode']}",
                "# Sender filter for node ID, short name, or long name. Wildcards such as JR* are supported.",
                f"autoresponder_sender_filter = {values['autoresponder_sender_filter']}",
                "",
                "# Message matching",
                "# all = answer every matching sender, filter = only when the message text matches.",
                f"autoresponder_message_mode = {values['autoresponder_message_mode']}",
                "# Message text filter. Wildcards such as !Ping* are supported; without wildcards it behaves like a contains match.",
                f"autoresponder_message_filter = {values['autoresponder_message_filter']}",
                "",
                "# Reply",
                "# Direct message text sent back to the original sender.",
                f"autoresponder_reply = {values['autoresponder_reply']}",
                "# Optional reply template with variables from the triggering message.",
                "# Available variables: %node_id%, %label%, %shortname%, %longname%, %message%, %channel_index%, %channel_name%, %scope%, %answer%",
                "# %answer% is replaced with the configured autoresponder_reply text.",
                "# Example: Autoresponder : %shortname%: %message% / Message:  %answer%",
                f"autoresponder_reply_template = {values['autoresponder_reply_template']}",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "# Workflow",
                f"# Stored mode for this cfg family. Typical default here: {values['mode']}.",
                "# Allowed values here: send | broadcast | history",
                f"mode = {values['mode']}",
                "",
                "# Connection",
                "# Serial port such as COM7, /dev/ttyUSB0, or /dev/ttyACM0. Leave empty to auto-detect or ask.",
                f"port = {values['port']}",
                "# Channel index for direct messages or broadcasts, usually 0 or 1.",
                f"channel_index = {values['channel_index']}",
                "",
                "# Sending reliability",
                "# true waits for ACK/NAK for direct messages. Broadcast ignores this.",
                f"ack = {values['ack']}",
                "# true also tries nodes flagged as unmessageable.",
                f"include_unmessageable = {values['include_unmessageable']}",
                "# Delay in seconds between recipients or retries.",
                f"delay = {values['delay']}",
                "# Timeout in seconds for connection and ACK waiting.",
                f"timeout = {values['timeout']}",
                "# Extra wait in seconds after the last transmission when not waiting for ACKs.",
                f"final_wait = {values['final_wait']}",
                "# Retries after implicit ACK results.",
                f"retry_implicit_ack = {values['retry_implicit_ack']}",
                "# Retries after NAK results.",
                f"retry_nak = {values['retry_nak']}",
                "# true shows what would happen without transmitting.",
                f"dry_run = {values['dry_run']}",
                "",
                "# Targeting",
                "# all = every known node, filter = matching nodes only, select = choose from numbered list.",
                f"target_mode = {values['target_mode']}",
                "# Node filter for ID, short name, or long name. Wildcards such as FR* are supported.",
                f"target_filter = {values['target_filter']}",
                "# Number list or ranges from a displayed selection list, for example 1,3-5.",
                f"selection = {values['selection']}",
                "# Default text used for send or broadcast workflows.",
                f"message = {values['message']}",
                "# true skips confirmation prompts. Required values must then come from cfg or CLI.",
                f"unattended = {values['unattended']}",
                "",
                "# Files",
                "# Optional JSONL log file for send/broadcast activity.",
                f"log_file = {values['log_file']}",
                "# Maximum size in MB before the log file rotates to .1, .2, ...",
                f"log_rotate_max_mb = {values['log_rotate_max_mb']}",
                "# Number of rotated log files to keep. 0 disables rotation.",
                f"log_rotate_backups = {values['log_rotate_backups']}",
                "# Optional JSONL history or inbox file for send/history workflows.",
                f"history_file = {values['history_file']}",
                "# Filter applied by history mode when showing saved entries.",
                f"history_filter = {values['history_filter']}",
                "# Number of recent history entries to show in history mode.",
                f"history_limit = {values['history_limit']}",
                "",
            ]
        )
    return "\n".join(lines)


def save_config(settings: dict, config_path: Path, config_family: str | None = None) -> None:
    resolved_family = config_family or ("listen" if config_path == LISTEN_CONFIG_PATH else "autoresponder" if config_path == AUTORESPONDER_CONFIG_PATH else "send")
    with config_path.open("w", encoding="utf-8") as config_file:
        config_file.write(render_config_text(settings, resolved_family))


def create_default_config(config_family: str) -> Path:
    config_path = config_path_for_family(config_family)
    save_config(defaults_for_family(config_family), config_path, config_family)
    print(colorize(f"Configuration created from defaults: {config_path}", "green"))
    return config_path


def ensure_missing_configs(args: argparse.Namespace) -> None:
    no_cli_args = len(sys.argv) == 1
    if no_cli_args:
        for config_family in ("send", "listen", "autoresponder"):
            config_path = config_path_for_family(config_family)
            if not config_path.exists():
                create_default_config(config_family)
        return

    config_family = determine_config_family(args)
    active_config_path = config_path_for_family(config_family)
    if not active_config_path.exists():
        create_default_config(config_family)

    if config_family == "listen" and not AUTORESPONDER_CONFIG_PATH.exists():
        create_default_config("autoresponder")


def rendered_config_text(settings: dict, config_path: Path, config_family: str | None = None) -> str:
    resolved_family = config_family or ("listen" if config_path == LISTEN_CONFIG_PATH else "autoresponder" if config_path == AUTORESPONDER_CONFIG_PATH else "send")
    return render_config_text(settings, resolved_family)


def config_would_change(settings: dict, config_path: Path, config_family: str | None = None) -> bool:
    new_text = rendered_config_text(settings, config_path, config_family)
    if not config_path.exists():
        return True
    try:
        current_text = config_path.read_text(encoding="utf-8")
    except OSError:
        return True
    return current_text != new_text


def confirm_cfg_overwrite(config_path: Path) -> bool:
    print(colorize(f"Warning: existing configuration will be overwritten: {config_path}", "yellow", bold=True))
    answer = input("Overwrite this cfg file? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def collect_cli_overrides(args: argparse.Namespace) -> dict:
    overrides = {}
    for key in (
        "mode",
        "port",
        "channel_index",
        "ack",
        "include_unmessageable",
        "delay",
        "timeout",
        "final_wait",
        "target_mode",
        "target_filter",
        "selection",
        "message",
        "unattended",
        "log_file",
        "listen_filter",
        "listen_channel_index",
        "listen_dm_only",
        "listen_group_only",
        "listen_text_only",
        "listen_verbose",
        "autoresponder",
        "retry_implicit_ack",
        "retry_nak",
        "dry_run",
        "history_file",
        "history_filter",
        "history_limit",
    ):
        value = getattr(args, key, None)
        if value is not None:
            overrides[key] = value

    if args.listen:
        overrides["mode"] = "listen"
    if args.broadcast:
        overrides["mode"] = "broadcast"
    if args.history:
        overrides["mode"] = "history"
    if "selection" in overrides and "target_mode" not in overrides:
        overrides["target_mode"] = "select"
    elif "target_filter" in overrides and "target_mode" not in overrides:
        overrides["target_mode"] = "filter"

    return overrides


def resolve_settings(args: argparse.Namespace) -> dict | None:
    config_family = determine_config_family(args)
    config_path = config_path_for_family(config_family)
    cli_overrides = collect_cli_overrides(args)
    cfg_relevant_overrides = {
        key: value
        for key, value in cli_overrides.items()
        if key in config_keys_for_family(config_family) and key != "mode"
    }
    config_exists = config_path.exists()
    should_write_cfg = bool(cfg_relevant_overrides) and not args.protectcfg

    if not config_exists and not cli_overrides:
        print(f"No configuration file found: {config_path}")
        print("Run the script with parameters the first time, for example:")
        print(example_command_for_family(config_family))
        return None

    settings, sources = load_config_with_sources(config_path, config_family)
    if config_family == "listen":
        autoresponder_settings, autoresponder_sources = load_config_with_sources(AUTORESPONDER_CONFIG_PATH, "autoresponder")
        for key in AUTORESPONDER_CONFIG_KEYS:
            settings[key] = autoresponder_settings[key]
            sources[key] = autoresponder_sources[key]
        send_settings, send_sources = load_config_with_sources(SEND_CONFIG_PATH, "send")
        for key in AUTORESPONDER_SEND_KEYS:
            mapped_key = AUTORESPONDER_SEND_KEY_MAP[key]
            settings[mapped_key] = send_settings[key]
            sources[mapped_key] = send_sources.get(key, "default")

    if cli_overrides:
        settings.update(cli_overrides)
        for key in cli_overrides:
            sources[key] = "cmd"
        if should_write_cfg:
            cfg_changed = config_would_change(settings, config_path, config_family)
            should_save = True
            if config_exists and cfg_changed:
                if args.unattended or args.forcecfg:
                    print(colorize(f"Warning: overwriting existing configuration: {config_path}", "yellow"))
                else:
                    should_save = confirm_cfg_overwrite(config_path)
            if should_save:
                save_config(settings, config_path, config_family)
                if config_exists:
                    if cfg_changed:
                        print(colorize(f"Configuration updated: {config_path}", "green"))
                    else:
                        print(colorize(f"Configuration unchanged: {config_path}", "cyan"))
                else:
                    print(colorize(f"Configuration created: {config_path}", "green"))
            else:
                print(colorize("Configuration update cancelled. Using values for this run only.", "yellow"))
        elif args.protectcfg:
            print(colorize("CFG protection is active, configuration changes will not be saved for this run.", "yellow"))
    elif config_exists:
        print(colorize(f"Using configuration from: {config_path}", "cyan"))

    settings["__sources"] = sources
    settings["__config_path"] = config_path
    settings["__config_family"] = config_family
    if config_family == "listen":
        settings["__autoresponder_config_path"] = AUTORESPONDER_CONFIG_PATH
        settings["__send_config_path"] = SEND_CONFIG_PATH
    return settings


def clear_config(args: argparse.Namespace) -> int:
    config_family = determine_config_family(args)
    config_path = config_path_for_family(config_family)
    if config_path.exists():
        config_path.unlink()
        print(colorize(f"Configuration deleted: {config_path}", "green"))
    else:
        print(colorize(f"No configuration file present: {config_path}", "yellow"))
    return 0


def prompt_message(default_message: str | None = None, unattended: bool = False) -> str:
    if unattended:
        message = (default_message or "").strip()
        if not message:
            raise ValueError("No message is set. Please provide --message or store one in the cfg.")
        return message

    prompt = "Message text to send"
    if default_message:
        prompt += f' [{default_message}]'
    prompt += ": "
    message = input(prompt).strip()
    if not message and default_message:
        message = default_message.strip()
    if not message:
        raise ValueError("Empty messages are not sent.")
    return message


def get_local_node_num(interface: SerialInterface):
    my_info = getattr(interface, "myInfo", None)
    if my_info is None:
        return None

    for attr in ("myNodeNum", "my_node_num"):
        if hasattr(my_info, attr):
            return getattr(my_info, attr)
    return None


def get_available_ports() -> list:
    return list(list_ports.comports())


def print_available_ports(ports: list) -> None:
    if not ports:
        print(colorize("No serial ports found.", "red"))
        return

    print("Available serial ports:")
    for index, port in enumerate(ports, start=1):
        description = port.description or "no description"
        hwid = port.hwid or "no HWID"
        print(f"  {index}. {port.device} - {description} [{hwid}]")


def choose_port_interactively(ports: list) -> str:
    while True:
        choice = input("Which port do you want to use? Enter the number: ").strip()
        if not choice.isdigit():
            print("Please enter a valid number.")
            continue

        selected_index = int(choice)
        if 1 <= selected_index <= len(ports):
            return ports[selected_index - 1].device

        print("That number is outside the list.")


def resolve_port(cli_port: str | None, unattended: bool = False) -> str:
    if cli_port:
        return cli_port

    ports = get_available_ports()
    if not ports:
        raise RuntimeError("No serial ports found. Please connect a device or provide --port.")

    if len(ports) == 1:
        selected = ports[0].device
        print(f"One serial port found, selecting it automatically: {selected}")
        return selected

    if unattended:
        raise RuntimeError(
            "Multiple serial ports found. Please provide --port or save a port in the cfg."
        )

    print_available_ports(ports)
    return choose_port_interactively(ports)


def collect_recipients(interface: SerialInterface, include_unmessageable: bool) -> list[dict]:
    recipients: list[dict] = []
    local_num = get_local_node_num(interface)

    for node_id, node in sorted(interface.nodes.items()):
        user = node.get("user", {})
        if not user:
            continue
        if node.get("num") == local_num:
            continue
        if user.get("isUnmessagable") and not include_unmessageable:
            continue

        recipients.append(
            {
                "node_id": node_id,
                "label": user.get("longName") or user.get("shortName") or node_id,
                "long_name": user.get("longName", ""),
                "short_name": user.get("shortName", ""),
                "last_heard": node.get("lastHeard"),
                "distance_m": (
                    node.get("distance")
                    or node.get("distanceMeters")
                    or node.get("distance_m")
                    or node.get("position", {}).get("distance")
                    or node.get("position", {}).get("distanceMeters")
                    or node.get("position", {}).get("distance_m")
                ),
            }
        )

    return recipients


def format_last_seen(last_heard) -> str:
    if not last_heard:
        return "unknown"
    try:
        timestamp = float(last_heard)
    except (TypeError, ValueError):
        return str(last_heard)

    delta_seconds = max(0, int(time.time() - timestamp))
    if delta_seconds < 60:
        return f"{delta_seconds}s ago"
    if delta_seconds < 3600:
        return f"{delta_seconds // 60}m ago"
    if delta_seconds < 86400:
        return f"{delta_seconds // 3600}h ago"
    return f"{delta_seconds // 86400}d ago"


def format_distance(distance_m) -> str:
    if distance_m in (None, ""):
        return "unknown"
    try:
        meters = float(distance_m)
    except (TypeError, ValueError):
        return str(distance_m)

    if meters < 1000:
        return f"{meters:.0f} m"
    return f"{meters / 1000:.2f} km"


def format_recipient_summary(recipient: dict) -> str:
    short_name = recipient.get("short_name") or "-"
    long_name = recipient.get("long_name") or recipient.get("node_id") or "-"
    last_seen = format_last_seen(recipient.get("last_heard"))
    return f"{long_name} ({short_name}), {recipient['node_id']}, last seen {last_seen}"


def recipient_matches_filter(recipient: dict, target_filter: str) -> bool:
    pattern = target_filter.casefold()
    candidates = [
        recipient["node_id"],
        recipient["label"],
        recipient["short_name"],
        recipient["long_name"],
    ]
    normalized = [candidate.casefold() for candidate in candidates if candidate]

    has_wildcards = any(char in target_filter for char in "*?[]")
    if has_wildcards:
        return any(fnmatch.fnmatch(value, pattern) for value in normalized)

    return any(pattern in value for value in normalized)


def text_matches_filter(text: str | None, value_filter: str) -> bool:
    if text is None:
        return False
    pattern = value_filter.casefold()
    normalized = text.casefold()
    has_wildcards = any(char in value_filter for char in "*?[]")
    if has_wildcards:
        return fnmatch.fnmatch(normalized, pattern)
    return pattern in normalized


def prompt_target_mode(
    cli_target_mode: str | None,
    cli_target_filter: str | None,
    selection: str | None,
    unattended: bool = False,
) -> tuple[str, str | None, str | None]:
    resolved_filter = (cli_target_filter or "").strip() or None
    resolved_selection = (selection or "").strip() or None
    if cli_target_mode == "all":
        return "all", None, resolved_selection
    if cli_target_mode == "filter":
        if resolved_filter:
            return "filter", resolved_filter, resolved_selection
        if unattended:
            raise ValueError("Target mode 'filter' requires --filter or a saved cfg value.")
    if cli_target_mode == "select":
        return "select", resolved_filter, resolved_selection

    if unattended:
        return "all", resolved_filter, resolved_selection

    while True:
        print()
        print("Target selection:")
        print("  1. Send to all known nodes")
        print("  2. Send to all filtered matches")
        print("  3. Select nodes from a list")
        choice = input("Choice [1/2/3]: ").strip().lower()
        if choice in {"1", "all"}:
            return "all", None, None
        if choice in {"2", "filter"}:
            target_filter = input("Enter a filter (for example !55d8c9dc, Rico, or FR*): ").strip()
            if target_filter:
                return "filter", target_filter, None
            print("Please enter a non-empty filter.")
            continue
        if choice in {"3", "select"}:
            target_filter = input(
                "Optional prefilter for the list (for example !55d8c9dc, Rico, or FR*), or press Enter for all: "
            ).strip()
            return "select", target_filter or None, None
        print("Please enter 1, 2, or 3.")


def filter_recipients(recipients: list[dict], target_filter: str | None) -> list[dict]:
    if not target_filter:
        return list(recipients)
    return [recipient for recipient in recipients if recipient_matches_filter(recipient, target_filter)]


def print_recipient_list(recipients: list[dict]) -> None:
    for index, recipient in enumerate(recipients, start=1):
        print(f"  {index:>2}. {format_recipient_summary(recipient)}")


def parse_selection_spec(selection: str, max_index: int) -> list[int]:
    selected: set[int] = set()
    for part in selection.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            if not start_text.strip().isdigit() or not end_text.strip().isdigit():
                raise ValueError(f"Invalid range: {token}")
            start = int(start_text)
            end = int(end_text)
            if start > end:
                raise ValueError(f"Invalid range: {token}")
            for index in range(start, end + 1):
                if not 1 <= index <= max_index:
                    raise ValueError(f"Selection index out of range: {index}")
                selected.add(index)
            continue

        if not token.isdigit():
            raise ValueError(f"Invalid selection entry: {token}")

        index = int(token)
        if not 1 <= index <= max_index:
            raise ValueError(f"Selection index out of range: {index}")
        selected.add(index)

    if not selected:
        raise ValueError("No valid selection entries were provided.")

    return sorted(selected)


def choose_recipients_from_list(
    recipients: list[dict], selection: str | None, unattended: bool = False
) -> tuple[list[dict], str]:
    if not recipients:
        return [], "manual selection"

    print()
    print("Selectable nodes:")
    print_recipient_list(recipients)

    if unattended:
        if not selection:
            raise ValueError("Selection is required in unattended mode when target mode is 'select'.")
        indices = parse_selection_spec(selection, len(recipients))
    else:
        selection_prompt = (
            "Enter selection indexes or ranges (for example 1,3-5)"
            if not selection
            else f"Enter selection indexes or ranges [{selection}]"
        )
        while True:
            raw = input(f"{selection_prompt}: ").strip()
            if not raw and selection:
                raw = selection
            try:
                indices = parse_selection_spec(raw, len(recipients))
                break
            except ValueError as exc:
                print(exc)

    selected = [recipients[index - 1] for index in indices]
    description = f"manual selection [{','.join(str(index) for index in indices)}]"
    return selected, description


def select_recipients(
    recipients: list[dict],
    cli_target_mode: str | None,
    cli_target_filter: str | None,
    selection: str | None,
    unattended: bool = False,
) -> tuple[list[dict], str]:
    target_mode, target_filter, resolved_selection = prompt_target_mode(
        cli_target_mode, cli_target_filter, selection, unattended
    )
    if target_mode == "all":
        return recipients, "all known nodes"

    filtered = filter_recipients(recipients, target_filter)
    if target_mode == "filter":
        return filtered, f'filter "{target_filter}"'

    selected, selection_description = choose_recipients_from_list(filtered, resolved_selection, unattended)
    if target_filter:
        return selected, f'{selection_description} from filter "{target_filter}"'
    return selected, selection_description


def select_recipients_silently(
    recipients: list[dict],
    target_mode: str | None,
    target_filter: str | None,
    selection: str | None,
) -> tuple[list[dict], str]:
    resolved_mode = (target_mode or "all").strip().lower()
    resolved_filter = (target_filter or "").strip() or None
    resolved_selection = (selection or "").strip() or None

    if resolved_mode == "all":
        return list(recipients), "all known nodes"

    filtered = filter_recipients(recipients, resolved_filter)
    if resolved_mode == "filter":
        return filtered, f'filter "{resolved_filter}"'

    if resolved_mode != "select":
        raise ValueError(f"Unsupported target mode for autoresponder unicast: {resolved_mode}")

    if not resolved_selection:
        raise ValueError("Selection is required for autoresponder unicast when send target mode is 'select'.")

    indices = parse_selection_spec(resolved_selection, len(filtered))
    selected = [filtered[index - 1] for index in indices]
    description = f"manual selection [{','.join(str(index) for index in indices)}]"
    if resolved_filter:
        description = f'{description} from filter "{resolved_filter}"'
    return selected, description


def confirm_send(_message: str, recipients: list[dict], _target_description: str, unattended: bool = False) -> bool:
    print()
    print(f"Recipients: {len(recipients)}")
    for recipient in recipients:
        print(f"  - {format_recipient_summary(recipient)}")
    print()
    if unattended:
        print("Unattended mode is active, sending without confirmation.")
        return True
    answer = input("Send now? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def wait_for_ack(interface: SerialInterface, message: str, node_id: str, channel_index: int, timeout: int):
    ack_event = threading.Event()
    ack_result = {"packet": None}

    def onAckNak(packet):
        ack_result["packet"] = packet
        ack_event.set()

    interface._acknowledgment.reset()
    packet = interface.sendText(
        message,
        destinationId=node_id,
        wantAck=True,
        onResponse=onAckNak,
        channelIndex=channel_index,
    )

    if not ack_event.wait(timeout):
        raise TimeoutError(f"No ACK/NAK received within {timeout}s for packet ID {packet.id}")

    return packet, ack_result["packet"]


def classify_ack(interface: SerialInterface, ack_packet: dict | None) -> tuple[str, str]:
    if not ack_packet:
        return "timeout", "No ACK/NAK packet received."

    routing = ack_packet.get("decoded", {}).get("routing", {})
    error_reason = routing.get("errorReason", "NONE")
    if error_reason != "NONE":
        return "nak", f"Received a NAK, error reason: {error_reason}"

    if int(ack_packet.get("from", -1)) == interface.localNode.nodeNum:
        return "implicit_ack", "Sent, but not confirmed (implicit ACK only)."

    return "ack", "Received an ACK."


def now_string() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def resolve_log_path(log_file: str | None) -> Path | None:
    if not log_file:
        return None
    path = Path(log_file)
    if not path.is_absolute():
        path = SCRIPT_PATH.parent / path
    return path


def set_log_rotation_policy(log_path: Path | None, max_mb: int, backups: int) -> None:
    if log_path is None:
        return
    max_bytes = max(0, int(max_mb)) * 1024 * 1024
    LOG_ROTATION_POLICY[str(log_path)] = (max_bytes, max(0, int(backups)))


def rotate_log_if_needed(log_path: Path) -> None:
    max_bytes, backups = LOG_ROTATION_POLICY.get(str(log_path), (0, 0))
    if max_bytes <= 0 or backups <= 0:
        return
    try:
        if not log_path.exists() or log_path.stat().st_size < max_bytes:
            return
    except OSError:
        return

    oldest = log_path.with_name(f"{log_path.name}.{backups}")
    try:
        if oldest.exists():
            oldest.unlink()
    except OSError:
        return

    for index in range(backups - 1, 0, -1):
        src = log_path.with_name(f"{log_path.name}.{index}")
        dst = log_path.with_name(f"{log_path.name}.{index + 1}")
        try:
            if src.exists():
                src.replace(dst)
        except OSError:
            return

    try:
        if log_path.exists():
            log_path.replace(log_path.with_name(f"{log_path.name}.1"))
    except OSError:
        return


def resolve_history_path(history_file: str | None, config_family: str) -> Path:
    if not history_file:
        return history_path_for_family(config_family)
    path = Path(history_file)
    if not path.is_absolute():
        path = SCRIPT_PATH.parent / path
    return path


def sanitize_for_json(value):
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if key == "raw":
                continue
            sanitized[key] = sanitize_for_json(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_for_json(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_for_json(item) for item in value]
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    return value


def append_jsonl(log_path: Path | None, event_type: str, payload: dict) -> None:
    if log_path is None:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rotate_log_if_needed(log_path)
    record = {
        "timestamp": now_string(),
        "event": event_type,
        **payload,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True, default=str) + "\n")


def append_history(history_path: Path, entry_type: str, payload: dict) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": now_string(),
        "entry_type": entry_type,
        **payload,
    }
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True, default=str) + "\n")


def file_mtime_ns(path: Path) -> int | None:
    try:
        return path.stat().st_mtime_ns
    except FileNotFoundError:
        return None
    except OSError:
        return None


def source_is_runtime_override(source: str | None) -> bool:
    return source in {"cmd", "prompt", "auto"}


def reload_listen_runtime_settings(settings: dict) -> tuple[list[str], list[tuple[str, object]]]:
    sources = settings.setdefault("__sources", {})
    changed_families: list[str] = []
    restart_required: list[tuple[str, object]] = []

    listen_settings, listen_sources = load_config_with_sources(LISTEN_CONFIG_PATH, "listen")
    if LISTEN_CONFIG_PATH.exists():
        changed_families.append("listen")
    for key in LISTEN_HOT_RELOAD_KEYS:
        if source_is_runtime_override(sources.get(key)):
            continue
        settings[key] = listen_settings[key]
        sources[key] = listen_sources.get(key, "default")
    for key in LISTEN_RESTART_REQUIRED_KEYS:
        new_value = listen_settings[key]
        current_value = settings.get(key)
        if new_value != current_value:
            restart_required.append((key, new_value))

    autoresponder_settings, autoresponder_sources = load_config_with_sources(AUTORESPONDER_CONFIG_PATH, "autoresponder")
    if AUTORESPONDER_CONFIG_PATH.exists():
        changed_families.append("autoresponder")
    for key in AUTORESPONDER_CONFIG_KEYS:
        if source_is_runtime_override(sources.get(key)):
            continue
        settings[key] = autoresponder_settings[key]
        sources[key] = autoresponder_sources.get(key, "default")

    send_settings, send_sources = load_config_with_sources(SEND_CONFIG_PATH, "send")
    if SEND_CONFIG_PATH.exists():
        changed_families.append("send")
    for key in AUTORESPONDER_SEND_KEYS:
        mapped_key = AUTORESPONDER_SEND_KEY_MAP[key]
        if source_is_runtime_override(sources.get(mapped_key)):
            continue
        settings[mapped_key] = send_settings[key]
        sources[mapped_key] = send_sources.get(key, "default")

    return changed_families, restart_required


def reload_send_runtime_settings(settings: dict, active_only: bool = False) -> tuple[list[str], list[tuple[str, object]]]:
    sources = settings.setdefault("__sources", {})
    changed_families: list[str] = []
    restart_required: list[tuple[str, object]] = []

    send_settings, send_sources = load_config_with_sources(SEND_CONFIG_PATH, "send")
    if SEND_CONFIG_PATH.exists():
        changed_families.append("send")

    hot_reload_keys = SEND_ACTIVE_HOT_RELOAD_KEYS if active_only else SEND_PREP_HOT_RELOAD_KEYS
    for key in hot_reload_keys:
        if source_is_runtime_override(sources.get(key)):
            continue
        settings[key] = send_settings[key]
        sources[key] = send_sources.get(key, "default")

    for key in SEND_RESTART_REQUIRED_KEYS:
        new_value = send_settings[key]
        current_value = settings.get(key)
        if new_value != current_value:
            restart_required.append((key, new_value))

    return changed_families, restart_required


def get_recipient_label(interface: SerialInterface, node_id: str | None) -> str:
    if not node_id:
        return "unknown"
    node = interface.nodes.get(node_id, {})
    user = node.get("user", {})
    return user.get("longName") or user.get("shortName") or node_id


def extract_text(packet: dict) -> str | None:
    decoded = packet.get("decoded", {})
    text = decoded.get("text")
    if text:
        return text
    payload = decoded.get("payload")
    if isinstance(payload, (bytes, bytearray)):
        try:
            return bytes(payload).decode("utf-8")
        except UnicodeDecodeError:
            return None
    return None


def local_channel_infos(interface: SerialInterface) -> list[dict]:
    try:
        return interface.localNode.get_channels_with_hash()
    except Exception:
        return []


def channel_from_hash(interface: SerialInterface, raw_channel: int) -> dict | None:
    for info in local_channel_infos(interface):
        if info.get("hash") == raw_channel:
            return info
    return None


def packet_channel(interface: SerialInterface, packet: dict) -> int | None:
    value = packet.get("channel")
    if value is None:
        value = packet.get("channelIndex")
    if value is None:
        return 0
    try:
        channel_index = int(value)
    except (TypeError, ValueError):
        return None
    if 0 <= channel_index <= 7:
        return channel_index
    hashed_channel = channel_from_hash(interface, channel_index)
    if hashed_channel is not None:
        return hashed_channel.get("index")
    return None


def packet_raw_channel(packet: dict):
    value = packet.get("channel")
    if value is None:
        value = packet.get("channelIndex")
    return value


def channel_name(interface: SerialInterface, channel_index: int | None) -> str | None:
    if channel_index is None:
        return None
    for info in local_channel_infos(interface):
        if info.get("index") == channel_index:
            if info.get("name"):
                return str(info["name"])
            role = info.get("role")
            if role == "PRIMARY":
                return "Primary"
            if role == "SECONDARY":
                return f"Channel {channel_index}"
            return None
    try:
        channel = interface.localNode.getChannelByChannelIndex(channel_index)
    except Exception:
        channel = None
    if channel is None:
        return None
    settings = getattr(channel, "settings", None)
    if settings is None:
        return None
    name = getattr(settings, "name", None)
    if name:
        return str(name)
    return None


def is_direct_message(packet: dict) -> bool:
    to_id = packet.get("toId")
    return bool(to_id and to_id != "^all")


def build_sender_candidate(interface: SerialInterface, packet: dict) -> dict:
    node_id = packet.get("fromId") or str(packet.get("from", "unknown"))
    node = interface.nodes.get(node_id, {})
    user = node.get("user", {})
    label = user.get("longName") or user.get("shortName") or node_id
    return {
        "node_id": node_id,
        "label": label,
        "short_name": user.get("shortName", ""),
        "long_name": user.get("longName", ""),
    }


def packet_matches_listen_filters(interface: SerialInterface, packet: dict, settings: dict) -> bool:
    if settings["listen_filter"]:
        sender = build_sender_candidate(interface, packet)
        if not recipient_matches_filter(sender, settings["listen_filter"]):
            return False

    if settings["listen_channel_index"] is not None:
        if packet_channel(interface, packet) != settings["listen_channel_index"]:
            return False

    if settings["listen_dm_only"] and not is_direct_message(packet):
        return False

    if settings["listen_group_only"] and is_direct_message(packet):
        return False

    if settings["listen_text_only"] and not extract_text(packet):
        return False

    return True


def build_receive_record(interface: SerialInterface, packet: dict) -> dict:
    sender_id = packet.get("fromId") or str(packet.get("from", "unknown"))
    sender_node = interface.nodes.get(sender_id, {})
    sender_user = sender_node.get("user", {})
    sender_short_name = sender_user.get("shortName", "")
    sender_long_name = sender_user.get("longName", "")
    sender_label = sender_long_name or sender_short_name or get_recipient_label(interface, sender_id)
    receiver_id = packet.get("toId") or str(packet.get("to", "unknown"))
    text = extract_text(packet)
    channel = packet_channel(interface, packet)
    raw_channel = packet_raw_channel(packet)
    hashed_channel = None
    if raw_channel is not None and channel is not None:
        try:
            raw_value = int(raw_channel)
        except (TypeError, ValueError):
            raw_value = None
        if raw_value is not None and not 0 <= raw_value <= 7:
            hashed_channel = channel_from_hash(interface, raw_value)
    portnum = packet.get("decoded", {}).get("portnum", "UNKNOWN")
    dm = is_direct_message(packet)
    return {
        "from_id": sender_id,
        "from_label": sender_label,
        "from_short_name": sender_short_name,
        "from_long_name": sender_long_name,
        "to_id": receiver_id,
        "channel_index": channel,
        "channel_name": channel_name(interface, channel),
        "raw_channel": raw_channel,
        "channel_hash_match": hashed_channel,
        "scope": "dm" if dm else "group",
        "portnum": portnum,
        "text": text,
        "packet": sanitize_for_json(packet),
    }


def format_port_label(portnum) -> str:
    value = str(portnum or "UNKNOWN")
    labels = {
        "TEXT_MESSAGE_APP": "text",
        "TEXT_MESSAGE_COMPRESSED_APP": "text-compressed",
        "NODEINFO_APP": "nodeinfo",
        "POSITION_APP": "position",
        "TELEMETRY_APP": "telemetry",
        "ROUTING_APP": "routing",
        "ADMIN_APP": "admin",
        "NEIGHBORINFO_APP": "neighborinfo",
        "TRACEROUTE_APP": "traceroute",
        "WAYPOINT_APP": "waypoint",
        "RANGE_TEST_APP": "rangetest",
        "STORE_FORWARD_APP": "storeforward",
        "PRIVATE_APP": "private",
        "ATAK_PLUGIN": "atak",
        "MAP_REPORT_APP": "map-report",
        "ALERT_APP": "alert",
        "REPLY_APP": "reply",
    }
    return labels.get(value, value.lower().replace("_app", "").replace("_", "-"))


def is_text_message_port(portnum) -> bool:
    return str(portnum or "UNKNOWN") in {"TEXT_MESSAGE_APP", "TEXT_MESSAGE_COMPRESSED_APP"}


def format_receive_line(record: dict) -> str:
    scope_text = record["scope"].upper()
    scope = colorize(scope_text, "green" if scope_text == "DM" else "cyan", bold=True)
    if record["channel_index"] is None:
        if record.get("raw_channel") is None:
            channel = "unknown"
        else:
            channel = f"unknown(raw={record['raw_channel']})"
    elif record.get("channel_hash_match"):
        channel = (
            f"{record['channel_index']}:{record.get('channel_name') or 'unknown'}"
            f"(hash={record['raw_channel']})"
        )
    elif record.get("channel_name"):
        channel = f"{record['channel_index']}:{record['channel_name']}"
    else:
        channel = str(record["channel_index"])
    port_label = format_port_label(record["portnum"])
    channel = colorize(f"ch={channel}", "magenta")
    port_label = colorize(f"port={port_label}", "blue")
    sender = colorize(f"{record['from_label']} ({record['from_id']})", "white", bold=True)
    target = colorize(record["to_id"], "white")
    text = record["text"]
    if text:
        return (
            f"[{now_string()}] {scope} {channel} {port_label} "
            f"{sender} -> {target}: {text}"
        )
    return (
        f"[{now_string()}] {scope} {channel} {port_label} "
        f"{sender} -> {target} "
        f"[{record['portnum']}]"
    )


def history_matches_filter(entry: dict, history_filter: str) -> bool:
    pattern = history_filter.casefold()
    candidates = [
        str(entry.get("entry_type", "")),
        str(entry.get("from_id", "")),
        str(entry.get("from_label", "")),
        str(entry.get("to_id", "")),
        str(entry.get("recipient_id", "")),
        str(entry.get("recipient_label", "")),
        str(entry.get("scope", "")),
        str(entry.get("message", "")),
        str(entry.get("text", "")),
        str(entry.get("result", "")),
    ]
    normalized = [candidate.casefold() for candidate in candidates if candidate]
    has_wildcards = any(char in history_filter for char in "*?[]")
    if has_wildcards:
        return any(fnmatch.fnmatch(value, pattern) for value in normalized)
    return any(pattern in value for value in normalized)


def format_history_line(entry: dict) -> str:
    timestamp = entry.get("timestamp", "?")
    entry_type = str(entry.get("entry_type", "unknown"))
    if entry_type == "receive":
        record = {
            "scope": entry.get("scope", "group"),
            "channel_index": entry.get("channel_index"),
            "channel_name": entry.get("channel_name"),
            "raw_channel": entry.get("raw_channel"),
            "channel_hash_match": entry.get("channel_hash_match"),
            "portnum": entry.get("portnum", "UNKNOWN"),
            "from_label": entry.get("from_label", "unknown"),
            "from_id": entry.get("from_id", "unknown"),
            "to_id": entry.get("to_id", "unknown"),
            "text": entry.get("text"),
        }
        line = format_receive_line(record)
        suffix = line.split("] ", 1)[1] if "] " in line else line
        return f"[{timestamp}] {suffix}"

    if entry_type == "send_direct":
        recipient = colorize(
            f"{entry.get('recipient_label', 'unknown')} ({entry.get('recipient_id', 'unknown')})",
            "white",
            bold=True,
        )
        result = colorize(str(entry.get("result", "sent")), "green" if entry.get("result") == "ack" else "yellow")
        channel_text = colorize(f"ch={entry.get('channel_index', '?')}", "magenta")
        return (
            f"[{timestamp}] {colorize('SEND', 'cyan', bold=True)} "
            f"{channel_text} "
            f"{recipient} result={result}: {entry.get('message', '')}"
        )

    if entry_type == "send_broadcast":
        result = colorize(str(entry.get("result", "sent")), "cyan")
        channel_text = colorize(f"ch={entry.get('channel_index', '?')}", "magenta")
        return (
            f"[{timestamp}] {colorize('BROADCAST', 'cyan', bold=True)} "
            f"{channel_text} "
            f"result={result}: {entry.get('message', '')}"
        )

    if entry_type == "send_autoresponse":
        recipient = colorize(
            f"{entry.get('recipient_label', 'unknown')} ({entry.get('recipient_id', 'unknown')})",
            "white",
            bold=True,
        )
        result = colorize(str(entry.get("result", "sent")), "cyan")
        channel_text = colorize(f"ch={entry.get('channel_index', '?')}", "magenta")
        return (
            f"[{timestamp}] {colorize('AUTOREPLY', 'magenta', bold=True)} "
            f"{channel_text} "
            f"{recipient} result={result}: {entry.get('message', '')}"
        )

    return f"[{timestamp}] {entry_type}: {entry}"


def autoresponder_sender_matches(interface: SerialInterface, packet: dict, settings: dict) -> bool:
    if settings["autoresponder_sender_mode"] == "all":
        return True
    sender = build_sender_candidate(interface, packet)
    sender_filter = (settings["autoresponder_sender_filter"] or "").strip()
    if not sender_filter:
        return False
    return recipient_matches_filter(sender, sender_filter)


def autoresponder_message_matches(record: dict, settings: dict) -> bool:
    if settings["autoresponder_message_mode"] == "all":
        return True
    message_filter = (settings["autoresponder_message_filter"] or "").strip()
    if not message_filter:
        return False
    return text_matches_filter(record.get("text"), message_filter)


def build_autoresponder_reply_text(record: dict, settings: dict) -> str:
    base_answer = (settings.get("autoresponder_reply") or "").strip()
    template = (settings.get("autoresponder_reply_template") or "").strip()
    if not template:
        return base_answer

    replacements = {
        "%node_id%": str(record.get("from_id") or ""),
        "%label%": str(record.get("from_label") or ""),
        "%shortname%": str(record.get("from_short_name") or ""),
        "%longname%": str(record.get("from_long_name") or ""),
        "%message%": str(record.get("text") or ""),
        "%channel_index%": "" if record.get("channel_index") is None else str(record.get("channel_index")),
        "%channel_name%": str(record.get("channel_name") or ""),
        "%scope%": str(record.get("scope") or ""),
        "%answer%": base_answer,
    }
    reply_text = template
    for placeholder, value in replacements.items():
        reply_text = reply_text.replace(placeholder, value)
    return reply_text.strip()


def should_autorespond(interface: SerialInterface, packet: dict, record: dict, settings: dict) -> bool:
    if not settings.get("autoresponder"):
        return False
    if not is_text_message_port(record.get("portnum")):
        return False
    if not record.get("text"):
        return False
    if not str(record.get("text")).strip():
        return False
    local_num = get_local_node_num(interface)
    packet_from = packet.get("from")
    if local_num is not None and packet_from == local_num:
        return False
    if not autoresponder_sender_matches(interface, packet, settings):
        return False
    if not autoresponder_message_matches(record, settings):
        return False
    reply_text = build_autoresponder_reply_text(record, settings)
    if not reply_text:
        return False
    return True


def resolve_autoresponder_targets(
    interface: SerialInterface,
    record: dict,
    settings: dict,
) -> tuple[list[dict], int, str | None, str]:
    if not settings.get("autoresponder_unicast"):
        recipient_id = record.get("from_id")
        if not recipient_id:
            return [], 0, None, "triggering sender"
        channel_index = record.get("channel_index")
        if channel_index is None:
            channel_index = 0
        return (
            [
                {
                    "node_id": recipient_id,
                    "label": record.get("from_label") or recipient_id,
                }
            ],
            channel_index,
            record.get("channel_name"),
            "triggering sender",
        )

    recipients = collect_recipients(interface, settings.get("autoresponder_send_include_unmessageable", False))
    selected, target_description = select_recipients_silently(
        recipients,
        settings.get("autoresponder_send_target_mode"),
        settings.get("autoresponder_send_target_filter"),
        settings.get("autoresponder_send_selection"),
    )
    channel_index = settings.get("autoresponder_send_channel_index")
    if channel_index is None:
        channel_index = 0
    return selected, channel_index, channel_name(interface, channel_index), target_description


def send_autoresponse(
    interface: SerialInterface,
    record: dict,
    settings: dict,
    log_path: Path | None,
    history_path: Path,
) -> None:
    reply_text = build_autoresponder_reply_text(record, settings)
    try:
        targets, channel_index, resolved_channel_name, target_description = resolve_autoresponder_targets(
            interface, record, settings
        )
    except ValueError as exc:
        print(colorize(f"Autoresponder target selection failed: {exc}", "red", bold=True))
        return

    if not targets:
        print(colorize("Autoresponder found no matching recipients for the current send target selection.", "yellow"))
        return

    channel_text = f"{channel_index}:{resolved_channel_name}" if resolved_channel_name else str(channel_index)
    if settings.get("autoresponder_unicast"):
        print(colorize(f"Autoresponder unicast target set: {target_description}", "cyan"))

    send_ack = settings.get("autoresponder_send_ack", False)
    send_delay = settings.get("autoresponder_send_delay", 0.5)
    send_timeout = settings.get("autoresponder_send_timeout", settings["timeout"])
    send_retry_implicit_ack = settings.get("autoresponder_send_retry_implicit_ack", 0)
    send_retry_nak = settings.get("autoresponder_send_retry_nak", 0)

    for recipient in targets:
        recipient_id = recipient.get("node_id")
        if not recipient_id:
            continue
        recipient_label = recipient.get("label") or recipient_id
        result = "sent_without_ack"
        packet_id = "unknown"
        if send_ack:
            ack_kind, ack_message, packet_id, _attempts_used = send_with_ack_retry(
                interface,
                {
                    "node_id": recipient_id,
                    "label": recipient_label,
                },
                reply_text,
                {
                    "channel_index": channel_index,
                    "timeout": send_timeout,
                    "retry_implicit_ack": send_retry_implicit_ack,
                    "retry_nak": send_retry_nak,
                    "delay": send_delay,
                },
                log_path,
            )
            result = ack_kind
            color = "green" if ack_kind == "ack" else "yellow" if ack_kind == "implicit_ack" else "red"
            print(
                colorize(
                    f"Sent to {recipient_label} ({recipient_id}) on ch={channel_text}: {reply_text} [autoresponder]",
                    "cyan",
                )
            )
            print(colorize(f"{ack_message} {recipient_label} ({recipient_id}), packet ID {packet_id} [autoresponder]", color))
        else:
            packet = interface.sendText(
                reply_text,
                destinationId=recipient_id,
                wantAck=False,
                channelIndex=channel_index,
            )
            packet_id = getattr(packet, "id", "unknown")
            print(
                colorize(
                    f"Sent to {recipient_label} ({recipient_id}) on ch={channel_text}: {reply_text} [autoresponder], packet ID {packet_id}",
                    "cyan",
                )
            )
        payload = {
            "recipient_id": recipient_id,
            "recipient_label": recipient_label,
            "channel_index": channel_index,
            "channel_name": resolved_channel_name,
            "message": reply_text,
            "packet_id": packet_id,
            "result": result,
            "source_text": record.get("text"),
            "source_sender_filter": settings.get("autoresponder_sender_filter", ""),
            "source_message_filter": settings.get("autoresponder_message_filter", ""),
            "autoresponder_unicast": settings.get("autoresponder_unicast", False),
            "target_description": target_description,
        }
        append_jsonl(log_path, "autoresponse", payload)
        append_history(history_path, "send_autoresponse", payload)


def run_listen_mode(interface: SerialInterface, settings: dict) -> int:
    log_path = resolve_log_path(settings["log_file"])
    history_path = resolve_history_path(settings["history_file"], "listen")
    received_count = 0
    watched_cfg_paths = {
        "listen": LISTEN_CONFIG_PATH,
        "autoresponder": AUTORESPONDER_CONFIG_PATH,
        "send": SEND_CONFIG_PATH,
    }
    cfg_mtimes = {family: file_mtime_ns(path) for family, path in watched_cfg_paths.items()}

    print_effective_parameters(
        settings,
        "listen",
        [
            ("port", settings["port"]),
            ("timeout", "listen_timeout", settings["timeout"]),
            ("listen_filter", settings["listen_filter"]),
            ("listen_channel_index", settings["listen_channel_index"]),
            ("listen_dm_only", settings["listen_dm_only"]),
            ("listen_group_only", settings["listen_group_only"]),
            ("listen_text_only", settings["listen_text_only"]),
            ("listen_verbose", settings["listen_verbose"]),
            ("autoresponder", settings["autoresponder"]),
            ("autoresponder_unicast", settings["autoresponder_unicast"]),
            ("autoresponder_sender_mode", settings["autoresponder_sender_mode"]),
            ("autoresponder_sender_filter", settings["autoresponder_sender_filter"]),
            ("autoresponder_message_mode", settings["autoresponder_message_mode"]),
            ("autoresponder_message_filter", settings["autoresponder_message_filter"]),
            ("autoresponder_reply", settings["autoresponder_reply"]),
            ("autoresponder_reply_template", settings["autoresponder_reply_template"]),
            ("autoresponder_send_channel_index", "send_channel_index", settings.get("autoresponder_send_channel_index")),
            ("autoresponder_send_target_mode", "send_target_mode", settings.get("autoresponder_send_target_mode")),
            ("autoresponder_send_target_filter", "send_target_filter", settings.get("autoresponder_send_target_filter")),
            ("autoresponder_send_selection", "send_selection", settings.get("autoresponder_send_selection")),
            ("autoresponder_send_include_unmessageable", "send_include_unmessageable", settings.get("autoresponder_send_include_unmessageable")),
            ("autoresponder_send_ack", "send_ack", settings.get("autoresponder_send_ack")),
            ("autoresponder_send_delay", "send_delay", settings.get("autoresponder_send_delay")),
            ("autoresponder_send_timeout", "send_timeout", settings.get("autoresponder_send_timeout")),
            ("autoresponder_send_retry_implicit_ack", "send_retry_implicit_ack", settings.get("autoresponder_send_retry_implicit_ack")),
            ("autoresponder_send_retry_nak", "send_retry_nak", settings.get("autoresponder_send_retry_nak")),
            ("unattended", settings["unattended"]),
            ("log_file", log_path if settings["log_file"] else "<disabled>"),
            ("log_rotate_max_mb", settings["log_rotate_max_mb"]),
            ("log_rotate_backups", settings["log_rotate_backups"]),
            ("history_file", history_path),
            ("history_filter", settings["history_filter"]),
            ("history_limit", settings["history_limit"]),
        ],
    )

    print("Listen mode started. Press Ctrl+C to stop.")
    if settings["listen_filter"]:
        print(f"Sender filter: {settings['listen_filter']}")
    if settings["listen_channel_index"] is not None:
        print(f"Channel filter: {settings['listen_channel_index']}")
    if settings["listen_dm_only"]:
        print("Scope filter: direct messages only")
    if settings["listen_group_only"]:
        print("Scope filter: group traffic only")
    if log_path:
        print(colorize(f"Logging to: {log_path}", "cyan"))
        set_log_rotation_policy(log_path, settings["log_rotate_max_mb"], settings["log_rotate_backups"])
    print(colorize(f"History file: {history_path}", "cyan"))
    if settings["autoresponder"]:
        print(colorize("Autoresponder: enabled", "magenta", bold=True))
        if not (settings.get("autoresponder_reply") or "").strip():
            print(colorize("Autoresponder reply text is empty, so no replies will be sent.", "yellow"))

    def maybe_reload_runtime_config() -> None:
        nonlocal log_path, history_path, cfg_mtimes
        changed_families: list[str] = []
        for family, path in watched_cfg_paths.items():
            current_mtime = file_mtime_ns(path)
            if current_mtime != cfg_mtimes.get(family):
                cfg_mtimes[family] = current_mtime
                changed_families.append(family)

        if not changed_families:
            return

        previous_log_path = log_path
        previous_history_path = history_path
        reloaded_families, restart_required = reload_listen_runtime_settings(settings)
        log_path = resolve_log_path(settings["log_file"])
        history_path = resolve_history_path(settings["history_file"], "listen")

        changed_label = ", ".join(f"{family} cfg" for family in changed_families)
        if reloaded_families:
            print(colorize(f"Configuration reloaded: {changed_label}", "magenta", bold=True))
        else:
            print(colorize(f"Configuration change detected: {changed_label}", "magenta", bold=True))

        if previous_log_path != log_path:
            if log_path:
                print(colorize(f"Logging switched to: {log_path}", "cyan"))
            else:
                print(colorize("Logging disabled by config reload.", "cyan"))
        if log_path:
            set_log_rotation_policy(log_path, settings["log_rotate_max_mb"], settings["log_rotate_backups"])

        if previous_history_path != history_path:
            print(colorize(f"History file switched to: {history_path}", "cyan"))

        if settings["autoresponder"]:
            print(colorize("Autoresponder: enabled", "magenta", bold=True))
        else:
            print(colorize("Autoresponder: disabled", "yellow"))

        restart_required_map = {key: value for key, value in restart_required}
        if "port" in restart_required_map:
            print(colorize(f"Port changed in listen cfg ({restart_required_map['port']}). Restart required to use the new serial port setting.", "yellow", bold=True))
        if "timeout" in restart_required_map:
            print(colorize("Listen connection timeout changed in cfg. Restart required for the new timeout to affect the serial connection.", "yellow"))

    def on_receive(packet, interface):
        nonlocal received_count
        maybe_reload_runtime_config()
        if not packet_matches_listen_filters(interface, packet, settings):
            return
        received_count += 1
        record = build_receive_record(interface, packet)
        print(format_receive_line(record))
        if settings["listen_verbose"]:
            print(colorize(f"  record: {json.dumps(record, ensure_ascii=True, sort_keys=True)}", "blue"))
        append_jsonl(log_path, "receive", record)
        append_history(history_path, "receive", record)
        if should_autorespond(interface, packet, record, settings):
            try:
                send_autoresponse(interface, record, settings, log_path, history_path)
            except Exception as exc:
                print(colorize(f"Autoresponder failed for {record.get('from_label', 'unknown')} ({record.get('from_id', 'unknown')}): {exc}", "red"))

    pub.subscribe(on_receive, "meshtastic.receive")
    try:
        while True:
            maybe_reload_runtime_config()
            time.sleep(0.5)
    except KeyboardInterrupt:
        print()
        print(colorize(f"Stopped listening. Matching packets shown: {received_count}", "green"))
        return 0
    finally:
        try:
            pub.unsubscribe(on_receive, "meshtastic.receive")
        except Exception:
            pass


def confirm_broadcast(_message: str, channel_index: int, channel_label: str | None, unattended: bool = False) -> bool:
    print()
    if channel_label:
        print(f"Broadcast destination: {channel_index}:{channel_label}")
    else:
        print(f"Broadcast destination: {channel_index}")
    print()
    if unattended:
        print("Unattended mode is active, broadcasting without confirmation.")
        return True
    answer = input("Broadcast now? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def run_history_mode(settings: dict) -> int:
    history_path = resolve_history_path(settings["history_file"], "send")
    if not history_path.exists():
        print(colorize(f"No history file found: {history_path}", "yellow"))
        return 0

    entries = []
    with history_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if settings["history_filter"] and not history_matches_filter(entry, settings["history_filter"]):
                continue
            entries.append(entry)

    if not entries:
        print(colorize("No history entries match the selected filter.", "yellow"))
        return 0

    limit = max(1, int(settings["history_limit"]))
    selected_entries = entries[-limit:]
    print(colorize(f"Showing {len(selected_entries)} history entr{'y' if len(selected_entries) == 1 else 'ies'} from {history_path}", "cyan"))
    for entry in selected_entries:
        print(format_history_line(entry))
    return 0


def run_broadcast_mode(interface: SerialInterface, settings: dict) -> int:
    try:
        message = prompt_message(settings["message"], settings["unattended"])
    except ValueError as exc:
        print(colorize(str(exc), "red"))
        return 1
    if message != settings["message"]:
        settings["message"] = message
        settings["__sources"]["message"] = "prompt"

    log_path = resolve_log_path(settings["log_file"])
    history_path = resolve_history_path(settings["history_file"], "send")
    channel_label = channel_name(interface, settings["channel_index"])

    print_effective_parameters(
        settings,
        "broadcast",
        [
            ("port", settings["port"]),
            ("channel_index", settings["channel_index"]),
            ("message", settings["message"]),
            ("dry_run", settings["dry_run"]),
            ("unattended", settings["unattended"]),
            ("final_wait", settings["final_wait"]),
            ("log_file", log_path if settings["log_file"] else "<disabled>"),
            ("log_rotate_max_mb", settings["log_rotate_max_mb"]),
            ("log_rotate_backups", settings["log_rotate_backups"]),
            ("history_file", history_path),
        ],
    )

    if settings["ack"]:
        print(colorize("Broadcast mode ignores --ack because broadcast messages do not produce a single direct ACK path.", "yellow"))
    if log_path:
        set_log_rotation_policy(log_path, settings["log_rotate_max_mb"], settings["log_rotate_backups"])

    if not confirm_broadcast(message, settings["channel_index"], channel_label, settings["unattended"]):
        print(colorize("Cancelled.", "yellow"))
        return 0

    if settings["dry_run"]:
        channel_display = f"{settings['channel_index']}:{channel_label}" if channel_label else str(settings["channel_index"])
        print(colorize(f"Dry run: would broadcast on channel {channel_display}: {message}", "cyan", bold=True))
        return 0

    packet = interface.sendText(
        message,
        wantAck=False,
        channelIndex=settings["channel_index"],
    )
    packet_id = getattr(packet, "id", "unknown")
    print(colorize(f"Broadcast sent on channel {settings['channel_index']} ({channel_label or 'unknown'}), packet ID {packet_id}", "cyan"))
    record = {
        "channel_index": settings["channel_index"],
        "channel_name": channel_label,
        "message": message,
        "packet_id": packet_id,
        "result": "sent_without_ack",
    }
    append_jsonl(log_path, "send_broadcast", record)
    append_history(history_path, "send_broadcast", record)

    if settings["final_wait"] > 0:
        print(colorize(
            f"Waiting another {settings['final_wait']:.1f}s so the device can finish sending outgoing packets ...",
            "yellow",
        ))
        time.sleep(settings["final_wait"])
    return 0


def send_with_ack_retry(
    interface: SerialInterface,
    recipient: dict,
    message: str,
    settings: dict,
    log_path: Path | None,
    refresh_settings=None,
    log_path_resolver=None,
) -> tuple[str, str, int, int]:
    node_id = recipient["node_id"]
    label = recipient["label"]
    attempt = 0
    implicit_retries_used = 0
    nak_retries_used = 0

    while True:
        if refresh_settings is not None:
            refresh_settings()
        current_log_path = log_path_resolver() if log_path_resolver is not None else log_path
        attempt += 1
        packet, ack_packet = wait_for_ack(
            interface,
            message,
            node_id,
            settings["channel_index"],
            settings["timeout"],
        )
        packet_id = getattr(packet, "id", "unknown")
        ack_kind, ack_message = classify_ack(interface, ack_packet)
        append_jsonl(
            current_log_path,
            "send_attempt",
            {
                "recipient_id": node_id,
                "recipient_label": label,
                "attempt": attempt,
                "packet_id": packet_id,
                "result": ack_kind,
                "message": message,
                "channel_index": settings["channel_index"],
                "ack_packet": sanitize_for_json(ack_packet),
            },
        )

        if ack_kind == "implicit_ack" and implicit_retries_used < settings["retry_implicit_ack"]:
            implicit_retries_used += 1
            print(
                colorize(
                    f"{ack_message} {label} ({node_id}), packet ID {packet_id}. "
                    f"Retrying implicit ACK ({implicit_retries_used}/{settings['retry_implicit_ack']}) ...",
                    "yellow",
                )
            )
            time.sleep(settings["delay"])
            continue

        if ack_kind == "nak" and nak_retries_used < settings["retry_nak"]:
            nak_retries_used += 1
            print(
                colorize(
                    f"{ack_message} {label} ({node_id}), packet ID {packet_id}. "
                    f"Retrying NAK ({nak_retries_used}/{settings['retry_nak']}) ...",
                    "yellow",
                )
            )
            time.sleep(settings["delay"])
            continue

        return ack_kind, ack_message, packet_id, attempt


def run_send_mode(interface: SerialInterface, settings: dict) -> int:
    try:
        message = prompt_message(settings["message"], settings["unattended"])
    except ValueError as exc:
        print(colorize(str(exc), "red"))
        return 1
    if message != settings["message"]:
        settings["message"] = message
        settings["__sources"]["message"] = "prompt"

    log_path = resolve_log_path(settings["log_file"])
    history_path = resolve_history_path(settings["history_file"], "send")
    watched_send_cfg_mtime = file_mtime_ns(SEND_CONFIG_PATH)
    recipients = collect_recipients(interface, settings["include_unmessageable"])

    print_effective_parameters(
        settings,
        "send",
        [
            ("port", settings["port"]),
            ("channel_index", settings["channel_index"]),
            ("message", settings["message"]),
            ("target_mode", settings["target_mode"]),
            ("target_filter", settings["target_filter"]),
            ("selection", settings["selection"]),
            ("ack", settings["ack"]),
            ("include_unmessageable", settings["include_unmessageable"]),
            ("delay", settings["delay"]),
            ("timeout", settings["timeout"]),
            ("final_wait", settings["final_wait"]),
            ("retry_implicit_ack", settings["retry_implicit_ack"]),
            ("retry_nak", settings["retry_nak"]),
            ("dry_run", settings["dry_run"]),
            ("unattended", settings["unattended"]),
            ("log_file", log_path if settings["log_file"] else "<disabled>"),
            ("log_rotate_max_mb", settings["log_rotate_max_mb"]),
            ("log_rotate_backups", settings["log_rotate_backups"]),
            ("history_file", history_path),
        ],
    )

    if not recipients:
        print(colorize("No matching known nodes found.", "red"))
        return 1
    if log_path:
        set_log_rotation_policy(log_path, settings["log_rotate_max_mb"], settings["log_rotate_backups"])

    def maybe_reload_send_config(active_only: bool = False) -> None:
        nonlocal log_path, history_path, watched_send_cfg_mtime, recipients, message
        current_mtime = file_mtime_ns(SEND_CONFIG_PATH)
        if current_mtime == watched_send_cfg_mtime:
            return
        watched_send_cfg_mtime = current_mtime

        previous_log_path = log_path
        previous_history_path = history_path
        reloaded_families, restart_required = reload_send_runtime_settings(settings, active_only=active_only)
        log_path = resolve_log_path(settings["log_file"])
        history_path = resolve_history_path(settings["history_file"], "send")
        if active_only:
            if reloaded_families:
                print(colorize("Configuration reloaded: send cfg (active send settings)", "magenta", bold=True))
        else:
            if reloaded_families:
                print(colorize("Configuration reloaded: send cfg", "magenta", bold=True))
            if not source_is_runtime_override(settings.get("__sources", {}).get("message")):
                message = settings["message"]
            recipients = collect_recipients(interface, settings["include_unmessageable"])

        if previous_log_path != log_path:
            if log_path:
                print(colorize(f"Logging switched to: {log_path}", "cyan"))
            else:
                print(colorize("Logging disabled by config reload.", "cyan"))
        if log_path:
            set_log_rotation_policy(log_path, settings["log_rotate_max_mb"], settings["log_rotate_backups"])

        if previous_history_path != history_path:
            print(colorize(f"History file switched to: {history_path}", "cyan"))

        restart_required_map = {key: value for key, value in restart_required}
        if "port" in restart_required_map:
            print(colorize(f"Port changed in send cfg ({restart_required_map['port']}). Restart required to use the new serial port setting.", "yellow", bold=True))

    maybe_reload_send_config(active_only=False)

    try:
        recipients, target_description = select_recipients(
            recipients,
            settings["target_mode"],
            settings["target_filter"],
            settings["selection"],
            settings["unattended"],
        )
    except ValueError as exc:
        print(colorize(str(exc), "red"))
        return 1

    if not recipients:
        print(colorize("No nodes match the selected filter or selection.", "red"))
        return 1

    if not confirm_send(message, recipients, target_description, settings["unattended"]):
        print(colorize("Cancelled.", "yellow"))
        return 0

    if log_path:
        print(colorize(f"Logging to: {log_path}", "cyan"))
    print(colorize(f"History file: {history_path}", "cyan"))

    if settings["dry_run"]:
        print(colorize("Dry run: no packets will be sent.", "cyan", bold=True))
        print(colorize(
            f"Would send direct messages to {len(recipients)} recipient(s) on channel {settings['channel_index']}.",
            "cyan",
        ))
        return 0

    sent = 0
    failed = 0
    acked = 0
    implicit_acks = 0
    total_attempts = 0

    for recipient in recipients:
        maybe_reload_send_config(active_only=True)
        node_id = recipient["node_id"]
        label = recipient["label"]
        try:
            if settings["ack"]:
                ack_kind, ack_message, packet_id, attempts_used = send_with_ack_retry(
                    interface,
                    recipient,
                    message,
                    settings,
                    log_path,
                    refresh_settings=lambda: maybe_reload_send_config(active_only=True),
                    log_path_resolver=lambda: log_path,
                )
                total_attempts += attempts_used
                if ack_kind == "ack":
                    acked += 1
                    print(colorize(f"{ack_message} {label} ({node_id}), packet ID {packet_id}", "green"))
                elif ack_kind == "implicit_ack":
                    implicit_acks += 1
                    print(colorize(f"{ack_message} {label} ({node_id}), packet ID {packet_id}", "yellow"))
                else:
                    failed += 1
                    print(colorize(f"{ack_message} {label} ({node_id}), packet ID {packet_id}", "red"))
                append_history(
                    history_path,
                    "send_direct",
                    {
                        "recipient_id": node_id,
                        "recipient_label": label,
                        "channel_index": settings["channel_index"],
                        "message": message,
                        "packet_id": packet_id,
                        "result": ack_kind,
                    },
                )
            else:
                packet = interface.sendText(
                    message,
                    destinationId=node_id,
                    wantAck=False,
                    channelIndex=settings["channel_index"],
                )
                packet_id = getattr(packet, "id", "unknown")
                total_attempts += 1
                print(colorize(f"Sent to {label} ({node_id}), packet ID {packet_id}", "cyan"))
                append_jsonl(
                    log_path,
                    "send_attempt",
                    {
                        "recipient_id": node_id,
                        "recipient_label": label,
                        "attempt": 1,
                        "packet_id": packet_id,
                        "result": "sent_without_ack",
                        "message": message,
                        "channel_index": settings["channel_index"],
                    },
                )
                append_history(
                    history_path,
                    "send_direct",
                    {
                        "recipient_id": node_id,
                        "recipient_label": label,
                        "channel_index": settings["channel_index"],
                        "message": message,
                        "packet_id": packet_id,
                        "result": "sent_without_ack",
                    },
                )

            sent += 1
        except TimeoutError as exc:
            failed += 1
            total_attempts += 1
            print(colorize(f"Timeout for {label} ({node_id}): {exc}", "red"))
            append_jsonl(
                log_path,
                "send_attempt",
                {
                    "recipient_id": node_id,
                    "recipient_label": label,
                    "attempt": 1,
                    "result": "timeout",
                    "message": message,
                    "channel_index": settings["channel_index"],
                    "error": str(exc),
                },
            )
            append_history(
                history_path,
                "send_direct",
                {
                    "recipient_id": node_id,
                    "recipient_label": label,
                    "channel_index": settings["channel_index"],
                    "message": message,
                    "result": "timeout",
                    "error": str(exc),
                },
            )
        except Exception as exc:
            failed += 1
            total_attempts += 1
            print(colorize(f"Error for {label} ({node_id}): {exc}", "red"))
            append_jsonl(
                log_path,
                "send_attempt",
                {
                    "recipient_id": node_id,
                    "recipient_label": label,
                    "attempt": 1,
                    "result": "error",
                    "message": message,
                    "channel_index": settings["channel_index"],
                    "error": str(exc),
                },
            )
            append_history(
                history_path,
                "send_direct",
                {
                    "recipient_id": node_id,
                    "recipient_label": label,
                    "channel_index": settings["channel_index"],
                    "message": message,
                    "result": "error",
                    "error": str(exc),
                },
            )

        time.sleep(settings["delay"])

    if not settings["ack"] and settings["final_wait"] > 0:
        print()
        print(colorize(
            f"Waiting another {settings['final_wait']:.1f}s so the device can finish sending outgoing packets ...",
            "yellow",
        ))
        time.sleep(settings["final_wait"])

    print()
    if settings["ack"]:
        summary_color = "green" if failed == 0 and implicit_acks == 0 else "yellow" if failed == 0 else "red"
        print(colorize(
            f"Done. Recipients processed: {sent}, attempts: {total_attempts}, "
            f"ACKs: {acked}, implicit ACKs: {implicit_acks}, errors/timeouts: {failed}",
            summary_color,
            bold=True,
        ))
    else:
        summary_color = "green" if failed == 0 else "red"
        print(colorize(
            f"Done. Recipients processed: {sent}, attempts: {total_attempts}, errors: {failed}",
            summary_color,
            bold=True,
        ))
    return 0 if sent else 1


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.clear:
        return clear_config(args)

    if args.list_ports:
        print_available_ports(get_available_ports())
        return 0

    ensure_missing_configs(args)

    settings = resolve_settings(args)
    if settings is None:
        return 1

    if settings["mode"] == "history":
        return run_history_mode(settings)

    interface = None
    try:
        port = resolve_port(settings["port"] or None, settings["unattended"])
        if not settings["port"]:
            settings["port"] = port
            settings["__sources"]["port"] = "auto"
        print(colorize(f"Connecting via {port} ...", "cyan"))
        interface = SerialInterface(devPath=port, timeout=settings["timeout"])

        if settings["mode"] == "listen":
            return run_listen_mode(interface, settings)
        if settings["mode"] == "broadcast":
            return run_broadcast_mode(interface, settings)
        return run_send_mode(interface, settings)
    except Exception as exc:
        print(colorize(f"Connection or send failed: {exc}", "red", bold=True))
        return 1
    finally:
        if interface is not None:
            try:
                interface.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
