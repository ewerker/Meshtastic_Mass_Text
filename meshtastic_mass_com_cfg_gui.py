"""GUI config generator for Meshtastic_Mass_Com.

Copyright (c) 2026 Frank Richter, https://w-2.de
SPDX-License-Identifier: MIT
"""

import configparser
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from meshtastic_mass_com_version import APP_NAME, APP_VERSION

APP_TITLE = f"{APP_NAME} Config Generator v{APP_VERSION}"
SCRIPT_DIR = Path(__file__).resolve().parent
SEND_CFG_NAME = "meshtastic_mass_com.send.cfg"
LISTEN_CFG_NAME = "meshtastic_mass_com.listen.cfg"
AUTORESPONDER_CFG_NAME = "meshtastic_mass_com.autoresponder.cfg"
SEND_HISTORY_NAME = "meshtastic_mass_com.send.history.jsonl"
LISTEN_HISTORY_NAME = "meshtastic_mass_com.listen.history.jsonl"
SETTINGS_SECTION = "settings"


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    field_type: str
    default: object
    help_text: str
    choices: tuple[str, ...] = ()
    width: int = 18


SEND_FIELDS = [
    FieldSpec("port", "Serial Port", "text", "", "Serial port used for sending. Examples: /dev/ttyUSB0, /dev/ttyACM0, or COM7."),
    FieldSpec("channel_index", "Channel Index", "int", 1, "Channel used for direct messages or broadcasts. Example: 1."),
    FieldSpec("message", "Message", "text", "Hello Mesh", "Message text for send or broadcast mode. Example: Hello Mesh."),
    FieldSpec("target_mode", "Target Mode", "choice", "all", "Recipient selection for send mode. Example: all or filter.", ("all", "filter", "select")),
    FieldSpec("target_filter", "Filter", "text", "", "Filter for node id, short name, or long name. Example: FR* or !55d8c9dc."),
    FieldSpec("selection", "Selection", "text", "", "List indexes or ranges for select mode. Example: 1,3-5."),
    FieldSpec("ack", "Wait For ACK", "bool", True, "Wait for ACK, implicit ACK, or NAK. Example: enabled."),
    FieldSpec("include_unmessageable", "Include Unmessageable", "bool", False, "Also include nodes marked as unmessageable. Example: disabled."),
    FieldSpec("delay", "Delay (s)", "float", 1.5, "Delay between recipients or retries. Example: 1.5."),
    FieldSpec("timeout", "Timeout (s)", "int", 60, "Timeout for connection and ACK waiting. Example: 60."),
    FieldSpec("final_wait", "Final Wait (s)", "float", 5.0, "Extra wait after the last transmission when ACK is disabled. Example: 5.0."),
    FieldSpec("retry_implicit_ack", "Retry Implicit ACK", "int", 1, "Retry count for implicit ACK results. Example: 1."),
    FieldSpec("retry_nak", "Retry NAK", "int", 1, "Retry count after a NAK result. Example: 1."),
    FieldSpec("dry_run", "Dry Run", "bool", False, "Preview only, do not transmit. Example: disabled."),
    FieldSpec("unattended", "Unattended", "bool", False, "Skip prompts; all required values must come from CLI or cfg. Example: disabled."),
    FieldSpec("log_file", "Log File", "text", "", "Optional JSONL send log file. Example: ./logs/send_log.jsonl."),
    FieldSpec("history_file", "History File", "text", SEND_HISTORY_NAME, "JSONL history file used while sending. Example: ./logs/send_history.jsonl."),
]


LISTEN_FIELDS = [
    FieldSpec("port", "Serial Port", "text", "", "Serial port used for listening. Examples: /dev/ttyUSB0, /dev/ttyACM0, or COM7."),
    FieldSpec("timeout", "Timeout (s)", "int", 30, "Connection timeout for the listen workflow. Example: 30."),
    FieldSpec("listen_filter", "Listen Filter", "text", "*", "Only show packets whose sender matches this filter. Example: FR*."),
    FieldSpec("listen_channel_index", "Listen Channel", "optional_int", "", "Only show packets for this channel index. Leave blank for all. Example: 1."),
    FieldSpec("listen_dm_only", "DM Only", "bool", False, "Only show direct messages while listening. Example: disabled."),
    FieldSpec("listen_group_only", "Group Only", "bool", False, "Only show group or broadcast traffic while listening. Example: disabled."),
    FieldSpec("listen_text_only", "Text Only", "bool", False, "Only show text packets while listening. Example: enabled."),
    FieldSpec("unattended", "Unattended", "bool", False, "Skip prompts such as serial port selection; all required values must come from cfg or CLI. Example: disabled."),
    FieldSpec("log_file", "Log File", "text", "", "Optional JSONL listen log file. Example: ./logs/listen_log.jsonl."),
    FieldSpec("history_file", "History File", "text", LISTEN_HISTORY_NAME, "JSONL history file used while listening. Example: ./logs/listen_history.jsonl."),
    FieldSpec("history_filter", "History Filter", "text", "", "Filter used by history mode. Example: Naunhof."),
    FieldSpec("history_limit", "History Limit", "int", 20, "Number of recent history entries to show. Example: 50."),
]


AUTORESPONDER_FIELDS = [
    FieldSpec("autoresponder", "Enabled", "bool", False, "Enable the autoresponder by default for listen mode. Example: enabled."),
    FieldSpec("autoresponder_unicast", "Unicast Mode", "bool", False, "Send direct replies to the recipients selected by the send cfg instead of only back to the triggering sender. Example: enabled."),
    FieldSpec("autoresponder_sender_mode", "Sender Mode", "choice", "all", "Which senders may trigger replies. Example: filter.", ("all", "filter")),
    FieldSpec("autoresponder_sender_filter", "Sender Filter", "text", "JR*", "Sender filter for node ID, short name, or long name. Example: JR or JR*."),
    FieldSpec("autoresponder_message_mode", "Message Mode", "choice", "filter", "Which messages may trigger replies. Example: filter.", ("all", "filter")),
    FieldSpec("autoresponder_message_filter", "Message Filter", "text", "!Ping", "Message text filter. Without wildcards it works like contains. Example: !Ping."),
    FieldSpec("autoresponder_reply", "Reply Text", "text", "Pong", "Fixed direct-message reply text. Example: Pong."),
    FieldSpec("autoresponder_reply_template", "Reply Template", "text", "Autoresponder: from %longname%: %message% / Message;  %answer%", "Optional template with trigger variables. Variables: %node_id%, %label%, %shortname%, %longname%, %message%, %channel_index%, %channel_name%, %scope%, %answer%. %answer% is replaced with the configured autoresponder_reply text. Example: Autoresponder: from %longname%: %message% / Message;  %answer%"),
]


class ConfigLogic:
    @staticmethod
    def defaults_from_specs(specs: list[FieldSpec]) -> dict:
        return {spec.key: spec.default for spec in specs}

    @staticmethod
    def default_send_settings() -> dict:
        settings = ConfigLogic.defaults_from_specs(SEND_FIELDS)
        settings["mode"] = "send"
        return settings

    @staticmethod
    def default_listen_settings() -> dict:
        settings = ConfigLogic.defaults_from_specs(LISTEN_FIELDS)
        settings["mode"] = "listen"
        return settings

    @staticmethod
    def default_autoresponder_settings() -> dict:
        return ConfigLogic.defaults_from_specs(AUTORESPONDER_FIELDS)

    @staticmethod
    def config_path(output_dir: Path, family: str) -> Path:
        if family == "listen":
            return output_dir / LISTEN_CFG_NAME
        if family == "autoresponder":
            return output_dir / AUTORESPONDER_CFG_NAME
        return output_dir / SEND_CFG_NAME

    @staticmethod
    def parse_bool(value: str, field_name: str) -> bool:
        normalized = str(value).strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        raise ValueError(f"{field_name} must be true or false.")

    @staticmethod
    def validate_value(spec: FieldSpec, raw_value) -> object:
        if spec.field_type == "text":
            return str(raw_value).strip()
        if spec.field_type == "choice":
            value = str(raw_value).strip()
            if value not in spec.choices:
                raise ValueError(f"{spec.label} must be one of: {', '.join(spec.choices)}")
            return value
        if spec.field_type == "bool":
            return bool(raw_value)
        if spec.field_type == "int":
            text = str(raw_value).strip()
            if text == "":
                raise ValueError(f"{spec.label} is required.")
            return int(text)
        if spec.field_type == "float":
            text = str(raw_value).strip()
            if text == "":
                raise ValueError(f"{spec.label} is required.")
            return float(text)
        if spec.field_type == "optional_int":
            text = str(raw_value).strip()
            return "" if text == "" else int(text)
        raise ValueError(f"Unsupported field type: {spec.field_type}")

    @staticmethod
    def validate_settings(raw_values: dict, specs: list[FieldSpec]) -> dict:
        validated = {}
        for spec in specs:
            try:
                validated[spec.key] = ConfigLogic.validate_value(spec, raw_values.get(spec.key, spec.default))
            except ValueError as exc:
                raise ValueError(f"{spec.label}: {exc}") from exc
        return validated

    @staticmethod
    def load_section(path: Path, section_name: str) -> dict:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(path, encoding="utf-8")
        if not parser.has_section(section_name):
            return {}
        return {key: value for key, value in parser[section_name].items()}

    @staticmethod
    def load_cfg_set(output_dir: Path) -> tuple[dict, dict, dict]:
        send_settings = ConfigLogic.default_send_settings()
        listen_settings = ConfigLogic.default_listen_settings()
        autoresponder_settings = ConfigLogic.default_autoresponder_settings()

        send_path = ConfigLogic.config_path(output_dir, "send")
        listen_path = ConfigLogic.config_path(output_dir, "listen")
        autoresponder_path = ConfigLogic.config_path(output_dir, "autoresponder")

        if send_path.exists():
            send_settings.update(ConfigLogic.coerce_loaded_values(send_path, SEND_FIELDS))

        if listen_path.exists():
            listen_settings.update(ConfigLogic.coerce_loaded_values(listen_path, LISTEN_FIELDS))

        if autoresponder_path.exists():
            autoresponder_settings.update(ConfigLogic.coerce_loaded_values(autoresponder_path, AUTORESPONDER_FIELDS))

        return send_settings, listen_settings, autoresponder_settings

    @staticmethod
    def load_cfg(output_dir: Path, family: str) -> dict:
        path = ConfigLogic.config_path(output_dir, family)
        return ConfigLogic.load_cfg_from_path(path, family)

    @staticmethod
    def load_cfg_from_path(path: Path, family: str) -> dict:
        if family == "listen":
            settings = ConfigLogic.default_listen_settings()
            specs = LISTEN_FIELDS
        elif family == "autoresponder":
            settings = ConfigLogic.default_autoresponder_settings()
            specs = AUTORESPONDER_FIELDS
        else:
            settings = ConfigLogic.default_send_settings()
            specs = SEND_FIELDS
        if path.exists():
            settings.update(ConfigLogic.coerce_loaded_values(path, specs))
        return settings

    @staticmethod
    def coerce_loaded_values(path: Path, specs: list[FieldSpec], section_name: str = SETTINGS_SECTION) -> dict:
        raw_values = ConfigLogic.load_section(path, section_name)
        loaded = {}
        for spec in specs:
            if spec.key not in raw_values:
                continue
            raw = raw_values[spec.key]
            if spec.field_type == "bool":
                loaded[spec.key] = ConfigLogic.parse_bool(raw, spec.label)
            elif spec.field_type == "int":
                loaded[spec.key] = int(raw)
            elif spec.field_type == "float":
                loaded[spec.key] = float(raw)
            elif spec.field_type == "optional_int":
                loaded[spec.key] = "" if raw.strip() == "" else int(raw)
            else:
                loaded[spec.key] = raw
        return loaded

    @staticmethod
    def settings_to_strings(settings: dict, specs: list[FieldSpec]) -> dict:
        output = {}
        for spec in specs:
            value = settings.get(spec.key, spec.default)
            if spec.field_type == "bool":
                output[spec.key] = str(bool(value)).lower()
            else:
                output[spec.key] = "" if value == "" else str(value)
        return output

    @staticmethod
    def render_cfg(family: str, settings: dict, script_path: Path) -> str:
        if family == "listen":
            specs = LISTEN_FIELDS
            family_title = "Listen workflow"
            family_modes = "listen"
        elif family == "autoresponder":
            specs = AUTORESPONDER_FIELDS
            family_title = "Autoresponder"
            family_modes = "autoresponder"
        else:
            specs = SEND_FIELDS
            family_title = "Send workflow"
            family_modes = "send, broadcast, history"
        settings_map = ConfigLogic.settings_to_strings(settings, specs)
        example = ConfigLogic.example_command(family, script_path)

        lines = [
            f"# Meshtastic_Mass_Com - {family_title} configuration",
            "# Copyright (c) 2026 Frank Richter, https://w-2.de",
            "# SPDX-License-Identifier: MIT",
            "#",
            f"# This file is the default cfg for: {family_modes}",
            "# It can be generated with the GUI helper or updated by the CLI tool itself.",
            "# The CLI parameter names map directly to the keys below.",
            "# Example command:",
            f"# {example}",
            "",
            f"[{SETTINGS_SECTION}]",
            "",
        ]

        if family == "send":
            lines.extend(
                [
                    "# Workflow",
                    "# Fixed cfg mode for this file family.",
                    "mode = send",
                    "",
                    "# Connection",
                    "# Serial port such as /dev/ttyUSB0, /dev/ttyACM0, or COM7. Leave empty to auto-detect or ask.",
                    f"port = {settings_map['port']}",
                    "# Channel index for direct messages or broadcasts.",
                    f"channel_index = {settings_map['channel_index']}",
                    "",
                    "# Message and recipients",
                    f"message = {settings_map['message']}",
                    "# all = all known nodes, filter = matching nodes only, select = manual selection list.",
                    f"target_mode = {settings_map['target_mode']}",
                    f"target_filter = {settings_map['target_filter']}",
                    f"selection = {settings_map['selection']}",
                    "",
                    "# Delivery handling",
                    f"ack = {settings_map['ack']}",
                    f"include_unmessageable = {settings_map['include_unmessageable']}",
                    f"delay = {settings_map['delay']}",
                    f"timeout = {settings_map['timeout']}",
                    f"final_wait = {settings_map['final_wait']}",
                    f"retry_implicit_ack = {settings_map['retry_implicit_ack']}",
                    f"retry_nak = {settings_map['retry_nak']}",
                    f"dry_run = {settings_map['dry_run']}",
                    f"unattended = {settings_map['unattended']}",
                    "",
                    "# Files",
                    f"log_file = {settings_map['log_file']}",
                    f"history_file = {settings_map['history_file']}",
                    "",
                ]
            )
        elif family == "listen":
            lines.extend(
                [
                    "# Workflow",
                    "# Fixed cfg mode for this file family.",
                    "mode = listen",
                    "",
                    "# Connection",
                    "# Serial port such as /dev/ttyUSB0, /dev/ttyACM0, or COM7. Leave empty to auto-detect or ask.",
                    f"port = {settings_map['port']}",
                    f"timeout = {settings_map['timeout']}",
                    "",
                    "# Listen filters",
                    f"listen_filter = {settings_map['listen_filter']}",
                    "# Leave blank to listen on all channels.",
                    f"listen_channel_index = {settings_map['listen_channel_index']}",
                    f"listen_dm_only = {settings_map['listen_dm_only']}",
                    f"listen_group_only = {settings_map['listen_group_only']}",
                    f"listen_text_only = {settings_map['listen_text_only']}",
                    "",
                    "# Runtime",
                    "# true skips interactive prompts such as port selection.",
                    f"unattended = {settings_map['unattended']}",
                    "",
                    "# Files",
                    f"log_file = {settings_map['log_file']}",
                    f"history_file = {settings_map['history_file']}",
                    f"history_filter = {settings_map['history_filter']}",
                    f"history_limit = {settings_map['history_limit']}",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "# Workflow",
                    "# Enable or disable the autoresponder by default for listen mode.",
                    f"autoresponder = {settings_map['autoresponder']}",
                    "# true sends direct replies to the recipients selected by the send cfg instead of only back to the triggering sender.",
                    f"autoresponder_unicast = {settings_map['autoresponder_unicast']}",
                    "",
                    "# Sender matching",
                    "# all = accept every sender, filter = only matching senders.",
                    f"autoresponder_sender_mode = {settings_map['autoresponder_sender_mode']}",
                    "# Filter for sender node ID, short name, or long name.",
                    f"autoresponder_sender_filter = {settings_map['autoresponder_sender_filter']}",
                    "",
                    "# Message matching",
                    "# all = answer every matching sender, filter = only when message text matches.",
                    f"autoresponder_message_mode = {settings_map['autoresponder_message_mode']}",
                    "# Message text filter. Without wildcards it behaves like contains.",
                    f"autoresponder_message_filter = {settings_map['autoresponder_message_filter']}",
                    "",
                    "# Reply",
                    "# Fixed direct-message reply text sent back to the sender.",
                    f"autoresponder_reply = {settings_map['autoresponder_reply']}",
                    "# Optional template with variables from the triggering message.",
                    "# Available variables: %node_id%, %label%, %shortname%, %longname%, %message%, %channel_index%, %channel_name%, %scope%, %answer%",
                    "# %answer% is replaced with the configured autoresponder_reply text.",
                    "# Example: Autoresponder: from %longname%: %message% / Message;  %answer%",
                    f"autoresponder_reply_template = {settings_map['autoresponder_reply_template']}",
                    "",
                ]
            )

        return "\n".join(lines)

    @staticmethod
    def example_command(family: str, script_path: Path) -> str:
        script_name = f"./{script_path.name}"
        if family == "listen":
            return (
                f'python {script_name} --listen --port <PORT> --listen-filter "FR*" '
                '--listen-channel-index 1 --dm-only --text-only --forcecfg'
            )
        if family == "autoresponder":
            return f'python {script_name} --listen --autoresponder'
        return (
            f'python {script_name} --mode send --port <PORT> --channel-index 1 --ack '
            '--target-mode all --message "Hello Mesh" --timeout 60 --forcecfg'
        )

    @staticmethod
    def save_cfg_files(output_dir: Path, send_settings: dict, listen_settings: dict, autoresponder_settings: dict, script_path: Path) -> tuple[Path, Path, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        send_path = ConfigLogic.config_path(output_dir, "send")
        listen_path = ConfigLogic.config_path(output_dir, "listen")
        autoresponder_path = ConfigLogic.config_path(output_dir, "autoresponder")
        send_path.write_text(ConfigLogic.render_cfg("send", send_settings, script_path), encoding="utf-8")
        listen_path.write_text(ConfigLogic.render_cfg("listen", listen_settings, script_path), encoding="utf-8")
        autoresponder_path.write_text(ConfigLogic.render_cfg("autoresponder", autoresponder_settings, script_path), encoding="utf-8")
        return send_path, listen_path, autoresponder_path

    @staticmethod
    def save_cfg(output_dir: Path, family: str, settings: dict, script_path: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = ConfigLogic.config_path(output_dir, family)
        path.write_text(ConfigLogic.render_cfg(family, settings, script_path), encoding="utf-8")
        return path


def resolve_console_python() -> str:
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        python_exe = executable.with_name("python.exe")
        if python_exe.exists():
            return str(python_exe)
    return str(executable)


class MeshtasticConfigGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1380x860")
        self.root.minsize(1200, 760)

        self.send_specs = SEND_FIELDS
        self.listen_specs = LISTEN_FIELDS
        self.autoresponder_specs = AUTORESPONDER_FIELDS
        self.output_dir_var = tk.StringVar(value=str(SCRIPT_DIR))
        self.status_var = tk.StringVar(value="Ready.")

        self.send_vars = self._create_variables(self.send_specs)
        self.listen_vars = self._create_variables(self.listen_specs)
        self.autoresponder_vars = self._create_variables(self.autoresponder_specs)

        self.send_preview = None
        self.listen_preview = None
        self.autoresponder_preview = None
        self.form_notebook = None
        self.preview_notebook = None
        self.load_button = None
        self.save_button = None
        self._active_scroll_canvas = None

        self._build_layout()
        self.load_existing_configs(initial=True)

    def _create_variables(self, specs: list[FieldSpec]) -> dict[str, tk.Variable]:
        variables: dict[str, tk.Variable] = {}
        for spec in specs:
            if spec.field_type == "bool":
                variables[spec.key] = tk.BooleanVar(value=bool(spec.default))
            else:
                variables[spec.key] = tk.StringVar(value="" if spec.default == "" else str(spec.default))
        return variables

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top_bar = ttk.Frame(self.root, padding=(12, 12, 12, 6))
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.columnconfigure(1, weight=1)

        ttk.Label(top_bar, text="Output Folder").grid(row=0, column=0, padx=(0, 8), sticky="w")
        ttk.Entry(top_bar, textvariable=self.output_dir_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(top_bar, text="Browse", command=self.choose_output_directory).grid(row=0, column=2, padx=8)
        ttk.Button(top_bar, text="Generate Config", command=self.generate_preview).grid(row=0, column=3, padx=4)
        self.load_button = ttk.Button(top_bar, text="Load Send CFG", command=self.load_config)
        self.load_button.grid(row=0, column=4, padx=4)
        self.save_button = ttk.Button(top_bar, text="Save Send CFG", command=self.save_config)
        self.save_button.grid(row=0, column=5, padx=4)

        main_frame = ttk.Panedwindow(self.root, orient="horizontal")
        main_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))

        form_container = ttk.Frame(main_frame, padding=8)
        preview_container = ttk.Frame(main_frame, padding=8)
        main_frame.add(form_container, weight=3)
        main_frame.add(preview_container, weight=2)

        form_container.columnconfigure(0, weight=1)
        form_container.rowconfigure(0, weight=1)
        preview_container.columnconfigure(0, weight=1)
        preview_container.rowconfigure(0, weight=1)

        self.form_notebook = ttk.Notebook(form_container)
        self.form_notebook.grid(row=0, column=0, sticky="nsew")

        send_tab, send_content = self._create_scrollable_tab(self.form_notebook)
        listen_tab, listen_content = self._create_scrollable_tab(self.form_notebook)
        autoresponder_tab, autoresponder_content = self._create_scrollable_tab(self.form_notebook)
        self.form_notebook.add(send_tab, text="Send CFG")
        self.form_notebook.add(listen_tab, text="Listen CFG")
        self.form_notebook.add(autoresponder_tab, text="Autoresponder CFG")
        self.form_notebook.bind("<<NotebookTabChanged>>", self._on_form_tab_changed)

        self._build_tab_actions(send_content, [("Start Send Script", self.start_send_script)], columns=2)
        self._build_tab_actions(listen_content, [("Start Listen Script", self.start_listen_script)], columns=2)
        self._build_form(send_content, self.send_specs, self.send_vars, columns=2)
        self._build_form(listen_content, self.listen_specs, self.listen_vars, columns=2)
        self._build_form(autoresponder_content, self.autoresponder_specs, self.autoresponder_vars, columns=2)

        self.preview_notebook = ttk.Notebook(preview_container)
        self.preview_notebook.grid(row=0, column=0, sticky="nsew")

        send_preview_tab = ttk.Frame(self.preview_notebook, padding=6)
        listen_preview_tab = ttk.Frame(self.preview_notebook, padding=6)
        autoresponder_preview_tab = ttk.Frame(self.preview_notebook, padding=6)
        self.preview_notebook.add(send_preview_tab, text=SEND_CFG_NAME)
        self.preview_notebook.add(listen_preview_tab, text=LISTEN_CFG_NAME)
        self.preview_notebook.add(autoresponder_preview_tab, text=AUTORESPONDER_CFG_NAME)

        self.send_preview = self._build_preview_text(send_preview_tab)
        self.listen_preview = self._build_preview_text(listen_preview_tab)
        self.autoresponder_preview = self._build_preview_text(autoresponder_preview_tab)

        status_bar = ttk.Frame(self.root, padding=(12, 4, 12, 12))
        status_bar.grid(row=2, column=0, sticky="ew")
        status_bar.columnconfigure(0, weight=1)
        ttk.Label(status_bar, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        self._update_action_labels()

    def _create_scrollable_tab(self, notebook: ttk.Notebook) -> tuple[ttk.Frame, ttk.Frame]:
        tab = ttk.Frame(notebook)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)

        canvas = tk.Canvas(tab, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        content = ttk.Frame(canvas, padding=10)
        content_window = canvas.create_window((0, 0), window=content, anchor="nw")

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        content.bind(
            "<Configure>",
            lambda _event, current_canvas=canvas: current_canvas.configure(scrollregion=current_canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event, current_canvas=canvas, window_id=content_window: current_canvas.itemconfigure(window_id, width=event.width),
        )
        content.bind("<Enter>", lambda _event, current_canvas=canvas: self._set_active_scroll_canvas(current_canvas))
        content.bind("<Leave>", lambda _event: self._set_active_scroll_canvas(None))
        canvas.bind("<Enter>", lambda _event, current_canvas=canvas: self._set_active_scroll_canvas(current_canvas))
        canvas.bind("<Leave>", lambda _event: self._set_active_scroll_canvas(None))
        return tab, content

    def _set_active_scroll_canvas(self, canvas: tk.Canvas | None) -> None:
        self._active_scroll_canvas = canvas

    def _on_mousewheel(self, event) -> None:
        if self._active_scroll_canvas is None:
            return
        if hasattr(event, "delta") and event.delta:
            steps = -1 if event.delta > 0 else 1
        elif getattr(event, "num", None) == 4:
            steps = -1
        elif getattr(event, "num", None) == 5:
            steps = 1
        else:
            return
        self._active_scroll_canvas.yview_scroll(steps, "units")

    def _build_form(self, parent: ttk.Frame, specs: list[FieldSpec], variables: dict[str, tk.Variable], columns: int) -> None:
        for column in range(columns):
            parent.columnconfigure(column, weight=1)

        row = parent.grid_size()[1]
        column = 0
        for spec in specs:
            frame = ttk.LabelFrame(parent, text=spec.label, padding=8)
            frame.grid(row=row, column=column, padx=6, pady=6, sticky="nsew")
            frame.columnconfigure(0, weight=1)

            widget = self._create_widget(frame, spec, variables[spec.key])
            widget.grid(row=0, column=0, sticky="ew")
            ttk.Label(frame, text=spec.help_text, wraplength=240, foreground="#555555").grid(
                row=1, column=0, sticky="w", pady=(6, 0)
            )

            column += 1
            if column >= columns:
                column = 0
                row += 1

    def _build_tab_actions(self, parent: ttk.Frame, actions: list[tuple[str, object]], columns: int) -> None:
        if not actions:
            return
        next_row = parent.grid_size()[1]
        action_frame = ttk.Frame(parent, padding=(6, 0, 6, 8))
        action_frame.grid(row=next_row, column=0, columnspan=columns, sticky="ew")
        for index, (label, callback) in enumerate(actions):
            ttk.Button(action_frame, text=label, command=callback).grid(row=0, column=index, padx=(0, 8), sticky="w")

    def _create_widget(self, parent: ttk.Frame, spec: FieldSpec, variable: tk.Variable):
        if spec.field_type == "choice":
            return ttk.Combobox(parent, textvariable=variable, values=spec.choices, state="readonly", width=spec.width)
        if spec.field_type == "bool":
            return ttk.Checkbutton(parent, variable=variable, text="Enabled")
        return ttk.Entry(parent, textvariable=variable, width=spec.width)

    def _build_preview_text(self, parent: ttk.Frame) -> tk.Text:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        text = tk.Text(parent, wrap="none", font=("Consolas", 10))
        y_scroll = ttk.Scrollbar(parent, orient="vertical", command=text.yview)
        x_scroll = ttk.Scrollbar(parent, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        return text

    def choose_output_directory(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_dir_var.get() or str(SCRIPT_DIR))
        if selected:
            self.output_dir_var.set(selected)
            self.load_existing_configs()

    def _collect_values(self, specs: list[FieldSpec], variables: dict[str, tk.Variable]) -> dict:
        return {spec.key: variables[spec.key].get() for spec in specs}

    def _set_values(self, specs: list[FieldSpec], variables: dict[str, tk.Variable], values: dict) -> None:
        for spec in specs:
            value = values.get(spec.key, spec.default)
            if spec.field_type == "bool":
                variables[spec.key].set(bool(value))
            else:
                variables[spec.key].set("" if value == "" else str(value))

    def _validated_all(self) -> tuple[dict, dict, dict]:
        send_settings = ConfigLogic.validate_settings(self._collect_values(self.send_specs, self.send_vars), self.send_specs)
        listen_settings = ConfigLogic.validate_settings(self._collect_values(self.listen_specs, self.listen_vars), self.listen_specs)
        autoresponder_settings = ConfigLogic.validate_settings(self._collect_values(self.autoresponder_specs, self.autoresponder_vars), self.autoresponder_specs)
        send_settings["mode"] = "send"
        listen_settings["mode"] = "listen"
        return send_settings, listen_settings, autoresponder_settings

    def _active_family(self) -> str:
        if self.form_notebook is None:
            return "send"
        current_index = self.form_notebook.index(self.form_notebook.select())
        return "listen" if current_index == 1 else "autoresponder" if current_index == 2 else "send"

    def _update_action_labels(self) -> None:
        family = self._active_family()
        label = "Listen CFG" if family == "listen" else "Autoresponder CFG" if family == "autoresponder" else "Send CFG"
        if self.load_button is not None:
            self.load_button.configure(text=f"Load {label}")
        if self.save_button is not None:
            self.save_button.configure(text=f"Save {label}")

    def _on_form_tab_changed(self, _event=None) -> None:
        family = self._active_family()
        self._update_action_labels()
        if self.preview_notebook is not None:
            self.preview_notebook.select(1 if family == "listen" else 2 if family == "autoresponder" else 0)

    def generate_preview(self) -> None:
        try:
            send_settings, listen_settings, autoresponder_settings = self._validated_all()
            output_dir = Path(self.output_dir_var.get()).expanduser()
            send_text = ConfigLogic.render_cfg("send", send_settings, output_dir / "meshtastic_mass_com.py")
            listen_text = ConfigLogic.render_cfg("listen", listen_settings, output_dir / "meshtastic_mass_com.py")
            autoresponder_text = ConfigLogic.render_cfg("autoresponder", autoresponder_settings, output_dir / "meshtastic_mass_com.py")
            self._set_preview(self.send_preview, send_text)
            self._set_preview(self.listen_preview, listen_text)
            self._set_preview(self.autoresponder_preview, autoresponder_text)
            self.status_var.set("Preview generated successfully.")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            self.status_var.set(f"Validation failed: {exc}")

    def _set_preview(self, widget: tk.Text, content: str) -> None:
        widget.delete("1.0", tk.END)
        widget.insert("1.0", content)

    def load_existing_configs(self, initial: bool = False) -> None:
        try:
            output_dir = Path(self.output_dir_var.get()).expanduser()
            send_settings, listen_settings, autoresponder_settings = ConfigLogic.load_cfg_set(output_dir)
            self._set_values(self.send_specs, self.send_vars, send_settings)
            self._set_values(self.listen_specs, self.listen_vars, listen_settings)
            self._set_values(self.autoresponder_specs, self.autoresponder_vars, autoresponder_settings)
            self.generate_preview()
            send_exists = ConfigLogic.config_path(output_dir, "send").exists()
            listen_exists = ConfigLogic.config_path(output_dir, "listen").exists()
            autoresponder_exists = ConfigLogic.config_path(output_dir, "autoresponder").exists()
            if send_exists or listen_exists or autoresponder_exists:
                self.status_var.set(f"Loaded existing cfg files from {output_dir}")
            elif initial:
                self.status_var.set("No existing cfg files found. Showing default values.")
            else:
                self.status_var.set(f"No cfg files found in {output_dir}. Showing default values.")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not load existing config files:\n{exc}")
            self.status_var.set(f"Load failed: {exc}")

    def load_config(self) -> None:
        try:
            family = self._active_family()
            initial_dir = Path(self.output_dir_var.get()).expanduser()
            selected = filedialog.askopenfilename(
                title=f"Load {family} cfg template",
                initialdir=str(initial_dir),
                filetypes=[("CFG files", "*.cfg"), ("All files", "*.*")],
            )
            if not selected:
                self.status_var.set("Load cancelled.")
                return
            selected_path = Path(selected)
            settings = ConfigLogic.load_cfg_from_path(selected_path, family)
            if family == "listen":
                self._set_values(self.listen_specs, self.listen_vars, settings)
            elif family == "autoresponder":
                self._set_values(self.autoresponder_specs, self.autoresponder_vars, settings)
            else:
                self._set_values(self.send_specs, self.send_vars, settings)
            self.generate_preview()
            self.status_var.set(f"Loaded {family} cfg template from {selected_path}")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not load config files:\n{exc}")
            self.status_var.set(f"Load failed: {exc}")

    def save_config(self) -> None:
        try:
            family = self._active_family()
            saved_path = self._save_family_config(family)
            self.generate_preview()
            self.status_var.set(f"Saved: {saved_path.name}")
        except RuntimeError:
            return
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not save config files:\n{exc}")
            self.status_var.set(f"Save failed: {exc}")

    def _settings_for_family(self, family: str, send_settings: dict, listen_settings: dict, autoresponder_settings: dict) -> dict:
        return (
            autoresponder_settings
            if family == "autoresponder"
            else listen_settings
            if family == "listen"
            else send_settings
        )

    def _save_family_config(self, family: str) -> Path:
        send_settings, listen_settings, autoresponder_settings = self._validated_all()
        output_dir = Path(self.output_dir_var.get()).expanduser()
        settings = self._settings_for_family(family, send_settings, listen_settings, autoresponder_settings)
        target_path = ConfigLogic.config_path(output_dir, family)
        new_content = ConfigLogic.render_cfg(family, settings, output_dir / "meshtastic_mass_com.py")
        if target_path.exists():
            try:
                current_content = target_path.read_text(encoding="utf-8")
            except OSError:
                current_content = None
            if current_content is None or current_content != new_content:
                overwrite = messagebox.askyesno(
                    APP_TITLE,
                    f"The existing {family} cfg will be overwritten:\n\n{target_path}\n\nContinue?",
                    icon="warning",
                )
                if not overwrite:
                    self.status_var.set(f"Save cancelled for {target_path.name}")
                    raise RuntimeError("Save cancelled.")
        return ConfigLogic.save_cfg(
            output_dir,
            family,
            settings,
            output_dir / "meshtastic_mass_com.py",
        )

    def _launch_script(self, family: str) -> None:
        output_dir = Path(self.output_dir_var.get()).expanduser()
        script_path = output_dir / "meshtastic_mass_com.py"
        if not script_path.exists():
            messagebox.showerror(APP_TITLE, f"Main script not found:\n\n{script_path}")
            self.status_var.set(f"Launch failed: missing {script_path.name}")
            return

        try:
            self._save_family_config(family)
        except RuntimeError:
            return
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not save {family} cfg before launch:\n{exc}")
            self.status_var.set(f"Launch failed: {exc}")
            return

        python_cmd = resolve_console_python()
        command = [python_cmd, str(script_path)]
        if family == "listen":
            command.append("--listen")
        else:
            command.extend(["--mode", "send"])

        try:
            if sys.platform.startswith("win"):
                cmdline = subprocess.list2cmdline(command)
                launch_command = ["cmd.exe", "/k", cmdline]
                subprocess.Popen(
                    launch_command,
                    cwd=str(output_dir),
                    creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                )
            else:
                subprocess.Popen(command, cwd=str(output_dir))
            self.status_var.set(f"Started {family} script: {' '.join(command[2:]) or 'default'}")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not start the script:\n{exc}")
            self.status_var.set(f"Launch failed: {exc}")

    def start_send_script(self) -> None:
        self._launch_script("send")

    def start_listen_script(self) -> None:
        self._launch_script("listen")


def main() -> None:
    root = tk.Tk()
    style = ttk.Style(root)
    try:
        style.theme_use("vista")
    except tk.TclError:
        pass
    app = MeshtasticConfigGUI(root)
    root.bind_all("<MouseWheel>", app._on_mousewheel)
    root.bind_all("<Button-4>", app._on_mousewheel)
    root.bind_all("<Button-5>", app._on_mousewheel)
    root.mainloop()


if __name__ == "__main__":
    main()
