import argparse
import configparser
import fnmatch
import sys
import threading
import time
from pathlib import Path

from meshtastic.serial_interface import SerialInterface
from serial.tools import list_ports

CONFIG_PATH = Path(__file__).with_suffix(".cfg")
CONFIG_SECTION = "settings"
DEFAULT_SETTINGS = {
    "port": "",
    "channel_index": 0,
    "ack": False,
    "include_unmessageable": False,
    "delay": 0.5,
    "timeout": 30,
    "final_wait": 5.0,
    "target_mode": "all",
    "target_filter": "",
    "message": "",
    "unattended": False,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send a direct Meshtastic message to all known message-capable nodes."
    )
    parser.add_argument(
        "--port",
        default=None,
        help="Serial port of the Meshtastic device. If omitted, available ports are auto-detected.",
    )
    parser.add_argument(
        "--channel-index",
        type=int,
        default=None,
        help="Channel index to use for sending (default: 0).",
    )
    parser.add_argument(
        "--ack",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Request reliable delivery and wait for ACK/NAK for each message.",
    )
    parser.add_argument(
        "--include-unmessageable",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Also try nodes that are marked as unmessageable.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Delay in seconds between messages (default: 0.5).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Connection timeout in seconds (default: 30).",
    )
    parser.add_argument(
        "--final-wait",
        type=float,
        default=None,
        help="Seconds to keep the connection open after the last send when not waiting for ACKs (default: 5.0).",
    )
    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="Only show available serial ports and exit.",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete the cfg file in the script directory and exit.",
    )
    cfg_group = parser.add_mutually_exclusive_group()
    cfg_group.add_argument(
        "--forcecfg",
        action="store_true",
        help="Always write/update the cfg when parameters are passed.",
    )
    cfg_group.add_argument(
        "--protectcfg",
        action="store_true",
        help="Never write/update the cfg for this run, even when parameters are passed.",
    )
    parser.add_argument(
        "--target-mode",
        choices=("all", "filter"),
        default=None,
        help="Choose whether to send to all known nodes or only filtered matches.",
    )
    parser.add_argument(
        "--filter",
        dest="target_filter",
        default=None,
        help="Filter for node selection, e.g. !55d8c9dc, Rico, or FR*.",
    )
    parser.add_argument(
        "--message",
        default=None,
        help="Default message text to send. If omitted, the script asks interactively unless a message exists in the cfg.",
    )
    parser.add_argument(
        "-u",
        "--unattended",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Run without confirmation prompts. Missing required values must come from parameters or cfg.",
    )
    return parser


def example_command() -> str:
    python_exe = Path(sys.executable)
    script_path = Path(__file__)
    return (
        f'"{python_exe}" "{script_path}" --port COM7 --channel-index 1 --ack '
        '--delay 1.5 --timeout 60 --target-mode filter --filter "FR*" '
        '--message "Test message" --unattended'
    )


def load_config() -> dict:
    settings = DEFAULT_SETTINGS.copy()
    if not CONFIG_PATH.exists():
        return settings

    parser = configparser.ConfigParser()
    parser.read(CONFIG_PATH, encoding="utf-8")
    if not parser.has_section(CONFIG_SECTION):
        return settings

    section = parser[CONFIG_SECTION]
    settings["port"] = section.get("port", fallback=settings["port"])
    settings["channel_index"] = section.getint("channel_index", fallback=settings["channel_index"])
    settings["ack"] = section.getboolean("ack", fallback=settings["ack"])
    settings["include_unmessageable"] = section.getboolean(
        "include_unmessageable", fallback=settings["include_unmessageable"]
    )
    settings["delay"] = section.getfloat("delay", fallback=settings["delay"])
    settings["timeout"] = section.getint("timeout", fallback=settings["timeout"])
    settings["final_wait"] = section.getfloat("final_wait", fallback=settings["final_wait"])
    settings["target_mode"] = section.get("target_mode", fallback=settings["target_mode"])
    settings["target_filter"] = section.get("target_filter", fallback=settings["target_filter"])
    settings["message"] = section.get("message", fallback=settings["message"])
    settings["unattended"] = section.getboolean("unattended", fallback=settings["unattended"])
    return settings


def save_config(settings: dict) -> None:
    parser = configparser.ConfigParser()
    parser[CONFIG_SECTION] = {
        "port": settings["port"] or "",
        "channel_index": str(settings["channel_index"]),
        "ack": str(settings["ack"]).lower(),
        "include_unmessageable": str(settings["include_unmessageable"]).lower(),
        "delay": str(settings["delay"]),
        "timeout": str(settings["timeout"]),
        "final_wait": str(settings["final_wait"]),
        "target_mode": settings["target_mode"] or "all",
        "target_filter": settings["target_filter"] or "",
        "message": settings["message"] or "",
        "unattended": str(settings["unattended"]).lower(),
    }
    with CONFIG_PATH.open("w", encoding="utf-8") as config_file:
        parser.write(config_file)


def collect_cli_overrides(args: argparse.Namespace) -> dict:
    overrides = {}
    for key in (
        "port",
        "channel_index",
        "ack",
        "include_unmessageable",
        "delay",
        "timeout",
        "final_wait",
        "target_mode",
        "target_filter",
        "message",
        "unattended",
    ):
        value = getattr(args, key)
        if value is not None:
            overrides[key] = value

    if "target_filter" in overrides and "target_mode" not in overrides:
        overrides["target_mode"] = "filter"

    return overrides


def resolve_settings(args: argparse.Namespace) -> dict | None:
    cli_overrides = collect_cli_overrides(args)
    config_exists = CONFIG_PATH.exists()
    should_write_cfg = bool(cli_overrides) and not args.protectcfg

    if not config_exists and not cli_overrides:
        print(f"No configuration file found: {CONFIG_PATH}")
        print("Run the script with parameters the first time, for example:")
        print(example_command())
        return None

    settings = load_config()

    if cli_overrides:
        settings.update(cli_overrides)
        if should_write_cfg:
            save_config(settings)
            if config_exists:
                print(f"Configuration updated: {CONFIG_PATH}")
            else:
                print(f"Configuration created: {CONFIG_PATH}")
        elif args.protectcfg:
            print("CFG protection is active, configuration changes will not be saved for this run.")
    elif config_exists:
        print(f"Using configuration from: {CONFIG_PATH}")

    return settings


def clear_config() -> int:
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()
        print(f"Configuration deleted: {CONFIG_PATH}")
    else:
        print(f"No configuration file present: {CONFIG_PATH}")
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
        print("No serial ports found.")
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
            }
        )

    return recipients


def prompt_target_mode(
    cli_target_mode: str | None, cli_target_filter: str | None, unattended: bool = False
) -> tuple[str, str | None]:
    if cli_target_mode == "filter" and cli_target_filter:
        return cli_target_mode, cli_target_filter.strip()
    if cli_target_mode == "all":
        return cli_target_mode, None
    if unattended:
        if cli_target_mode == "filter":
            raise ValueError("Filter is missing in unattended mode. Please provide --filter or save it in the cfg.")
        return "all", None

    while True:
        print()
        print("Target selection:")
        print("  1. Send to all known nodes")
        print("  2. Send to filtered matches")
        choice = input("Choice [1/2]: ").strip()
        if choice in {"1", "all"}:
            return "all", None
        if choice in {"2", "filter"}:
            target_filter = input("Enter a filter (for example !55d8c9dc, Rico, or FR*): ").strip()
            if target_filter:
                return "filter", target_filter
            print("Please enter a non-empty filter.")
            continue
        print("Please enter 1 or 2.")


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


def select_recipients(
    recipients: list[dict], cli_target_mode: str | None, cli_target_filter: str | None, unattended: bool = False
) -> tuple[list[dict], str]:
    target_mode, target_filter = prompt_target_mode(cli_target_mode, cli_target_filter, unattended)
    if target_mode == "all":
        return recipients, "all known nodes"

    filtered = [recipient for recipient in recipients if recipient_matches_filter(recipient, target_filter)]
    return filtered, f'Filter "{target_filter}"'


def confirm_send(message: str, recipients: list[dict], target_description: str, unattended: bool = False) -> bool:
    print()
    print(f'Message: "{message}"')
    print(f"Target mode: {target_description}")
    print(f"Recipients: {len(recipients)}")
    for recipient in recipients:
        print(f"  - {recipient['label']} ({recipient['node_id']})")
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


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.clear:
        return clear_config()

    if args.list_ports:
        print_available_ports(get_available_ports())
        return 0

    settings = resolve_settings(args)
    if settings is None:
        return 1

    try:
        message = prompt_message(settings["message"], settings["unattended"])
    except ValueError as exc:
        print(exc)
        return 1

    interface = None
    try:
        port = resolve_port(settings["port"] or None, settings["unattended"])
        print(f"Connecting via {port} ...")
        interface = SerialInterface(devPath=port, timeout=settings["timeout"])
        recipients = collect_recipients(interface, settings["include_unmessageable"])

        if not recipients:
            print("No matching known nodes found.")
            return 1

        recipients, target_description = select_recipients(
            recipients, settings["target_mode"], settings["target_filter"], settings["unattended"]
        )
        if not recipients:
            print("No nodes match the selected filter.")
            return 1

        if not confirm_send(message, recipients, target_description, settings["unattended"]):
            print("Cancelled.")
            return 0

        sent = 0
        failed = 0
        acked = 0
        implicit_acks = 0

        for recipient in recipients:
            node_id = recipient["node_id"]
            label = recipient["label"]
            try:
                if settings["ack"]:
                    packet, ack_packet = wait_for_ack(
                        interface,
                        message,
                        node_id,
                        settings["channel_index"],
                        settings["timeout"],
                    )
                    packet_id = getattr(packet, "id", "unknown")
                    ack_kind, ack_message = classify_ack(interface, ack_packet)
                    if ack_kind == "ack":
                        acked += 1
                        print(f"{ack_message} {label} ({node_id}), packet ID {packet_id}")
                    elif ack_kind == "implicit_ack":
                        implicit_acks += 1
                        print(f"{ack_message} {label} ({node_id}), packet ID {packet_id}")
                    else:
                        failed += 1
                        print(f"{ack_message} {label} ({node_id}), packet ID {packet_id}")
                else:
                    packet = interface.sendText(
                        message,
                        destinationId=node_id,
                        wantAck=False,
                        channelIndex=settings["channel_index"],
                    )
                    packet_id = getattr(packet, "id", "unknown")
                    print(f"Sent to {label} ({node_id}), packet ID {packet_id}")

                sent += 1
            except Exception as exc:
                failed += 1
                print(f"Error for {label} ({node_id}): {exc}")

            time.sleep(settings["delay"])

        if not settings["ack"] and settings["final_wait"] > 0:
            print()
            print(
                f"Waiting another {settings['final_wait']:.1f}s so the device can finish sending outgoing packets ..."
            )
            time.sleep(settings["final_wait"])

        print()
        if settings["ack"]:
            print(f"Done. ACKs: {acked}, implicit ACKs: {implicit_acks}, errors/timeouts: {failed}")
        else:
            print(f"Done. Triggered: {sent}, errors: {failed}")
        return 0 if sent else 1
    except Exception as exc:
        print(f"Connection or send failed: {exc}")
        return 1
    finally:
        if interface is not None:
            try:
                interface.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
