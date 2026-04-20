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

SCRIPT_PATH = Path(__file__)
SCRIPT_STEM = SCRIPT_PATH.stem
SEND_CONFIG_PATH = SCRIPT_PATH.with_name(f"{SCRIPT_STEM}.send.cfg")
LISTEN_CONFIG_PATH = SCRIPT_PATH.with_name(f"{SCRIPT_STEM}.listen.cfg")
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
    "listen_filter": "",
    "listen_channel_index": None,
    "listen_dm_only": False,
    "listen_group_only": False,
    "listen_text_only": False,
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
    "listen_filter": "str",
    "listen_channel_index": "optional_int",
    "listen_dm_only": "bool",
    "listen_group_only": "bool",
    "listen_text_only": "bool",
    "retry_implicit_ack": "int",
    "retry_nak": "int",
    "dry_run": "bool",
    "history_file": "str",
    "history_filter": "str",
    "history_limit": "int",
}

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
        description="Communicate with Meshtastic through direct messages, group broadcasts, live listening, logging, and local history."
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
            '--listen-channel-index 1 --dm-only --text-only --log-file "./listen_log.jsonl" '
            '--history-file "./meshtastic_mass_com.listen.history.jsonl" --unattended --forcecfg'
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
    return LISTEN_CONFIG_PATH if config_family == "listen" else SEND_CONFIG_PATH


def history_path_for_family(config_family: str) -> Path:
    return LISTEN_HISTORY_PATH if config_family == "listen" else SEND_HISTORY_PATH


def load_config(config_path: Path) -> dict:
    settings, _sources = load_config_with_sources(config_path)
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


def load_config_with_sources(config_path: Path) -> tuple[dict, dict]:
    settings = DEFAULT_SETTINGS.copy()
    sources = {key: "default" for key in DEFAULT_SETTINGS}
    if not config_path.exists():
        return settings, sources

    parser = configparser.ConfigParser()
    parser.read(config_path, encoding="utf-8")
    if not parser.has_section(CONFIG_SECTION):
        return settings, sources

    section = parser[CONFIG_SECTION]
    for key, value_type in SETTING_TYPES.items():
        if section.get(key, fallback=None) is None:
            continue
        settings[key] = parse_config_value(section, key, value_type)
        sources[key] = "cfg"
    return settings, sources


def format_source_label(source: str) -> str:
    colors = {
        "cmd": "cyan",
        "cfg": "green",
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
    if config_path:
        print(f"  cfg file: {config_path}")
    for key, value in fields:
        source = settings.get("__sources", {}).get(key, "default")
        print(f"  {format_source_label(source)} {key} = {format_effective_value(value)}")


def config_file_values(settings: dict) -> dict[str, str]:
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
        "listen_filter": settings["listen_filter"] or "",
        "listen_channel_index": "" if settings["listen_channel_index"] is None else str(settings["listen_channel_index"]),
        "listen_dm_only": str(settings["listen_dm_only"]).lower(),
        "listen_group_only": str(settings["listen_group_only"]).lower(),
        "listen_text_only": str(settings["listen_text_only"]).lower(),
        "retry_implicit_ack": str(settings["retry_implicit_ack"]),
        "retry_nak": str(settings["retry_nak"]),
        "dry_run": str(settings["dry_run"]).lower(),
        "history_file": settings["history_file"] or "",
        "history_filter": settings["history_filter"] or "",
        "history_limit": str(settings["history_limit"]),
    }


def render_config_text(settings: dict, config_path: Path) -> str:
    config_family = "listen" if config_path == LISTEN_CONFIG_PATH else "send"
    values = config_file_values(settings)
    active_modes = "listen" if config_family == "listen" else "send, broadcast, history"
    family_title = "Listen workflow" if config_family == "listen" else "Send workflow"
    example = example_command_for_family(config_family)

    lines = [
        f"# Meshtastic_Mass_Com - {family_title} configuration",
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
        "# --listen-filter / --listen-channel-index / --dm-only / --group-only / --text-only control listen-mode filtering.",
        "# --log-file / --history-file / --history-filter / --history-limit control local files and history output.",
        "# --forcecfg / --protectcfg / --clear control cfg handling.",
        "# Notes for this cfg family:",
    ]

    if config_family == "listen":
        lines.extend(
            [
                "# - This cfg is used by --listen or --mode listen.",
                "# - Send-only options such as target_mode or retry_implicit_ack can still be stored here,",
                "#   but they matter mainly if you later switch workflows via CLI for a single run.",
            ]
        )
    else:
        lines.extend(
            [
                "# - This cfg is used by default runs and by --mode send, --mode broadcast, and --mode history.",
                "# - Listen-only options can still be stored here, but they are mainly relevant for temporary",
                "#   one-off listen runs unless you maintain a dedicated listen cfg.",
            ]
        )

    lines.extend(
        [
            "",
            f"[{CONFIG_SECTION}]",
            "",
            "# Workflow",
            f"# Stored mode for this cfg family. Typical default here: {'listen' if config_family == 'listen' else 'send'}.",
            "# Allowed values: send | listen | broadcast | history",
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
            "",
            "# Files",
            "# Optional JSONL log file for send and listen activity.",
            f"log_file = {values['log_file']}",
            "# Optional JSONL history or inbox file.",
            f"history_file = {values['history_file']}",
            "# Filter applied by history mode when showing saved entries.",
            f"history_filter = {values['history_filter']}",
            "# Number of recent history entries to show in history mode.",
            f"history_limit = {values['history_limit']}",
            "",
        ]
    )
    return "\n".join(lines)


def save_config(settings: dict, config_path: Path) -> None:
    with config_path.open("w", encoding="utf-8") as config_file:
        config_file.write(render_config_text(settings, config_path))


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
    config_exists = config_path.exists()
    should_write_cfg = bool(cli_overrides) and not args.protectcfg

    if not config_exists and not cli_overrides:
        print(f"No configuration file found: {config_path}")
        print("Run the script with parameters the first time, for example:")
        print(example_command_for_family(config_family))
        return None

    settings, sources = load_config_with_sources(config_path)

    if cli_overrides:
        settings.update(cli_overrides)
        for key in cli_overrides:
            sources[key] = "cmd"
        if should_write_cfg:
            save_config(settings, config_path)
            if config_exists:
                print(colorize(f"Configuration updated: {config_path}", "green"))
            else:
                print(colorize(f"Configuration created: {config_path}", "green"))
        elif args.protectcfg:
            print(colorize("CFG protection is active, configuration changes will not be saved for this run.", "yellow"))
    elif config_exists:
        print(colorize(f"Using configuration from: {config_path}", "cyan"))

    settings["__sources"] = sources
    settings["__config_path"] = config_path
    settings["__config_family"] = config_family
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
    sender_label = get_recipient_label(interface, sender_id)
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

    return f"[{timestamp}] {entry_type}: {entry}"


def run_listen_mode(interface: SerialInterface, settings: dict) -> int:
    log_path = resolve_log_path(settings["log_file"])
    history_path = resolve_history_path(settings["history_file"], "listen")
    received_count = 0

    print_effective_parameters(
        settings,
        "listen",
        [
            ("port", settings["port"]),
            ("timeout", settings["timeout"]),
            ("listen_filter", settings["listen_filter"]),
            ("listen_channel_index", settings["listen_channel_index"]),
            ("listen_dm_only", settings["listen_dm_only"]),
            ("listen_group_only", settings["listen_group_only"]),
            ("listen_text_only", settings["listen_text_only"]),
            ("unattended", settings["unattended"]),
            ("log_file", log_path if settings["log_file"] else "<disabled>"),
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
    if settings["listen_text_only"]:
        print("Content filter: text packets only")
    if log_path:
        print(colorize(f"Logging to: {log_path}", "cyan"))

    def on_receive(packet, interface):
        nonlocal received_count
        if not packet_matches_listen_filters(interface, packet, settings):
            return
        received_count += 1
        record = build_receive_record(interface, packet)
        print(format_receive_line(record))
        append_jsonl(log_path, "receive", record)
        append_history(history_path, "receive", record)

    pub.subscribe(on_receive, "meshtastic.receive")
    try:
        while True:
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
            ("history_file", history_path),
        ],
    )

    if settings["ack"]:
        print(colorize("Broadcast mode ignores --ack because broadcast messages do not produce a single direct ACK path.", "yellow"))

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
) -> tuple[str, str, int, int]:
    node_id = recipient["node_id"]
    label = recipient["label"]
    attempt = 0
    implicit_retries_used = 0
    nak_retries_used = 0

    while True:
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
            log_path,
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
            ("history_file", history_path),
        ],
    )

    if not recipients:
        print(colorize("No matching known nodes found.", "red"))
        return 1

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
