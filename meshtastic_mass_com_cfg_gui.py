import configparser
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


APP_TITLE = "Meshtastic_Mass_Com Config Generator"
SCRIPT_DIR = Path(__file__).resolve().parent
SEND_CFG_NAME = "meshtastic_mass_com.send.cfg"
LISTEN_CFG_NAME = "meshtastic_mass_com.listen.cfg"
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
    FieldSpec("history_file", "History File", "text", "", "Optional JSONL history file used while sending. Example: ./logs/history.jsonl."),
]


LISTEN_FIELDS = [
    FieldSpec("port", "Serial Port", "text", "", "Serial port used for listening. Examples: /dev/ttyUSB0, /dev/ttyACM0, or COM7."),
    FieldSpec("timeout", "Timeout (s)", "int", 30, "Connection timeout for the listen workflow. Example: 30."),
    FieldSpec("listen_filter", "Listen Filter", "text", "*", "Only show packets whose sender matches this filter. Example: FR*."),
    FieldSpec("listen_channel_index", "Listen Channel", "optional_int", "", "Only show packets for this channel index. Leave blank for all. Example: 1."),
    FieldSpec("listen_dm_only", "DM Only", "bool", False, "Only show direct messages while listening. Example: disabled."),
    FieldSpec("listen_group_only", "Group Only", "bool", False, "Only show group or broadcast traffic while listening. Example: disabled."),
    FieldSpec("listen_text_only", "Text Only", "bool", False, "Only show text packets while listening. Example: enabled."),
    FieldSpec("log_file", "Log File", "text", "", "Optional JSONL listen log file. Example: ./logs/listen_log.jsonl."),
    FieldSpec("history_file", "History File", "text", "", "Optional JSONL history file used while listening. Example: ./logs/listen_history.jsonl."),
    FieldSpec("history_filter", "History Filter", "text", "", "Filter used by history mode. Example: Naunhof."),
    FieldSpec("history_limit", "History Limit", "int", 20, "Number of recent history entries to show. Example: 50."),
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
    def config_path(output_dir: Path, family: str) -> Path:
        return output_dir / (LISTEN_CFG_NAME if family == "listen" else SEND_CFG_NAME)

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
        parser = configparser.ConfigParser()
        parser.read(path, encoding="utf-8")
        if not parser.has_section(section_name):
            return {}
        return {key: value for key, value in parser[section_name].items()}

    @staticmethod
    def load_cfg_pair(output_dir: Path) -> tuple[dict, dict]:
        send_settings = ConfigLogic.default_send_settings()
        listen_settings = ConfigLogic.default_listen_settings()

        send_path = ConfigLogic.config_path(output_dir, "send")
        listen_path = ConfigLogic.config_path(output_dir, "listen")

        if send_path.exists():
            send_settings.update(ConfigLogic.coerce_loaded_values(send_path, SEND_FIELDS))

        if listen_path.exists():
            listen_settings.update(ConfigLogic.coerce_loaded_values(listen_path, LISTEN_FIELDS))

        return send_settings, listen_settings

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
        settings_map = ConfigLogic.settings_to_strings(settings, SEND_FIELDS if family == "send" else LISTEN_FIELDS)
        family_title = "Send workflow" if family == "send" else "Listen workflow"
        family_modes = "send, broadcast, history" if family == "send" else "listen"
        example = ConfigLogic.example_command(family, script_path)

        lines = [
            f"# Meshtastic_Mass_Com - {family_title} configuration",
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
        else:
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
                    "# Files",
                    f"log_file = {settings_map['log_file']}",
                    f"history_file = {settings_map['history_file']}",
                    f"history_filter = {settings_map['history_filter']}",
                    f"history_limit = {settings_map['history_limit']}",
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
        return (
            f'python {script_name} --mode send --port <PORT> --channel-index 1 --ack '
            '--target-mode all --message "Hello Mesh" --timeout 60 --forcecfg'
        )

    @staticmethod
    def save_cfg_files(output_dir: Path, send_settings: dict, listen_settings: dict, script_path: Path) -> tuple[Path, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        send_path = ConfigLogic.config_path(output_dir, "send")
        listen_path = ConfigLogic.config_path(output_dir, "listen")
        send_path.write_text(ConfigLogic.render_cfg("send", send_settings, script_path), encoding="utf-8")
        listen_path.write_text(ConfigLogic.render_cfg("listen", listen_settings, script_path), encoding="utf-8")
        return send_path, listen_path


class MeshtasticConfigGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1380x860")
        self.root.minsize(1200, 760)

        self.send_specs = SEND_FIELDS
        self.listen_specs = LISTEN_FIELDS
        self.output_dir_var = tk.StringVar(value=str(SCRIPT_DIR))
        self.status_var = tk.StringVar(value="Ready.")

        self.send_vars = self._create_variables(self.send_specs)
        self.listen_vars = self._create_variables(self.listen_specs)

        self.send_preview = None
        self.listen_preview = None

        self._build_layout()
        self.generate_preview()

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
        ttk.Button(top_bar, text="Load Config", command=self.load_config).grid(row=0, column=3, padx=4)
        ttk.Button(top_bar, text="Generate Config", command=self.generate_preview).grid(row=0, column=4, padx=4)
        ttk.Button(top_bar, text="Save Config", command=self.save_config).grid(row=0, column=5, padx=4)

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

        notebook = ttk.Notebook(form_container)
        notebook.grid(row=0, column=0, sticky="nsew")

        send_tab = ttk.Frame(notebook, padding=10)
        listen_tab = ttk.Frame(notebook, padding=10)
        notebook.add(send_tab, text="Send CFG")
        notebook.add(listen_tab, text="Listen CFG")

        self._build_form(send_tab, self.send_specs, self.send_vars, columns=2)
        self._build_form(listen_tab, self.listen_specs, self.listen_vars, columns=2)

        preview_notebook = ttk.Notebook(preview_container)
        preview_notebook.grid(row=0, column=0, sticky="nsew")

        send_preview_tab = ttk.Frame(preview_notebook, padding=6)
        listen_preview_tab = ttk.Frame(preview_notebook, padding=6)
        preview_notebook.add(send_preview_tab, text=SEND_CFG_NAME)
        preview_notebook.add(listen_preview_tab, text=LISTEN_CFG_NAME)

        self.send_preview = self._build_preview_text(send_preview_tab)
        self.listen_preview = self._build_preview_text(listen_preview_tab)

        status_bar = ttk.Frame(self.root, padding=(12, 4, 12, 12))
        status_bar.grid(row=2, column=0, sticky="ew")
        status_bar.columnconfigure(0, weight=1)
        ttk.Label(status_bar, textvariable=self.status_var).grid(row=0, column=0, sticky="w")

    def _build_form(self, parent: ttk.Frame, specs: list[FieldSpec], variables: dict[str, tk.Variable], columns: int) -> None:
        for column in range(columns):
            parent.columnconfigure(column, weight=1)

        row = 0
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
            self.status_var.set(f"Output folder selected: {selected}")

    def _collect_values(self, specs: list[FieldSpec], variables: dict[str, tk.Variable]) -> dict:
        return {spec.key: variables[spec.key].get() for spec in specs}

    def _set_values(self, specs: list[FieldSpec], variables: dict[str, tk.Variable], values: dict) -> None:
        for spec in specs:
            value = values.get(spec.key, spec.default)
            if spec.field_type == "bool":
                variables[spec.key].set(bool(value))
            else:
                variables[spec.key].set("" if value == "" else str(value))

    def _validated_all(self) -> tuple[dict, dict]:
        send_settings = ConfigLogic.validate_settings(self._collect_values(self.send_specs, self.send_vars), self.send_specs)
        listen_settings = ConfigLogic.validate_settings(self._collect_values(self.listen_specs, self.listen_vars), self.listen_specs)
        send_settings["mode"] = "send"
        listen_settings["mode"] = "listen"
        return send_settings, listen_settings

    def generate_preview(self) -> None:
        try:
            send_settings, listen_settings = self._validated_all()
            output_dir = Path(self.output_dir_var.get()).expanduser()
            send_text = ConfigLogic.render_cfg("send", send_settings, output_dir / "meshtastic_mass_com.py")
            listen_text = ConfigLogic.render_cfg("listen", listen_settings, output_dir / "meshtastic_mass_com.py")
            self._set_preview(self.send_preview, send_text)
            self._set_preview(self.listen_preview, listen_text)
            self.status_var.set("Preview generated successfully.")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            self.status_var.set(f"Validation failed: {exc}")

    def _set_preview(self, widget: tk.Text, content: str) -> None:
        widget.delete("1.0", tk.END)
        widget.insert("1.0", content)

    def load_config(self) -> None:
        try:
            output_dir = Path(self.output_dir_var.get()).expanduser()
            send_settings, listen_settings = ConfigLogic.load_cfg_pair(output_dir)
            self._set_values(self.send_specs, self.send_vars, send_settings)
            self._set_values(self.listen_specs, self.listen_vars, listen_settings)
            self.generate_preview()
            self.status_var.set(f"Loaded cfg files from {output_dir}")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not load config files:\n{exc}")
            self.status_var.set(f"Load failed: {exc}")

    def save_config(self) -> None:
        try:
            send_settings, listen_settings = self._validated_all()
            output_dir = Path(self.output_dir_var.get()).expanduser()
            send_path, listen_path = ConfigLogic.save_cfg_files(
                output_dir,
                send_settings,
                listen_settings,
                output_dir / "meshtastic_mass_com.py",
            )
            self.generate_preview()
            self.status_var.set(f"Saved: {send_path.name} and {listen_path.name}")
            messagebox.showinfo(
                APP_TITLE,
                f"Config files written successfully:\n\n{send_path}\n{listen_path}",
            )
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not save config files:\n{exc}")
            self.status_var.set(f"Save failed: {exc}")


def main() -> None:
    root = tk.Tk()
    style = ttk.Style(root)
    try:
        style.theme_use("vista")
    except tk.TclError:
        pass
    MeshtasticConfigGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
