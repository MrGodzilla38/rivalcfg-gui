#!/usr/bin/env python3

# GTK3 dependency check
import sys
import os
import json
import subprocess
import threading
import math
import gettext
import locale
import logging
from logging.handlers import TimedRotatingFileHandler

def _get_locale_dir():
    locale_env = os.environ.get("RIVALCFG_GUI_LOCALE_DIR")
    if locale_env:
        return locale_env
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "locales")

LOCALE_DIR = _get_locale_dir()

def setup_gettext(lang=None):
    """Setup gettext translation for the given language."""
    if not lang:
        lang = locale.getlocale()[0][:2] if locale.getlocale()[0] else "en"
    try:
        translation = gettext.translation("rivalcfg_gui", localedir=LOCALE_DIR, languages=[lang], fallback=True)
    except FileNotFoundError:
        translation = gettext.NullTranslations()
    return translation.gettext

def _set_language(lang=None):
    """Update the global _ function to use the specified language."""
    global _
    _ = setup_gettext(lang)

_ = setup_gettext()

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, Gdk, GLib, GdkPixbuf
    import cairo
except ImportError:
    logging.critical("python-gobject is not installed. Install: pacman -S python-gobject")
    print(_("python-gobject is not installed. Install: pacman -S python-gobject"))
    sys.exit(1)

try:
    from pynput import mouse as pynput_mouse
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

try:
    import evdev
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False

try:
    import Xlib
    X11_AVAILABLE = True
except ImportError:
    X11_AVAILABLE = False

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
FLATPAK_ID = os.environ.get("FLATPAK_ID")
IN_FLATPAK = FLATPAK_ID is not None

# Prefer bundled rivalcfg binary, fall back to pip-installed or system PATH
def _find_rivalcfg():
    bundled = os.path.join(SCRIPT_DIR, "rivalcfg")
    if os.path.isfile(bundled) and os.access(bundled, os.X_OK):
        return bundled
    return "rivalcfg"

RIVALCFG_BIN = _find_rivalcfg()

# Check rivalcfg CLI availability
try:
    subprocess.run([RIVALCFG_BIN], capture_output=True, timeout=5)
except FileNotFoundError:
    logging.critical("rivalcfg is not installed. Install: pip install rivalcfg")
    print(_("rivalcfg is not installed. Install: pip install rivalcfg"))
    sys.exit(1)

# Global dictionary holding application state
app_state = {}

SETTINGS_DIR = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
SETTINGS_DIR = os.path.join(SETTINGS_DIR, "rivalcfg-gui")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")
LOGS_DIR = os.path.join(SETTINGS_DIR, "logs")

DEFAULT_SETTINGS = {
    "startup_minimize": False,
    "auto_apply": False,
    "accent_color": "#ff7800",
    "language": "en",
    "active_profile": "Default",
    "macro_enabled": False,
    "macro_cps": 10,
    "macro_trigger_key": "f6",
    "macro_toggle_key": "",
    "macro_mode": "toggle",
    "macro_button": "left",
}


def setup_logging():
    """Configure logging: daily rotating logs kept for 7 days."""
    os.makedirs(LOGS_DIR, exist_ok=True)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    def log_namer(default_name):
        basedir = os.path.dirname(default_name)
        fname = os.path.basename(default_name)
        parts = fname.split(".")
        if len(parts) >= 3 and len(parts[-1]) == 10 and parts[-1][4] == "-":
            return os.path.join(basedir, f"{parts[-1]}.log")
        return default_name

    rotating = TimedRotatingFileHandler(
        os.path.join(LOGS_DIR, "app.log"),
        when="midnight", interval=1, backupCount=7, encoding="utf-8"
    )
    rotating.namer = log_namer
    rotating.setFormatter(formatter)
    rotating.setLevel(logging.DEBUG)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(rotating)


def load_settings():
    """Load settings from JSON file."""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                saved = json.load(f)
            settings = dict(DEFAULT_SETTINGS)
            settings.update(saved)
            return settings
    except Exception as e:
        logging.warning("Failed to load settings: %s", e)
    return dict(DEFAULT_SETTINGS)


def save_settings():
    """Save current settings to JSON file."""
    try:
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        to_save = {k: v for k, v in app_state["settings"].items() if k != "macro_enabled"}
        with open(SETTINGS_FILE, "w") as f:
            json.dump(to_save, f, indent=4)
    except Exception as e:
        logging.error("Failed to save settings: %s", e)
        print(_("Failed to save settings: {}").format(e))

PROFILES_DIR = os.path.join(SETTINGS_DIR, "profiles")

def ensure_profiles_dir():
    os.makedirs(PROFILES_DIR, exist_ok=True)

def list_profiles():
    ensure_profiles_dir()
    profiles = []
    for f in os.listdir(PROFILES_DIR):
        if f.endswith(".json"):
            profiles.append(f[:-5])
    return sorted(profiles) if profiles else ["Default"]

def save_profile(name):
    ensure_profiles_dir()
    s = app_state.get("settings", {})
    profile = {
        "dpi_values": app_state.get("dpi_values", [800, 1600]),
        "polling_hz": app_state.get("polling_hz", 1000),
        "z1_hex": app_state.get("z1_hex", "ff6600"),
        "z2_hex": app_state.get("z2_hex", "ff6600"),
        "z3_hex": app_state.get("z3_hex", "ff6600"),
        "z4_hex": app_state.get("z4_hex", "ff6600"),
        "selected_effect": app_state.get("selected_effect", "steady"),
        "button_mapping": app_state.get("button_mapping", {}),
        "macro_cps": s.get("macro_cps", 10),
        "macro_trigger_key": s.get("macro_trigger_key", "f6"),
        "macro_toggle_key": s.get("macro_toggle_key", ""),
        "macro_mode": s.get("macro_mode", "toggle"),
        "macro_button": s.get("macro_button", "left"),
    }
    path = os.path.join(PROFILES_DIR, f"{name}.json")
    with open(path, "w") as f:
        json.dump(profile, f, indent=4)
    logging.info("Profile saved: %s (dpi=%s, polling=%s)", name,
                 profile["dpi_values"], profile["polling_hz"])

def load_profile_data(name):
    ensure_profiles_dir()
    path = os.path.join(PROFILES_DIR, f"{name}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)

def delete_profile_file(name):
    path = os.path.join(PROFILES_DIR, f"{name}.json")
    if os.path.exists(path):
        os.remove(path)

def rename_profile_file(old_name, new_name):
    if not new_name or old_name == new_name:
        return False
    ensure_profiles_dir()
    old_path = os.path.join(PROFILES_DIR, f"{old_name}.json")
    new_path = os.path.join(PROFILES_DIR, f"{new_name}.json")
    if not os.path.exists(old_path) or os.path.exists(new_path):
        return False
    os.rename(old_path, new_path)
    return True

def save_active_profile():
    name = app_state.get("settings", {}).get("active_profile", "Default")
    if name:
        save_profile(name)

CSS = """
window {
    background: #0a0a0f;
}

label {
    color: #ffffff;
}

button {
    background: #0f0f1a;
    color: #ffffff;
    border: 1px solid #2a2a40;
    border-radius: 6px;
    padding: 6px 16px;
}

entry {
    background: #0f0f1a;
    color: #ffffff;
    border: 1px solid #2a2a40;
    border-radius: 4px;
}

combobox {
    background: #0f0f1a;
    color: #ffffff;
    border: 1px solid #2a2a40;
    border-radius: 4px;
}

combobox window {
    background: #0f0f1a;
    color: #ffffff;
}

spinbutton {
    background: #0f0f1a;
    color: #ffffff;
    border: 1px solid #2a2a40;
    border-radius: 4px;
}

checkbutton {
    color: #ffffff;
}

.sidebar {
    background: #0d0d14;
    border-right: 1px solid #1e1e2e;
}

.sidebar combobox {
    min-width: 0;
}

.profile-selector {
    background: #0f0f1a;
    border: 1px solid #2a2a40;
    border-radius: 4px;
    padding: 6px 10px;
    min-height: 28px;
}

.profile-selector:hover {
    border-color: #3a3a55;
}

.profile-selector label {
    color: #ffffff;
    font-size: 13px;
}

.profile-popover {
    background: #0f0f1a;
    border: 1px solid #2a2a40;
    padding: 4px 0;
}

.profile-popover-row {
    padding: 2px 4px;
}

.profile-popover-row:hover {
    background-color: #1a1a2e;
}

.profile-menu-select {
    background: transparent;
    border: none;
    color: #ccccdd;
    font-size: 13px;
    padding: 6px 8px;
}

.profile-menu-select:hover {
    color: #ffffff;
}

.profile-menu-action {
    background: transparent;
    border: none;
    color: #888899;
    font-size: 14px;
    padding: 4px 6px;
    min-width: 28px;
    min-height: 28px;
}

.profile-menu-action:hover {
    background: #1a1a2e;
    color: #ccccdd;
}

.profile-menu-delete:hover {
    color: #ff7800;
}

.nav-btn {
    background: transparent;
    border: none;
    color: #888899;
    padding: 10px 14px;
    border-radius: 6px;
    font-size: 13px;
}

.nav-active {
    background: #1a0a14;
    color: #ff7800;
}

.page-title {
    font-size: 20px;
    font-weight: bold;
    color: #ffffff;
}

.card {
    background: #0f0f1a;
    border: 1px solid #1e1e2e;
    border-radius: 8px;
    padding: 20px;
}

.card-title {
    font-size: 11px;
    color: #ff7800;
    font-weight: bold;
}

.value-display {
    font-size: 26px;
    color: #ffffff;
    font-family: monospace;
    border: none;
    background: transparent;
    box-shadow: none;
}

spinbutton.value-display button {
    -gtk-icon-source: none;
    min-width: 0;
    min-height: 0;
    padding: 0;
    border: none;
    background: transparent;
}

.apply-btn {
    background: #ff7800;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
}

.apply-btn:hover {
    background: #ff5555;
}

.reset-btn {
    background: transparent;
    border: 1px solid #2a2a40;
    color: #666688;
    border-radius: 6px;
    padding: 8px 20px;
}

.status-bar {
    background: #080810;
    border-top: 1px solid #1a1a28;
    padding: 6px 20px;
}

.status-running {
    color: #ffaa33;
}

.status-ok {
    color: #33cc77;
}

.status-error {
    color: #ff7800;
}

scale trough {
    background: #1a1a2e;
    min-height: 6px;
}

scale trough highlight {
    background: #ff7800;
}

scale slider {
    background: #ffffff;
    min-width: 16px;
    min-height: 16px;
}

.danger-btn {
    background: #2a0a0a;
    border: 1px solid #ff7800;
    color: #ff7800;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
}

.danger-btn:hover {
    background: #ff7800;
    color: white;
}

combobox {
    background: #0f0f1a;
    color: #ffffff;
    border: 1px solid #2a2a40;
    border-radius: 4px;
}

checkbutton label {
    color: #666688;
    font-size: 12px;
}

checkbutton:checked label {
    color: #ffaa33;
}

.setting-row {
    padding: 4px 0;
}

.setting-label {
    font-size: 13px;
    color: #ccccdd;
}

.setting-desc {
    font-size: 11px;
    color: #555566;
}

.color-preview {
    border: 1px solid #2a2a40;
    border-radius: 6px;
}

scrolledwindow scrollbar {
    background: transparent;
}
scrolledwindow scrollbar slider {
    background: #2a2a40;
    border-radius: 4px;
    min-width: 6px;
}
scrolledwindow scrollbar slider:hover {
    background: #3a3a55;
}
"""


def set_status(status_type, message):
    """Update status bar; must be called from the GUI thread."""
    dot = app_state["status_dot"]
    label = app_state["status_label"]

    dot.get_style_context().remove_class("status-running")
    dot.get_style_context().remove_class("status-ok")
    dot.get_style_context().remove_class("status-error")
    dot.get_style_context().add_class(f"status-{status_type}")

    label.set_text(message)


def run_rivalcfg(args, on_done=None):
    """Run rivalcfg command in a background thread."""
    def target():
        GLib.idle_add(set_status, "running", _("Processing..."))
        try:
            cmd = [RIVALCFG_BIN]
            if app_state.get("no_save"):
                cmd.append("--no-save")
            cmd.extend(args)
            logging.info("rivalcfg %s", " ".join(cmd))
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                err = result.stderr.strip() if result.stderr.strip() else _("Unknown error")
                logging.error("rivalcfg failed (exit %d): %s", result.returncode, err)
                GLib.idle_add(set_status, "error", f"✗ {_('Error')}: {err}")
                if on_done:
                    GLib.idle_add(on_done, False, err)
            else:
                out = result.stdout.strip()
                GLib.idle_add(set_status, "ok", "✓ " + _("Done"))
                if on_done:
                    GLib.idle_add(on_done, True, out)
        except FileNotFoundError:
            msg = _("rivalcfg is not installed. Install: pip install rivalcfg")
            logging.error("rivalcfg binary not found")
            GLib.idle_add(set_status, "error", f"✗ {_('Error')}: {msg}")
            if on_done:
                GLib.idle_add(on_done, False, msg)
        except subprocess.TimeoutExpired:
            msg = _("Timeout (10s)")
            logging.error("rivalcfg command timed out: %s", args)
            GLib.idle_add(set_status, "error", f"✗ {_('Error')}: {msg}")
            if on_done:
                GLib.idle_add(on_done, False, msg)
        except Exception as e:
            msg = f"{_('Unexpected error')}: {e}"
            logging.error("Unexpected error in rivalcfg: %s", e, exc_info=True)
            GLib.idle_add(set_status, "error", f"✗ {_('Error')}: {msg}")
            if on_done:
                GLib.idle_add(on_done, False, msg)

    threading.Thread(target=target, daemon=True).start()


def rgba_to_hex(rgba):
    """Convert Gdk.RGBA to lowercase hex string without #."""
    r = int(rgba.red * 255)
    g = int(rgba.green * 255)
    b = int(rgba.blue * 255)
    return f"{r:02x}{g:02x}{b:02x}"


def _x11_to_linux_keycode(x11_kc):
    """Convert X11 keycode to Linux input keycode using display min_keycode offset."""
    if not X11_AVAILABLE:
        return x11_kc
    try:
        from Xlib import display as xd
        d = xd.Display()
        try:
            min_kc = d.display.info.min_keycode
            return x11_kc - min_kc
        finally:
            d.close()
    except Exception:
        pass
    return x11_kc


def _find_keyboard_device():
    """Find the first physical keyboard input device path.
    Prefers 1.0 (main keyboard) over 1.1 (media keys) interface.
    """
    from glob import glob
    paths = sorted(glob("/dev/input/by-path/*-event-kbd"))
    if paths:
        one_point_zero = [p for p in paths if ":1.0-event-kbd" in p]
        if one_point_zero:
            return one_point_zero[0]
        return paths[0]
    paths = sorted(glob("/dev/input/event*"))
    for p in paths:
        try:
            dev = evdev.InputDevice(p)
            caps = dev.capabilities()
            dev.close()
            if caps.get(evdev.ecodes.EV_KEY):
                return p
        except Exception:
            continue
    return None


def _find_mouse_device():
    """Find a physical mouse input device path.
    Prefers standalone mice over keyboard sub-interfaces.
    """
    from glob import glob
    import os
    paths = sorted(glob("/dev/input/by-path/*-event-mouse"))
    if paths:
        seen = set()
        uniq = []
        for p in paths:
            rp = os.path.realpath(p)
            if rp not in seen:
                seen.add(rp)
                uniq.append(p)
        if uniq:
            def iface_num(pa):
                base = pa.replace("-event-mouse", "")
                parts = base.rsplit(":", 1)
                if len(parts) > 1:
                    try:
                        return int(parts[-1].split(".")[-1])
                    except (ValueError, IndexError):
                        return 0
                return 0
            uniq.sort(key=iface_num)
            return uniq[0]
    paths = sorted(glob("/dev/input/event*"))
    for p in paths:
        try:
            dev = evdev.InputDevice(p)
            caps = dev.capabilities()
            dev.close()
            if evdev.ecodes.EV_KEY in caps:
                keys = set(caps[evdev.ecodes.EV_KEY])
                if evdev.ecodes.BTN_LEFT in keys and evdev.ecodes.KEY_A not in keys:
                    return p
        except Exception:
            continue
    return None


class MacroEngine:
    """Software auto-clicker engine using evdev event-based key detection."""

    def __init__(self):
        self.click_thread = None
        self.monitor_thread = None
        self.running = False
        self.active = False
        self._stop_event = threading.Event()
        self.mouse_ctrl = pynput_mouse.Controller()
        self._device_path = None
        self._device = None
        self._helper_proc = None
        self._toggle_listener_thread = None
        self._toggle_mouse_listener = None
        self._toggle_stop_event = threading.Event()

    def _helper_path(self):
        helper = os.path.join(SCRIPT_DIR, "evdev_helper")
        if os.path.exists(helper):
            return helper
        if IN_FLATPAK:
            candidate = "/app/lib/rivalcfg-gui/evdev_helper"
            if os.path.exists(candidate):
                return candidate
        return helper

    def _resolve_keycode(self, trigger_key):
        from Xlib import display as xd, XK
        name_map = {
            "enter": "Return", "tab": "Tab",
            "backspace": "BackSpace", "delete": "Delete",
            "insert": "Insert", "menu": "Menu", "pause": "Pause",
            "print_screen": "Print", "scroll_lock": "Scroll_Lock",
            "caps_lock": "Caps_Lock", "num_lock": "Num_Lock",
            "shift": "Shift_L", "ctrl": "Control_L", "alt": "Alt_L",
            "cmd": "Super_L", "super": "Super_L",
            "up": "Up", "down": "Down", "left": "Left", "right": "Right",
            "home": "Home", "end": "End",
            "page_up": "Page_Up", "page_down": "Page_Down",
            "escape": "Escape",
        }
        name = name_map.get(trigger_key)
        if not name:
            name = trigger_key.upper()
        ks = XK.string_to_keysym(name)
        if not ks:
            ks = XK.string_to_keysym(trigger_key)
        if not ks:
            return None
        disp = xd.Display()
        try:
            return disp.keysym_to_keycode(ks)
        finally:
            disp.close()

    def _ensure_device(self):
        if self._device is not None:
            return self._device
        if self._device_path is None:
            self._device_path = _find_keyboard_device()
        if self._device_path is None:
            return None
        try:
            self._device = evdev.InputDevice(self._device_path)
            return self._device
        except PermissionError:
            return None
        except Exception:
            self._device_path = None
            return None

    def _close_device(self):
        if self._helper_proc is not None:
            try:
                self._helper_proc.terminate()
            except Exception:
                pass
            self._helper_proc = None
        if self._device is not None:
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None

    def _ensure_helper_setup(self):
        """Ensure evdev_helper exists and is setuid root. Shows pkexec dialog if needed."""
        helper_path = self._helper_path()
        if not os.path.exists(helper_path):
            logging.error("evdev_helper binary not found")
            return False
        if IN_FLATPAK:
            return True
        st = os.stat(helper_path)
        if (st.st_mode & 0o4000) and (st.st_uid == 0):
            return True
        logging.info("Helper not setuid, trying pkexec setup...")
        GLib.idle_add(self._set_status_text, _("Setting up helper (enter password)..."))
        try:
            pkexec_cmd = ["flatpak-spawn", "--host", "pkexec"] if IN_FLATPAK else ["pkexec"]
            proc = subprocess.Popen(
                pkexec_cmd + ["sh", "-c",
                 f"chown root:root '{helper_path}' && chmod u+s '{helper_path}'"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            ret = proc.wait(timeout=60)
            if ret == 0:
                st = os.stat(helper_path)
                if (st.st_mode & 0o4000) and (st.st_uid == 0):
                    logging.info("Helper set up successfully via pkexec")
                    return True
            else:
                err = proc.stderr.read().decode().strip()
                logging.error(f"pkexec setup failed (exit={ret}): {err}")
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            logging.error("pkexec setup timed out")
        except Exception as e:
            logging.error(f"pkexec setup error: {e}")
        return False

    def _start_helper_monitor(self, dev_path, linux_kc, mode):
        if not self._ensure_helper_setup():
            GLib.idle_add(self._set_status_text, _("Helper setup failed"))
            return
        helper_path = self._helper_path()
        proc = None
        try:
            logging.info("Launching helper: %s --device %s --keycode %s",
                         helper_path, dev_path, linux_kc)
            proc = subprocess.Popen(
                [helper_path, "--device", dev_path,
                 "--keycode", str(linux_kc)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self._helper_proc = proc
            def read_stderr():
                for line in proc.stderr:
                    line = line.decode().strip()
                    if line:
                        logging.error(f"helper stderr: {line}")
            threading.Thread(target=read_stderr, daemon=True).start()
            for line in proc.stdout:
                if self._stop_event.is_set():
                    break
                try:
                    data = json.loads(line.decode().strip())
                    if data.get("key") == linux_kc:
                        if data.get("state") == "down":
                            if mode == "toggle":
                                self.active = not self.active
                            elif mode == "hold":
                                self.active = True
                            GLib.idle_add(self._update_status)
                        elif data.get("state") == "up":
                            if mode == "hold":
                                self.active = False
                                GLib.idle_add(self._update_status)
                except (json.JSONDecodeError, KeyError):
                    continue
        except Exception as e:
            logging.error(f"evdev helper error: {e}")
            GLib.idle_add(self._set_status_text, _("Helper error"))
        finally:
            if proc is not None:
                try:
                    proc.terminate()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=2)
                except Exception:
                    pass
            self._helper_proc = None
            self._close_device()

    def start(self, cps, trigger_key, mode, button):
        self.stop()
        self.running = True
        self._stop_event.clear()

        btn_map = {"left": pynput_mouse.Button.left,
                   "right": pynput_mouse.Button.right,
                   "middle": pynput_mouse.Button.middle}
        btn = btn_map.get(button, pynput_mouse.Button.left)
        interval = 1.0 / cps
        is_mouse_trigger = trigger_key.startswith("mouse_")

        if is_mouse_trigger:
            if not EVDEV_AVAILABLE:
                logging.error("evdev not available for mouse trigger monitoring")
                return
            mouse_kc_map = {
                "mouse_left": evdev.ecodes.BTN_LEFT,
                "mouse_right": evdev.ecodes.BTN_RIGHT,
                "mouse_middle": evdev.ecodes.BTN_MIDDLE,
                "mouse_x1": evdev.ecodes.BTN_SIDE,
                "mouse_x2": evdev.ecodes.BTN_EXTRA,
            }
            linux_kc = mouse_kc_map.get(trigger_key)
            if linux_kc is None:
                logging.error(f"Unknown mouse trigger key: {trigger_key}")
                return

            mouse_dev_path = _find_mouse_device()
            if mouse_dev_path is None:
                logging.error("No mouse evdev device found")
                GLib.idle_add(self._set_status_text, _("No mouse device"))
                return

            # On Wayland the compositor grabs evdev devices; use setuid helper.
            # On X11 try direct evdev first, fall back to helper on PermissionError.
            use_helper = bool(os.environ.get('WAYLAND_DISPLAY'))
            if not use_helper:
                try:
                    mouse_dev = evdev.InputDevice(mouse_dev_path)
                except PermissionError:
                    use_helper = True
                except Exception as e:
                    logging.error(f"Error opening mouse device: {e}")
                    GLib.idle_add(self._set_status_text, _("Mouse device error"))
                    return

            if use_helper:
                self.monitor_thread = threading.Thread(
                    target=self._start_helper_monitor,
                    args=(mouse_dev_path, linux_kc, mode), daemon=True
                )
                self.monitor_thread.start()
            else:
                def monitor_mouse(dev):
                    try:
                        import select
                        poll = select.poll()
                        poll.register(dev, select.POLLIN)
                        while not self._stop_event.is_set():
                            if not poll.poll(100):
                                continue
                            for event in dev.read():
                                if event.type == evdev.ecodes.EV_KEY:
                                    e = evdev.categorize(event)
                                    if e.scancode == linux_kc:
                                        if e.keystate == e.key_down:
                                            if mode == "toggle":
                                                self.active = not self.active
                                            elif mode == "hold":
                                                self.active = True
                                            GLib.idle_add(self._update_status)
                                        elif e.keystate == e.key_up:
                                            if mode == "hold":
                                                self.active = False
                                                GLib.idle_add(self._update_status)
                    except Exception as e:
                        logging.error(f"evdev mouse error: {e}")
                    finally:
                        try:
                            dev.close()
                        except Exception:
                            pass

                self.monitor_thread = threading.Thread(target=monitor_mouse, args=(mouse_dev,), daemon=True)
                self.monitor_thread.start()
        else:
            if not EVDEV_AVAILABLE:
                logging.error("evdev not available for keyboard monitoring")
                return
            if trigger_key.startswith("kc:"):
                parts = trigger_key.split(":", 2)
                linux_kc = int(parts[1])
            else:
                x11_kc = self._resolve_keycode(trigger_key)
                if x11_kc is None:
                    logging.error(f"Could not resolve keycode for '{trigger_key}'")
                    return
                from Xlib import display as xd
                d = xd.Display()
                try:
                    min_kc = d.display.info.min_keycode
                finally:
                    d.close()
                linux_kc = x11_kc - min_kc

            def monitor_direct(dev):
                try:
                    import select
                    poll = select.poll()
                    poll.register(dev, select.POLLIN)
                    while not self._stop_event.is_set():
                        if not poll.poll(100):
                            continue
                        for event in dev.read():
                            if event.type == evdev.ecodes.EV_KEY:
                                e = evdev.categorize(event)
                                if e.scancode == linux_kc:
                                    if e.keystate == e.key_down:
                                        if mode == "toggle":
                                            self.active = not self.active
                                        elif mode == "hold":
                                            self.active = True
                                        GLib.idle_add(self._update_status)
                                    elif e.keystate == e.key_up:
                                        if mode == "hold":
                                            self.active = False
                                            GLib.idle_add(self._update_status)
                except Exception as e:
                    logging.error(f"evdev direct error: {e}")
                finally:
                    self._close_device()

            dev = self._ensure_device()
            if dev is not None:
                self.monitor_thread = threading.Thread(
                    target=monitor_direct, args=(dev,), daemon=True
                )
                self.monitor_thread.start()
            elif self._device_path is not None:
                self.monitor_thread = threading.Thread(
                    target=self._start_helper_monitor,
                    args=(self._device_path, linux_kc, mode), daemon=True
                )
                self.monitor_thread.start()
            else:
                logging.error("No keyboard device found")
                GLib.idle_add(self._set_status_text, _("No keyboard device"))

        def click_loop():
            while not self._stop_event.is_set():
                if self.active:
                    self.mouse_ctrl.click(btn)
                self._stop_event.wait(interval)

        self.click_thread = threading.Thread(target=click_loop, daemon=True)
        self.click_thread.start()

    def stop(self):
        self.running = False
        self.active = False
        self._stop_event.set()
        if self._helper_proc is not None:
            try:
                self._helper_proc.terminate()
            except Exception:
                pass
            self._helper_proc = None
        if self.monitor_thread is not None:
            self.monitor_thread.join(timeout=2)
            self.monitor_thread = None
        if self.click_thread is not None:
            self.click_thread.join(timeout=2)
            self.click_thread = None
        self._close_device()
        GLib.idle_add(self._update_status)

    def _set_status_text(self, text):
        dot = app_state.get("macro_status_dot")
        label = app_state.get("macro_status_label")
        if dot and label:
            dot.get_style_context().remove_class("status-ok")
            dot.get_style_context().add_class("status-running")
            label.set_text(text)

    def _update_status(self):
        active = self.active
        dot = app_state.get("macro_status_dot")
        label = app_state.get("macro_status_label")
        if dot and label:
            if active:
                dot.get_style_context().remove_class("status-running")
                dot.get_style_context().add_class("status-ok")
                label.set_text(_("Macro running"))
            else:
                dot.get_style_context().remove_class("status-ok")
                dot.get_style_context().add_class("status-running")
                label.set_text(_("Macro stopped"))

    def start_toggle_listener(self, toggle_key, callback):
        self.stop_toggle_listener()
        if not toggle_key:
            return
        self._toggle_stop_event.clear()

        if toggle_key.startswith("kc:"):
            parts = toggle_key.split(":", 2)
            kc_part = parts[1]
            keycodes = [int(kc) for kc in kc_part.split(",")]

            def listen():
                if not EVDEV_AVAILABLE:
                    logging.error("evdev not available for toggle listener")
                    return
                dev_path = _find_keyboard_device()
                if dev_path is not None:
                    try:
                        dev = evdev.InputDevice(dev_path)
                    except PermissionError:
                        dev = None
                    except Exception:
                        dev = None
                    if dev is not None:
                        import select
                        poll = select.poll()
                        poll.register(dev, select.POLLIN)
                        if len(keycodes) == 1:
                            kc = keycodes[0]
                            while not self._toggle_stop_event.is_set():
                                if not poll.poll(100):
                                    continue
                                for event in dev.read():
                                    if event.type == evdev.ecodes.EV_KEY:
                                        e = evdev.categorize(event)
                                        if e.scancode == kc and e.keystate == e.key_down:
                                            GLib.idle_add(callback)
                        else:
                            pressed_set = set()
                            triggered = False
                            target = set(keycodes)
                            while not self._toggle_stop_event.is_set():
                                if not poll.poll(50):
                                    continue
                                for event in dev.read():
                                    if event.type == evdev.ecodes.EV_KEY:
                                        e = evdev.categorize(event)
                                        if e.scancode in keycodes:
                                            if e.keystate == e.key_down:
                                                pressed_set.add(e.scancode)
                                            elif e.keystate == e.key_up:
                                                pressed_set.discard(e.scancode)
                                                triggered = False
                                if pressed_set == target and not triggered:
                                    triggered = True
                                    GLib.idle_add(callback)
                        try:
                            dev.close()
                        except Exception:
                            pass
                else:
                    logging.error("No keyboard device for toggle listener")

            self._toggle_listener_thread = threading.Thread(target=listen, daemon=True)
            self._toggle_listener_thread.start()

        elif toggle_key.startswith("mouse_"):
            import pynput.mouse as pynput_mouse_global
            btn_map = {
                "mouse_left": pynput_mouse_global.Button.left,
                "mouse_right": pynput_mouse_global.Button.right,
                "mouse_middle": pynput_mouse_global.Button.middle,
                "mouse_x1": pynput_mouse_global.Button.button8,
                "mouse_x2": pynput_mouse_global.Button.button9,
            }
            mbtn = btn_map.get(toggle_key)
            if mbtn:
                def on_click(x, y, btn_pressed, pressed):
                    if btn_pressed == mbtn and pressed:
                        GLib.idle_add(callback)
                listener = pynput_mouse_global.Listener(on_click=on_click)
                listener.daemon = True
                listener.start()
                self._toggle_mouse_listener = listener

    def stop_toggle_listener(self):
        self._toggle_stop_event.set()
        if self._toggle_listener_thread is not None:
            self._toggle_listener_thread.join(timeout=2)
            self._toggle_listener_thread = None
        if hasattr(self, '_toggle_mouse_listener') and self._toggle_mouse_listener is not None:
            try:
                self._toggle_mouse_listener.stop()
            except Exception:
                pass
            self._toggle_mouse_listener = None


def create_dpi_page():
    """Create DPI settings page."""
    page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    page.set_margin_top(24)
    page.set_margin_bottom(24)
    page.set_margin_start(24)
    page.set_margin_end(24)

    title = Gtk.Label(label=_("DPI Settings"))
    title.get_style_context().add_class("page-title")
    title.set_halign(Gtk.Align.START)
    page.pack_start(title, False, False, 0)

    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    card.get_style_context().add_class("card")
    page.pack_start(card, True, True, 0)

    presets_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    card.pack_start(presets_box, False, False, 0)

    app_state["dpi_scales"] = []
    app_state["dpi_labels"] = []
    app_state["dpi_values"] = [800, 1600]

    assets_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets")
    trash_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
        os.path.join(assets_dir, "trash.svg"), 16, 16, True
    )

    add_btn = Gtk.Button(label="+ " + _("Add DPI"))
    add_btn.set_halign(Gtk.Align.START)

    def on_add_dpi(btn):
        if len(app_state["dpi_values"]) >= 5:
            return
        app_state["dpi_values"].append(800)
        rebuild_dpi_ui()
        if not app_state.get("_loading_profile") and app_state["settings"].get("auto_apply"):
            vals = app_state["dpi_values"]
            run_rivalcfg(["--sensitivity", ",".join(str(v) for v in vals)])

    add_btn.connect("clicked", on_add_dpi)
    card.pack_start(add_btn, False, False, 0)

    def rebuild_dpi_ui():
        for child in presets_box.get_children():
            presets_box.remove(child)
        app_state["dpi_scales"] = []
        app_state["dpi_labels"] = []

        for i, val in enumerate(app_state["dpi_values"]):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.set_margin_bottom(8)

            def on_delete_dpi(btn, idx=i):
                if len(app_state["dpi_values"]) <= 1:
                    return
                del app_state["dpi_values"][idx]
                rebuild_dpi_ui()
                if not app_state.get("_loading_profile") and app_state["settings"].get("auto_apply"):
                    vals = app_state["dpi_values"]
                    run_rivalcfg(["--sensitivity", ",".join(str(v) for v in vals)])

            trash_btn = Gtk.Button()
            trash_btn.set_image(Gtk.Image.new_from_pixbuf(trash_pixbuf))
            trash_btn.set_relief(Gtk.ReliefStyle.NONE)
            trash_btn.get_style_context().add_class("dpi-delete-btn")
            trash_btn.connect("clicked", on_delete_dpi)
            row.pack_start(trash_btn, False, False, 0)

            lbl = Gtk.Label(label=f"DPI {i + 1}")
            lbl.set_size_request(80, -1)
            lbl.set_halign(Gtk.Align.START)
            row.pack_start(lbl, False, False, 0)

            spin_btn = Gtk.SpinButton()
            spin_btn.set_range(200, 8500)
            spin_btn.set_increments(100, 100)
            spin_btn.set_digits(0)
            spin_btn.set_numeric(True)
            spin_btn.set_max_length(4)
            spin_btn.set_value(val)
            spin_btn.set_size_request(80, -1)
            spin_btn.set_halign(Gtk.Align.START)
            spin_btn.get_style_context().add_class("value-display")
            row.pack_start(spin_btn, False, False, 0)
            app_state["dpi_labels"].append(spin_btn)

            scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
            scale.set_range(200, 8500)
            scale.set_increments(100, 100)
            scale.set_draw_value(False)
            scale.set_digits(0)
            scale.set_value(val)
            scale.set_hexpand(True)

            _updating = [False]

            def on_dpi_changed(sc, idx=i, sb=spin_btn, guard=_updating):
                if guard[0]:
                    return
                guard[0] = True
                v = int(sc.get_value())
                sb.set_value(v)
                guard[0] = False
                app_state["dpi_values"][idx] = v
                if not app_state.get("_loading_profile") and app_state["settings"].get("auto_apply"):
                    vals = app_state["dpi_values"]
                    arg = ",".join(str(val) for val in vals)
                    run_rivalcfg(["--sensitivity", arg])

            def on_spin_changed(sb, idx=i, sc=scale, guard=_updating):
                if guard[0]:
                    return
                guard[0] = True
                v = int(sb.get_value())
                sc.set_value(v)
                guard[0] = False
                app_state["dpi_values"][idx] = v
                if not app_state.get("_loading_profile") and app_state["settings"].get("auto_apply"):
                    vals = app_state["dpi_values"]
                    arg = ",".join(str(val) for val in vals)
                    run_rivalcfg(["--sensitivity", arg])

            scale.connect("value-changed", on_dpi_changed)
            spin_btn.connect("value-changed", on_spin_changed)
            row.pack_start(scale, True, True, 0)
            app_state["dpi_scales"].append(scale)

            presets_box.pack_start(row, False, False, 0)

        presets_box.show_all()
        add_btn.set_visible(len(app_state["dpi_values"]) < 5)

    app_state["_rebuild_dpi_ui"] = rebuild_dpi_ui
    rebuild_dpi_ui()

    btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    btn_row.set_halign(Gtk.Align.START)

    apply_btn = Gtk.Button(label=_("APPLY"))
    apply_btn.get_style_context().add_class("apply-btn")

    def on_apply_dpi(btn):
        save_active_profile()
        vals = app_state["dpi_values"]
        arg = ",".join(str(v) for v in vals)
        run_rivalcfg(["--sensitivity", arg])

    apply_btn.connect("clicked", on_apply_dpi)
    btn_row.pack_start(apply_btn, False, False, 0)

    reset_btn = Gtk.Button(label=_("RESET"))
    reset_btn.get_style_context().add_class("reset-btn")

    def on_reset_dpi(btn):
        app_state["dpi_values"] = [800, 1600]
        rebuild_dpi_ui()

    reset_btn.connect("clicked", on_reset_dpi)
    btn_row.pack_start(reset_btn, False, False, 0)

    card.pack_start(btn_row, False, False, 0)

    return page


def create_polling_page():
    """Create Polling Rate page."""
    page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    page.set_margin_top(24)
    page.set_margin_bottom(24)
    page.set_margin_start(24)
    page.set_margin_end(24)

    title = Gtk.Label(label=_("Polling Rate"))
    title.get_style_context().add_class("page-title")
    title.set_halign(Gtk.Align.START)
    page.pack_start(title, False, False, 0)

    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    card.get_style_context().add_class("card")
    page.pack_start(card, True, True, 0)

    rates = [125, 250, 500, 1000]
    app_state["polling_hz"] = 1000
    app_state["polling_radios"] = {}
    group = None

    radio_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

    for hz in rates:
        if group is None:
            rb = Gtk.RadioButton(label=_("{} Hz").format(hz))
            group = rb
            rb.set_active(hz == 1000)
        else:
            rb = Gtk.RadioButton(label=_("{} Hz").format(hz), group=group)
            rb.set_active(hz == 1000)

        app_state["polling_radios"][hz] = rb

        def on_polling_toggled(button, val=hz):
            if button.get_active():
                app_state["polling_hz"] = val
                ms = 1000.0 / val
                app_state["polling_display"].set_text(_("{} Hz → {} ms").format(val, f"{ms:.1f}"))
                if not app_state.get("_loading_profile") and app_state["settings"].get("auto_apply"):
                    run_rivalcfg(["--polling-rate", str(val)])

        rb.connect("toggled", on_polling_toggled)
        radio_box.pack_start(rb, False, False, 0)

    card.pack_start(radio_box, False, False, 0)

    display = Gtk.Label(label=_("{} Hz → {} ms").format("1000", "1.0"))
    display.get_style_context().add_class("value-display")
    display.set_halign(Gtk.Align.START)
    card.pack_start(display, False, False, 0)
    app_state["polling_display"] = display

    apply_btn = Gtk.Button(label=_("APPLY"))
    apply_btn.get_style_context().add_class("apply-btn")
    apply_btn.set_halign(Gtk.Align.START)

    def on_apply_polling(btn):
        save_active_profile()
        run_rivalcfg(["--polling-rate", str(app_state["polling_hz"])])

    apply_btn.connect("clicked", on_apply_polling)
    card.pack_start(apply_btn, False, False, 0)

    return page


def create_rgb_page():
    """Create RGB Lighting page."""
    page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    page.set_margin_top(24)
    page.set_margin_bottom(24)
    page.set_margin_start(24)
    page.set_margin_end(24)

    title = Gtk.Label(label=_("RGB Lighting"))
    title.get_style_context().add_class("page-title")
    title.set_halign(Gtk.Align.START)
    page.pack_start(title, False, False, 0)

    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    card.get_style_context().add_class("card")
    page.pack_start(card, True, True, 0)

    colors_title = Gtk.Label(label=_("COLORS"))
    colors_title.get_style_context().add_class("card-title")
    colors_title.set_halign(Gtk.Align.START)
    card.pack_start(colors_title, False, False, 0)

    app_state["z1_hex"] = "ff6600"
    app_state["z2_hex"] = "ff6600"
    app_state["z3_hex"] = "ff6600"
    app_state["z4_hex"] = "ff6600"
    app_state["color_buttons"] = {}
    app_state["color_previews"] = {}

    def make_color_row(label_text, default_hex, key):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.set_margin_top(4)

        lbl = Gtk.Label(label=label_text)
        lbl.set_size_request(100, -1)
        lbl.set_halign(Gtk.Align.START)
        row.pack_start(lbl, False, False, 0)

        rgba = Gdk.RGBA()
        rgba.parse(f"#{default_hex}")

        color_btn = Gtk.ColorButton()
        color_btn.set_rgba(rgba)
        color_btn.set_size_request(60, -1)
        row.pack_start(color_btn, False, False, 0)
        app_state["color_buttons"][key] = color_btn

        preview = Gtk.DrawingArea()
        preview.set_size_request(40, 24)
        preview.get_style_context().add_class("card")
        row.pack_start(preview, False, False, 0)
        app_state["color_previews"][key] = preview

        def on_draw(widget, cr):
            h = app_state[key]
            r = int(h[0:2], 16) / 255.0
            g = int(h[2:4], 16) / 255.0
            b = int(h[4:6], 16) / 255.0
            cr.set_source_rgb(r, g, b)
            cr.paint()
            return False

        preview.connect("draw", on_draw)

        def on_color_set(button):
            col = button.get_rgba()
            app_state[key] = rgba_to_hex(col)
            preview.queue_draw()
            if not app_state.get("_loading_profile") and app_state["settings"].get("auto_apply"):
                color_map = {
                    "z1_hex": "--strip-top-color",
                    "z2_hex": "--strip-middle-color",
                    "z3_hex": "--strip-bottom-color",
                    "z4_hex": "--logo-color",
                }
                if key in color_map:
                    run_rivalcfg([color_map[key], app_state[key]])

        color_btn.connect("color-set", on_color_set)
        return row

    card.pack_start(make_color_row(_("Z1 - Top Strip"), "ff6600", "z1_hex"), False, False, 0)
    card.pack_start(make_color_row(_("Z2 - Middle Strip"), "ff6600", "z2_hex"), False, False, 0)
    card.pack_start(make_color_row(_("Z3 - Bottom Strip"), "ff6600", "z3_hex"), False, False, 0)
    card.pack_start(make_color_row(_("Z4 - Logo"), "ff6600", "z4_hex"), False, False, 0)

    effect_title = Gtk.Label(label=_("EFFECT"))
    effect_title.get_style_context().add_class("card-title")
    effect_title.set_halign(Gtk.Align.START)
    effect_title.set_margin_top(12)
    card.pack_start(effect_title, False, False, 0)

    effects = [
        (_("Steady"), "steady"),
        (_("Breath"), "breath"),
        (_("Breath (Slow)"), "breath-slow"),
        (_("Breath (Fast)"), "breath-fast"),
        (_("Rainbow Shift"), "rainbow-shift"),
        (_("Rainbow Breath"), "rainbow-breath"),
        (_("Disco"), "disco"),
    ]
    app_state["selected_effect"] = "steady"
    app_state["effect_radios"] = {}
    eff_group = None

    eff_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

    for name, value in effects:
        if eff_group is None:
            rb = Gtk.RadioButton(label=name)
            eff_group = rb
            rb.set_active(value == "steady")
        else:
            rb = Gtk.RadioButton(label=name, group=eff_group)
            rb.set_active(value == "steady")

        app_state["effect_radios"][value] = rb

        def on_effect_toggled(button, val=value):
            if button.get_active():
                app_state["selected_effect"] = val
                if not app_state.get("_loading_profile") and app_state["settings"].get("auto_apply"):
                    run_rivalcfg(["--light-effect", val])

        rb.connect("toggled", on_effect_toggled)
        eff_box.pack_start(rb, False, False, 0)

    card.pack_start(eff_box, False, False, 0)

    apply_btn = Gtk.Button(label=_("APPLY"))
    apply_btn.get_style_context().add_class("apply-btn")
    apply_btn.set_halign(Gtk.Align.START)
    apply_btn.set_margin_top(8)

    def on_apply_rgb(btn):
        save_active_profile()
        z1 = app_state["z1_hex"]
        z2 = app_state["z2_hex"]
        z3 = app_state["z3_hex"]
        z4 = app_state["z4_hex"]
        effect = app_state["selected_effect"]

        def after_z1(success, msg):
            if not success:
                return
            run_rivalcfg(["--strip-middle-color", z2], after_z2)

        def after_z2(success, msg):
            if not success:
                return
            run_rivalcfg(["--strip-bottom-color", z3], after_z3)

        def after_z3(success, msg):
            if not success:
                return
            run_rivalcfg(["--logo-color", z4], after_z4)

        def after_z4(success, msg):
            if not success:
                return
            run_rivalcfg(["--light-effect", effect])

        run_rivalcfg(["--strip-top-color", z1], after_z1)

    apply_btn.connect("clicked", on_apply_rgb)
    card.pack_start(apply_btn, False, False, 0)

    return page


def create_buttons_page():
    """Create Button Mapping page."""
    page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    page.set_margin_top(24)
    page.set_margin_bottom(24)
    page.set_margin_start(24)
    page.set_margin_end(24)

    title = Gtk.Label(label=_("Button Mapping"))
    title.get_style_context().add_class("page-title")
    title.set_halign(Gtk.Align.START)
    page.pack_start(title, False, False, 0)

    button_options = [
        ("button1", _("Button 1")),
        ("button2", _("Button 2")),
        ("button3", _("Button 3")),
        ("button4", _("Button 4")),
        ("button5", _("Button 5")),
        ("button6", _("Button 6")),
        ("dpi", _("DPI Cycle")),
        ("scrollup", _("Scroll Up")),
        ("scrolldown", _("Scroll Down")),
        ("disable", _("Disable")),
    ]

    defaults = {
        "button1": "button1",
        "button2": "button2",
        "button3": "button3",
        "button4": "button4",
        "button5": "button5",
        "button6": "dpi",
        "scrollup": "scrollup",
        "scrolldown": "scrolldown",
    }

    app_state["button_mapping"] = dict(defaults)

    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    card.get_style_context().add_class("card")
    page.pack_start(card, True, True, 0)

    img_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets", "rival3.png")

    overlay = Gtk.Overlay()
    overlay.set_hexpand(True)
    overlay.set_vexpand(True)

    if os.path.exists(img_path):
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(img_path, 400, 400, True)
        image_widget = Gtk.Image.new_from_pixbuf(pixbuf)
        image_widget.set_halign(Gtk.Align.CENTER)
        image_widget.set_valign(Gtk.Align.CENTER)
        overlay.add(image_widget)
    else:
        fallback = Gtk.Label(label=_("rival3.png not found."))
        overlay.add(fallback)

    lines_area = Gtk.DrawingArea()
    lines_area.set_hexpand(True)
    lines_area.set_vexpand(True)
    lines_area.set_halign(Gtk.Align.FILL)
    lines_area.set_valign(Gtk.Align.FILL)
    lines_area.set_app_paintable(True)

    box_hit_areas = {}

    def draw_lines(widget, cr):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()

        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()

        img_w = 400
        img_h = 400
        img_x = (w - img_w) / 2
        img_y = (h - img_h) / 2

        btn_positions = {
            "button1": (img_x + 156, img_y + 125),
            "button2": (img_x + 244, img_y + 125),
            "button3": (img_x + 200, img_y + 123),
            "button4": (img_x + 144, img_y + 231),
            "button5": (img_x + 144, img_y + 194),
            "button6": (img_x + 200, img_y + 175),
            "scrollup": (img_x + 200, img_y + 113),
            "scrolldown": (img_x + 200, img_y + 138),
        }

        btn_display_names = {
            "button1": _("Left Click"),
            "button2": _("Right Click"),
            "button3": _("Middle"),
            "button4": _("Back"),
            "button5": _("Forward"),
            "button6": _("DPI"),
            "scrollup": _("Scroll Up"),
            "scrolldown": _("Scroll Down"),
        }

        lw = 130
        lh = 24

        # Middle - mouse'un tam üst ortasında
        lx_middle = img_x + 200 - lw // 2
        ly_middle = img_y - 10

        # Scroll Up - Middle'nin solunda, hafif aşağıda
        lx_scrollup = lx_middle - 150
        ly_scrollup = ly_middle + 38

        # Scroll Down - Middle'nin sağında, hafif aşağıda
        lx_scrolldown = lx_middle + 150
        ly_scrolldown = ly_middle + 70

        # Her kutunun x pozisyonu
        label_xs = {
            "button3": lx_middle,
            "scrollup": lx_scrollup,
            "scrolldown": lx_scrolldown,
            "button1": img_x - lw,
            "button5": img_x - lw,
            "button4": img_x - lw,
            "button2": img_x + img_w,
            "button6": img_x + img_w,
        }

        label_ys = {
            "button3": ly_middle,
            "scrollup": ly_scrollup,
            "scrolldown": ly_scrolldown,
            "button1": img_y + 100,
            "button5": img_y + 165,
            "button4": img_y + 225,
            "button6": img_y + 165,
            "button2": img_y + 100,
        }

        box_hit_areas.clear()

        # Çizgi hedef kenarları
        line_targets = {
            "button3": "bottom",
            "scrollup": "bottom",
            "scrolldown": "bottom",
            "button1": "right",
            "button5": "right",
            "button4": "right",
            "button2": "left",
            "button6": "left",
        }

        for btn_name, (bx, by) in btn_positions.items():
            assigned = app_state["button_mapping"].get(btn_name, btn_name)
            display_name = btn_display_names[btn_name]
            label_text = f"{display_name}: {assigned}"
            ly = label_ys[btn_name]
            cx = label_xs[btn_name]

            box_hit_areas[btn_name] = (cx, ly, lw, lh)

            # Çizgi hedef noktasını hesapla
            target = line_targets.get(btn_name, "left")
            if target == "bottom":
                tx, ty = cx + lw / 2, ly + lh
            elif target == "right":
                tx, ty = cx + lw, ly + lh / 2
            else:  # left
                tx, ty = cx, ly + lh / 2

            cr.set_source_rgba(0.4, 0.6, 1.0, 0.7)
            cr.set_line_width(1.2)
            cr.move_to(bx, by)
            cr.line_to(tx, ty)
            cr.stroke()

            #cr.set_source_rgb(0.4, 0.6, 1.0)
            #cr.arc(bx, by, 4, 0, 2 * math.pi)
            #cr.fill()

            cr.set_source_rgba(0.08, 0.14, 0.26, 0.95)
            cr.rectangle(cx, ly, lw, lh)
            cr.fill()
            cr.set_source_rgb(0.25, 0.40, 0.70)
            cr.set_line_width(1)
            cr.rectangle(cx, ly, lw, lh)
            cr.stroke()

            cr.set_source_rgb(1, 1, 1)
            cr.select_font_face("monospace", 0, 0)
            cr.set_font_size(9)
            te = cr.text_extents(label_text)
            cr.move_to(cx + (lw - te[2]) / 2, ly + lh / 2 + te[3] / 2)
            cr.show_text(label_text)

        return False

    lines_area.connect("draw", draw_lines)

    popover = Gtk.Popover.new(lines_area)
    popover.set_modal(True)

    popover_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    popover_box.set_margin_start(6)
    popover_box.set_margin_end(6)
    popover_box.set_margin_top(6)
    popover_box.set_margin_bottom(6)

    current_popover_btn = [None]

    def apply_assignment(btn_name, value):
        app_state["button_mapping"][btn_name] = value
        app_state["redraw_buttons"]()
        popover.popdown()
        if app_state["settings"].get("auto_apply"):
            m = app_state["button_mapping"]
            arg = (
                f"buttons(button1={m['button1']}; button2={m['button2']}; "
                f"button3={m['button3']}; button4={m['button4']}; "
                f"button5={m['button5']}; button6={m['button6']}; "
                f"scrollup={m['scrollup']}; scrolldown={m['scrolldown']}; "
                f"layout=qwerty)"
            )
            run_rivalcfg(["--buttons", arg])

    for opt_val, opt_label in button_options:
        btn = Gtk.Button(label=opt_label)
        btn.set_halign(Gtk.Align.FILL)
        btn.connect("clicked", lambda w, o=opt_val: apply_assignment(current_popover_btn[0], o) if current_popover_btn[0] else None)
        popover_box.pack_start(btn, False, False, 0)

    popover.add(popover_box)
    popover_box.show_all()
    popover.hide()

    def on_button_press(widget, event):
        x, y = event.x, event.y
        for btn_name, (bx, by, bw, bh) in box_hit_areas.items():
            if bx <= x <= bx + bw and by <= y <= by + bh:
                current_popover_btn[0] = btn_name
                rect = Gdk.Rectangle()
                rect.x = int(bx)
                rect.y = int(by)
                rect.width = int(bw)
                rect.height = int(bh)
                popover.set_pointing_to(rect)
                popover.set_position(Gtk.PositionType.LEFT)
                popover.popup()
                return True
        return False

    lines_area.connect("button-press-event", on_button_press)
    lines_area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)

    overlay.connect("button-press-event", lambda w, e: popover.popdown() if popover.is_visible() else False)
    overlay.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)

    win = app_state["window"]
    win.connect("button-press-event", lambda w, e: popover.popdown() if popover.is_visible() else False)

    overlay.add_overlay(lines_area)
    app_state["redraw_buttons"] = lambda: lines_area.queue_draw()

    card.pack_start(overlay, True, True, 0)

    # --- MACRO SETTINGS ---
    macro_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    macro_card.get_style_context().add_class("card")
    macro_card.set_margin_top(16)

    macro_title = Gtk.Label(label=_("MACRO / AUTO CLICKER"))
    macro_title.get_style_context().add_class("card-title")
    macro_title.set_halign(Gtk.Align.START)
    macro_card.pack_start(macro_title, False, False, 0)

    enable_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
    enable_row.get_style_context().add_class("setting-row")

    enable_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    enable_text.set_hexpand(True)
    enable_label = Gtk.Label(label=_("Macro / Auto Clicker"))
    enable_label.get_style_context().add_class("setting-label")
    enable_label.set_halign(Gtk.Align.START)
    enable_desc = Gtk.Label(label=_("Enable auto-click macro"))
    enable_desc.get_style_context().add_class("setting-desc")
    enable_desc.set_halign(Gtk.Align.START)
    enable_text.pack_start(enable_label, False, False, 0)
    enable_text.pack_start(enable_desc, False, False, 0)
    enable_row.pack_start(enable_text, True, True, 0)

    current_toggle = app_state["settings"].get("macro_toggle_key", "")
    if current_toggle.startswith("kc:"):
        parts = current_toggle.split(":", 2)
        kc_part = parts[1]
        name_part = parts[2] if len(parts) > 2 else ""
        display_names = {
            "enter": "Enter", "space": "Space", "tab": "Tab",
            "backspace": "Backspace", "delete": "Delete",
            "shift": "Shift", "ctrl": "Ctrl", "alt": "Alt", "cmd": "Super",
            "up": "↑ Up", "down": "↓ Down", "left": "← Left", "right": "→ Right",
            "home": "Home", "end": "End", "page_up": "Pg Up", "page_down": "Pg Dn",
            "caps_lock": "Caps Lock", "num_lock": "Num Lock",
            "insert": "Insert", "menu": "Menu", "pause": "Pause",
            "print_screen": "PrtSc", "scroll_lock": "Scroll Lock",
        }
        if "+" in name_part:
            names = name_part.split("+")
            toggle_init = " + ".join(display_names.get(n, n.upper()) for n in names)
        elif name_part:
            toggle_init = display_names.get(name_part, name_part.upper())
        else:
            toggle_init = f"Key {kc_part}"
    elif current_toggle.startswith("mouse_"):
        toggle_init = current_toggle.replace("mouse_", "Mouse ").title()
    elif current_toggle:
        toggle_init = current_toggle.upper()
    else:
        toggle_init = _("Not set")
    toggle_display = Gtk.Label(label=_("Shortcut: ") + toggle_init)
    toggle_display.get_style_context().add_class("setting-label")
    toggle_display.set_margin_end(4)
    enable_row.pack_start(toggle_display, False, False, 0)

    toggle_set_btn = Gtk.Button(label=_("Set Key..."))
    toggle_set_btn.set_size_request(80, -1)
    enable_row.pack_start(toggle_set_btn, False, False, 0)

    macro_switch = Gtk.Switch()
    macro_switch.set_active(app_state["settings"].get("macro_enabled", False))
    enable_row.pack_start(macro_switch, False, False, 0)
    macro_card.pack_start(enable_row, False, False, 0)

    macro_settings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    macro_settings_box.set_visible(app_state["settings"].get("macro_enabled", False))

    if not EVDEV_AVAILABLE:
        evdev_warn = Gtk.Label(label=_("evdev module not installed.\nInstall: python-evdev"))
        evdev_warn.get_style_context().add_class("setting-desc")
        evdev_warn.set_halign(Gtk.Align.START)
        evdev_warn.set_margin_bottom(8)
        macro_settings_box.pack_start(evdev_warn, False, False, 0)

    cps_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    cps_row.get_style_context().add_class("setting-row")
    cps_label = Gtk.Label(label=_("Clicks per second:"))
    cps_label.set_halign(Gtk.Align.START)
    cps_label.set_size_request(150, -1)
    cps_adjustment = Gtk.Adjustment(
        value=app_state["settings"].get("macro_cps", 10), lower=1, upper=50, step_increment=1
    )
    cps_spin = Gtk.SpinButton(adjustment=cps_adjustment, climb_rate=1, digits=0)
    cps_spin.set_size_request(80, -1)
    cps_row.pack_start(cps_label, False, False, 0)
    cps_row.pack_end(cps_spin, False, False, 0)
    macro_settings_box.pack_start(cps_row, False, False, 0)

    current_trigger = app_state["settings"].get("macro_trigger_key", "f6")
    if current_trigger.startswith("kc:"):
        parts = current_trigger.split(":", 2)
        key_name = parts[2] if len(parts) > 2 else ""
        display_init = key_name.upper() if key_name else f"Key {parts[1]}"
    else:
        display_init = current_trigger.upper()
    key_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    key_row.get_style_context().add_class("setting-row")
    key_label = Gtk.Label(label=_("Trigger key:"))
    key_label.set_halign(Gtk.Align.START)
    key_label.set_size_request(150, -1)
    key_display = Gtk.Label(label=display_init)
    key_display.set_halign(Gtk.Align.START)
    key_display.set_size_request(80, -1)
    key_display.get_style_context().add_class("setting-label")
    key_set_btn = Gtk.Button(label=_("Set Key..."))
    key_set_btn.set_size_request(90, -1)
    key_row.pack_start(key_label, False, False, 0)
    key_row.pack_end(key_set_btn, False, False, 0)
    key_row.pack_end(key_display, False, False, 0)
    macro_settings_box.pack_start(key_row, False, False, 0)

    mode_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    mode_row.get_style_context().add_class("setting-row")
    mode_label = Gtk.Label(label=_("Mode:"))
    mode_label.set_halign(Gtk.Align.START)
    mode_label.set_size_request(150, -1)
    mode_combo = Gtk.ComboBoxText()
    mode_combo.append_text(_("Toggle (press once to start/stop)"))
    mode_combo.append_text(_("Hold (click while held)"))
    current_mode = app_state["settings"].get("macro_mode", "toggle")
    mode_combo.set_active(0 if current_mode == "toggle" else 1)
    mode_row.pack_start(mode_label, False, False, 0)
    mode_row.pack_end(mode_combo, False, False, 0)
    macro_settings_box.pack_start(mode_row, False, False, 0)

    btn_macro_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    btn_macro_row.get_style_context().add_class("setting-row")
    btn_macro_label = Gtk.Label(label=_("Mouse button:"))
    btn_macro_label.set_halign(Gtk.Align.START)
    btn_macro_label.set_size_request(150, -1)
    btn_macro_combo = Gtk.ComboBoxText()
    btn_macro_combo.append_text(_("Left Click"))
    btn_macro_combo.append_text(_("Right Click"))
    btn_macro_combo.append_text(_("Middle Click"))
    current_btn = app_state["settings"].get("macro_button", "left")
    btn_values = ["left", "right", "middle"]
    btn_macro_combo.set_active(btn_values.index(current_btn) if current_btn in btn_values else 0)
    btn_macro_row.pack_start(btn_macro_label, False, False, 0)
    btn_macro_row.pack_end(btn_macro_combo, False, False, 0)
    macro_settings_box.pack_start(btn_macro_row, False, False, 0)

    status_macro_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    status_macro_row.set_margin_top(8)
    macro_status_dot = Gtk.Label(label="●")
    macro_status_dot.get_style_context().add_class("status-running")
    macro_status_label = Gtk.Label(label=_("Macro stopped"))
    macro_status_label.get_style_context().add_class("setting-desc")
    status_macro_row.pack_start(macro_status_dot, False, False, 0)
    status_macro_row.pack_start(macro_status_label, False, False, 0)
    macro_settings_box.pack_start(status_macro_row, False, False, 0)

    app_state["macro_switch"] = macro_switch
    app_state["macro_toggle_display"] = toggle_display
    app_state["macro_toggle_set_btn"] = toggle_set_btn
    app_state["macro_cps_spin"] = cps_spin
    app_state["macro_key_display"] = key_display
    app_state["macro_mode_combo"] = mode_combo
    app_state["macro_btn_combo"] = btn_macro_combo
    app_state["macro_settings_box"] = macro_settings_box
    app_state["macro_status_dot"] = macro_status_dot
    app_state["macro_status_label"] = macro_status_label
    app_state["macro_card"] = macro_card

    macro_card.pack_start(macro_settings_box, False, False, 0)
    card.pack_start(macro_card, False, False, 0)

    def restart_macro():
        if app_state.get("_loading_profile"):
            return
        if not PYNPUT_AVAILABLE:
            macro_status_label.set_text(_("pynput not installed"))
            return
        engine = app_state.get("macro_engine")
        if engine:
            engine.stop()
        enabled = macro_switch.get_active()
        if enabled:
            cps = int(cps_spin.get_value())
            mode_idx = mode_combo.get_active()
            mode = "toggle" if mode_idx == 0 else "hold"
            btn_idx = btn_macro_combo.get_active()
            btn_val = btn_values[btn_idx] if 0 <= btn_idx < len(btn_values) else "left"
            key_val = app_state["settings"].get("macro_trigger_key", "f6")
            engine = app_state.get("macro_engine")
            if engine:
                engine.start(cps, key_val, mode, btn_val)

    app_state["restart_macro"] = restart_macro

    def on_macro_switch(s, *a):
        val = macro_switch.get_active()
        app_state["settings"]["macro_enabled"] = val
        macro_settings_box.set_visible(val)
        save_settings()
        restart_macro()

    macro_switch.connect("notify::active", on_macro_switch)

    def on_cps_changed(s):
        app_state["settings"]["macro_cps"] = int(s.get_value())
        save_settings()
        restart_macro()

    cps_spin.connect("value-changed", on_cps_changed)

    def on_mode_changed(combo):
        idx = combo.get_active()
        app_state["settings"]["macro_mode"] = "toggle" if idx == 0 else "hold"
        save_settings()
        restart_macro()

    mode_combo.connect("changed", on_mode_changed)

    def on_btn_macro_changed(combo):
        idx = combo.get_active()
        if 0 <= idx < len(btn_values):
            app_state["settings"]["macro_button"] = btn_values[idx]
            save_settings()
            restart_macro()

    btn_macro_combo.connect("changed", on_btn_macro_changed)

    def on_set_key(btn):
        if not PYNPUT_AVAILABLE:
            return
        dialog = Gtk.Dialog(
            title=_("Set Trigger Key"),
            parent=app_state["window"],
            flags=Gtk.DialogFlags.MODAL,
        )
        dialog.set_default_size(350, 150)
        box = dialog.get_content_area()
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        lbl = Gtk.Label(label=_("Press any key or click a mouse button...\nESC to cancel"))
        lbl.set_halign(Gtk.Align.CENTER)
        box.pack_start(lbl, True, True, 0)
        dialog.show_all()

        captured = [None]
        key_normalize = {
            "return": "enter", "kp_enter": "enter",
            "shift_l": "shift", "shift_r": "shift",
            "control_l": "ctrl", "control_r": "ctrl",
            "alt_l": "alt", "alt_r": "alt",
            "super_l": "cmd", "super_r": "cmd",
        }

        def on_key(widget, event):
            keyval = event.keyval
            keyname = Gdk.keyval_name(keyval)
            hw_kc = event.hardware_keycode
            linux_kc = _x11_to_linux_keycode(hw_kc)
            if keyname:
                kn = keyname.lower()
                if kn == 'escape':
                    captured[0] = '__cancel__'
                else:
                    normalized = key_normalize.get(kn, kn)
                    captured[0] = f"kc:{linux_kc}:{normalized}"
            else:
                captured[0] = f"kc:{linux_kc}:key_{keyval}"
            dialog.response(1)
            return True

        dialog.connect("key-press-event", on_key)

        def on_mouse_btn(widget, event):
            btn = event.button
            btn_map = {1: "mouse_left", 2: "mouse_middle", 3: "mouse_right",
                       8: "mouse_x1", 9: "mouse_x2"}
            if btn in btn_map:
                captured[0] = btn_map[btn]
                dialog.response(1)
            return True

        dialog.connect("button-press-event", on_mouse_btn)

        dialog.run()
        dialog.destroy()

        if captured[0] and captured[0] != '__cancel__':
            key_val = captured[0]
            app_state["settings"]["macro_trigger_key"] = key_val
            display_names = {
                "enter": "Enter", "space": "Space", "tab": "Tab",
                "backspace": "Backspace", "delete": "Delete",
                "shift": "Shift", "ctrl": "Ctrl", "alt": "Alt", "cmd": "Super",
                "up": "↑ Up", "down": "↓ Down", "left": "← Left", "right": "→ Right",
                "home": "Home", "end": "End", "page_up": "Pg Up", "page_down": "Pg Dn",
                "caps_lock": "Caps Lock", "num_lock": "Num Lock",
                "insert": "Insert", "menu": "Menu", "pause": "Pause",
                "print_screen": "PrtSc", "scroll_lock": "Scroll Lock",
            }
            if key_val.startswith("kc:"):
                parts = key_val.split(":", 2)
                key_name = parts[2] if len(parts) > 2 else ""
                if key_name in display_names:
                    display = display_names[key_name]
                elif key_name:
                    display = key_name.upper()
                else:
                    display = f"Key {parts[1]}"
            elif key_val.startswith("mouse_"):
                btn_name = key_val.replace("mouse_", "").title()
                display = f"Mouse {btn_name}"
            elif key_val in display_names:
                display = display_names[key_val]
            else:
                display = key_val.upper()
            key_display.set_text(display)
            save_settings()
            restart_macro()

    key_set_btn.connect("clicked", on_set_key)

    def _toggle_display_text(key_val):
        display_names = {
            "enter": "Enter", "space": "Space", "tab": "Tab",
            "backspace": "Backspace", "delete": "Delete",
            "shift": "Shift", "ctrl": "Ctrl", "alt": "Alt", "cmd": "Super",
            "up": "↑ Up", "down": "↓ Down", "left": "← Left", "right": "→ Right",
            "home": "Home", "end": "End", "page_up": "Pg Up", "page_down": "Pg Dn",
            "caps_lock": "Caps Lock", "num_lock": "Num Lock",
            "insert": "Insert", "menu": "Menu", "pause": "Pause",
            "print_screen": "PrtSc", "scroll_lock": "Scroll Lock",
        }
        if key_val.startswith("kc:"):
            parts = key_val.split(":", 2)
            kc_part = parts[1]
            name_part = parts[2] if len(parts) > 2 else ""
            if "+" in name_part:
                names = name_part.split("+")
                display = []
                for n in names:
                    display.append(display_names.get(n, n.upper()))
                return " + ".join(display)
            elif "+" in kc_part:
                return _("Chord")
            if name_part in display_names:
                return display_names[name_part]
            elif name_part:
                return name_part.upper()
            else:
                return f"Key {parts[1]}"
        elif key_val.startswith("mouse_"):
            btn_name = key_val.replace("mouse_", "").title()
            return f"Mouse {btn_name}"
        elif key_val in display_names:
            return display_names[key_val]
        else:
            return key_val.upper()

    def on_set_toggle_key(btn):
        if not PYNPUT_AVAILABLE:
            return
        dialog = Gtk.Dialog(
            title=_("Set Macro Toggle Key"),
            parent=app_state["window"],
            flags=Gtk.DialogFlags.MODAL,
        )
        dialog.set_default_size(350, 180)
        box = dialog.get_content_area()
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        lbl = Gtk.Label(
            label=_("Press key combination... (ENTER to confirm, ESC to cancel)")
        )
        lbl.set_halign(Gtk.Align.CENTER)
        box.pack_start(lbl, True, True, 0)

        combo_lbl = Gtk.Label(label=_("(press keys)"))
        combo_lbl.get_style_context().add_class("setting-label")
        combo_lbl.set_halign(Gtk.Align.CENTER)
        box.pack_start(combo_lbl, False, False, 0)
        dialog.show_all()

        captured = [None]
        pressed = {}
        display_names = {
            "enter": "Enter", "space": "Space", "tab": "Tab",
            "backspace": "Backspace", "delete": "Delete",
            "shift": "Shift", "ctrl": "Ctrl", "alt": "Alt", "cmd": "Super",
            "up": "↑ Up", "down": "↓ Down", "left": "← Left", "right": "→ Right",
            "home": "Home", "end": "End", "page_up": "Pg Up", "page_down": "Pg Dn",
            "caps_lock": "Caps Lock", "num_lock": "Num Lock",
            "insert": "Insert", "menu": "Menu", "pause": "Pause",
            "print_screen": "PrtSc", "scroll_lock": "Scroll Lock",
        }
        key_normalize = {
            "return": "enter", "kp_enter": "enter",
            "shift_l": "shift", "shift_r": "shift",
            "control_l": "ctrl", "control_r": "ctrl",
            "alt_l": "alt", "alt_r": "alt",
            "super_l": "cmd", "super_r": "cmd",
        }

        def update_combo_label():
            if pressed:
                names = [display_names.get(n, n.upper())
                         for kc, n in sorted(pressed.items())]
                combo_lbl.set_text(" + ".join(names))
            else:
                combo_lbl.set_text(_("(press keys)"))

        def on_key_press(widget, event):
            keyval = event.keyval
            keyname = Gdk.keyval_name(keyval)
            hw_kc = event.hardware_keycode
            linux_kc = _x11_to_linux_keycode(hw_kc)
            kn = keyname.lower() if keyname else ""
            if kn == 'escape':
                captured[0] = '__cancel__'
                dialog.response(1)
                return True
            if kn == 'return' or kn == 'kp_enter':
                if not pressed:
                    return True
                kcs = ",".join(str(k) for k in sorted(pressed.keys()))
                names = "+".join(pressed[k] for k in sorted(pressed.keys()))
                captured[0] = f"kc:{kcs}:{names}"
                dialog.response(1)
                return True
            if linux_kc is not None and linux_kc not in pressed:
                normalized = key_normalize.get(kn, kn)
                pressed[linux_kc] = normalized
                update_combo_label()
            return True

        def on_key_release(widget, event):
            return True

        dialog.connect("key-press-event", on_key_press)
        dialog.connect("key-release-event", on_key_release)

        def on_mouse_btn(widget, event):
            btn = event.button
            btn_map = {1: "mouse_left", 2: "mouse_middle", 3: "mouse_right",
                       8: "mouse_x1", 9: "mouse_x2"}
            if btn in btn_map:
                captured[0] = btn_map[btn]
                dialog.response(1)
            return True

        dialog.connect("button-press-event", on_mouse_btn)

        dialog.run()
        dialog.destroy()

        if captured[0] and captured[0] != '__cancel__':
            key_val = captured[0]
            app_state["settings"]["macro_toggle_key"] = key_val
            toggle_display.set_text(_("Shortcut: ") + _toggle_display_text(key_val))
            save_settings()

            engine = app_state.get("macro_engine")
            if engine:
                engine.stop_toggle_listener()
                engine.start_toggle_listener(key_val, on_toggle_macro)

    toggle_set_btn.connect("clicked", on_set_toggle_key)

    def on_toggle_macro():
        macro_switch.set_active(not macro_switch.get_active())
    app_state["on_toggle_macro"] = on_toggle_macro

    current_toggle = app_state["settings"].get("macro_toggle_key", "")
    if current_toggle:
        engine = app_state.get("macro_engine")
        if engine:
            engine.start_toggle_listener(current_toggle, on_toggle_macro)

    btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    btn_row.set_halign(Gtk.Align.START)
    btn_row.set_margin_top(12)
    btn_row.set_margin_start(12)
    btn_row.set_margin_bottom(12)

    apply_btn = Gtk.Button(label=_("APPLY"))
    apply_btn.get_style_context().add_class("apply-btn")

    def on_apply_buttons(btn):
        save_active_profile()
        m = app_state["button_mapping"]
        arg = (
            f"buttons(button1={m['button1']}; button2={m['button2']}; "
            f"button3={m['button3']}; button4={m['button4']}; "
            f"button5={m['button5']}; button6={m['button6']}; "
            f"scrollup={m['scrollup']}; scrolldown={m['scrolldown']}; "
            f"layout=qwerty)"
        )
        run_rivalcfg(["--buttons", arg])

    apply_btn.connect("clicked", on_apply_buttons)
    btn_row.pack_start(apply_btn, False, False, 0)

    reset_btn = Gtk.Button(label=_("RESET"))
    reset_btn.get_style_context().add_class("reset-btn")

    def on_reset_buttons(btn):
        defaults = {
            "button1": "button1",
            "button2": "button2",
            "button3": "button3",
            "button4": "button4",
            "button5": "button5",
            "button6": "dpi",
            "scrollup": "scrollup",
            "scrolldown": "scrolldown",
        }
        app_state["button_mapping"].update(defaults)
        app_state["redraw_buttons"]()

    reset_btn.connect("clicked", on_reset_buttons)
    btn_row.pack_start(reset_btn, False, False, 0)

    card.pack_start(btn_row, False, False, 0)

    return page


def create_devices_page():
    page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    page.set_margin_top(24)
    page.set_margin_bottom(24)
    page.set_margin_start(24)
    page.set_margin_end(24)

    title = Gtk.Label(label=_("Connected Devices"))
    title.get_style_context().add_class("page-title")
    title.set_halign(Gtk.Align.START)
    page.pack_start(title, False, False, 0)

    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    card.get_style_context().add_class("card")
    page.pack_start(card, True, True, 0)

    textview = Gtk.TextView()
    textview.set_editable(False)
    textview.set_cursor_visible(False)
    textview.set_wrap_mode(Gtk.WrapMode.WORD)
    textview.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 0))
    textview.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0.8, 0.8, 0.9, 1))
    app_state["devices_buffer"] = textview.get_buffer()
    app_state["devices_buffer"].set_text(_("Click refresh to scan..."))
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scrolled.set_min_content_height(200)
    scrolled.set_vexpand(True)
    scrolled.add(textview)
    card.pack_start(scrolled, True, True, 0)

    refresh_btn = Gtk.Button(label=_("REFRESH"))
    refresh_btn.get_style_context().add_class("apply-btn")
    refresh_btn.set_halign(Gtk.Align.START)
    refresh_btn.set_margin_top(8)

    def on_refresh(btn):
        def cb(success, msg):
            GLib.idle_add(app_state["devices_buffer"].set_text, msg)
        run_rivalcfg(["--list"], cb)

    refresh_btn.connect("clicked", on_refresh)
    card.pack_start(refresh_btn, False, False, 0)

    return page


def create_about_page():
    """Create About page."""
    page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    page.set_margin_top(24)
    page.set_margin_bottom(24)
    page.set_margin_start(24)
    page.set_margin_end(24)

    title = Gtk.Label(label=_("About"))
    title.get_style_context().add_class("page-title")
    title.set_halign(Gtk.Align.START)
    page.pack_start(title, False, False, 0)

    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    card.get_style_context().add_class("card")
    page.pack_start(card, True, True, 0)

    text = (
        _("Linux GUI configuration tool for SteelSeries mice.") + "\n" +
        _("Built on top of the rivalcfg library.") #+ "\n\n" +
#        _("Requirements:") + "\n" +
#        _("  pip install rivalcfg") + "\n" +
#        _("  pacman -S python-gobject python-cairo")
    )
    label = Gtk.Label(label=text)
    label.set_line_wrap(True)
    label.set_halign(Gtk.Align.START)
    label.set_valign(Gtk.Align.START)
    card.pack_start(label, False, False, 0)

    github_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
    github_box.set_halign(Gtk.Align.START)

    github_prefix = Gtk.Label(label=_("GitHub: "))
    github_prefix.set_halign(Gtk.Align.START)
    github_box.pack_start(github_prefix, False, False, 0)

    link_btn = Gtk.LinkButton(
        uri="https://github.com/MrGodzilla38/rivalcfg-gui",
        label=_("github.com/MrGodzilla38/rivalcfg-gui")
    )
    link_btn.set_halign(Gtk.Align.START)
    link_btn.set_relief(Gtk.ReliefStyle.NONE)
    github_box.pack_start(link_btn, False, False, 0)

    card.pack_start(github_box, False, False, 0)

    return page


def apply_profile_to_ui(profile):
    app_state["_loading_profile"] = True

    if "dpi_values" in profile:
        app_state["dpi_values"] = list(profile["dpi_values"])
        if "_rebuild_dpi_ui" in app_state:
            app_state["_rebuild_dpi_ui"]()

    if "polling_hz" in profile and "polling_radios" in app_state:
        for hz, rb in app_state["polling_radios"].items():
            rb.set_active(hz == profile["polling_hz"])

    for key in ["z1_hex", "z2_hex", "z3_hex", "z4_hex"]:
        if key in profile:
            app_state[key] = profile[key]
            if key in app_state.get("color_buttons", {}):
                rgba = Gdk.RGBA()
                rgba.parse(f"#{profile[key]}")
                app_state["color_buttons"][key].set_rgba(rgba)
            if key in app_state.get("color_previews", {}):
                app_state["color_previews"][key].queue_draw()

    if "selected_effect" in profile and "effect_radios" in app_state:
        for effect, rb in app_state["effect_radios"].items():
            rb.set_active(effect == profile["selected_effect"])

    if "button_mapping" in profile:
        app_state["button_mapping"].update(profile["button_mapping"])
        if "redraw_buttons" in app_state:
            app_state["redraw_buttons"]()

    if "macro_enabled" in profile:
        app_state["settings"]["macro_cps"] = profile.get("macro_cps", 10)
        app_state["settings"]["macro_trigger_key"] = profile.get("macro_trigger_key", "f6")
        app_state["settings"]["macro_toggle_key"] = profile.get("macro_toggle_key", "")
        app_state["settings"]["macro_mode"] = profile.get("macro_mode", "toggle")
        app_state["settings"]["macro_button"] = profile.get("macro_button", "left")
        sp = app_state.get("macro_cps_spin")
        if sp:
            sp.set_value(profile.get("macro_cps", 10))
        kd = app_state.get("macro_key_display")
        if kd:
            val = profile.get("macro_trigger_key", "f6")
            if val.startswith("kc:"):
                parts = val.split(":", 2)
                key_name = parts[2] if len(parts) > 2 else ""
                kd.set_text(key_name.upper() if key_name else f"Key {parts[1]}")
            else:
                kd.set_text(val.upper())
        td = app_state.get("macro_toggle_display")
        if td:
            toggle_val = profile.get("macro_toggle_key", "")
            display_names = {
                "enter": "Enter", "space": "Space", "tab": "Tab",
                "backspace": "Backspace", "delete": "Delete",
                "shift": "Shift", "ctrl": "Ctrl", "alt": "Alt", "cmd": "Super",
                "up": "↑ Up", "down": "↓ Down", "left": "← Left", "right": "→ Right",
                "home": "Home", "end": "End", "page_up": "Pg Up", "page_down": "Pg Dn",
                "caps_lock": "Caps Lock", "num_lock": "Num Lock",
                "insert": "Insert", "menu": "Menu", "pause": "Pause",
                "print_screen": "PrtSc", "scroll_lock": "Scroll Lock",
            }
            if toggle_val.startswith("kc:"):
                parts = toggle_val.split(":", 2)
                name_part = parts[2] if len(parts) > 2 else ""
                if "+" in name_part:
                    names = name_part.split("+")
                    display = " + ".join(display_names.get(n, n.upper()) for n in names)
                elif name_part:
                    display = display_names.get(name_part, name_part.upper())
                else:
                    display = f"Key {parts[1]}"
                td.set_text(_("Shortcut: ") + display)
            elif toggle_val.startswith("mouse_"):
                td.set_text(_("Shortcut: Mouse ") + toggle_val.replace("mouse_", "").title())
            elif toggle_val:
                td.set_text(_("Shortcut: ") + toggle_val.upper())
            else:
                td.set_text(_("Shortcut: Not set"))
        engine = app_state.get("macro_engine")
        toggle_cb = app_state.get("on_toggle_macro")
        if engine and toggle_cb:
            engine.stop_toggle_listener()
            toggle_key = app_state["settings"].get("macro_toggle_key", "")
            if toggle_key:
                engine.start_toggle_listener(toggle_key, toggle_cb)
        mc = app_state.get("macro_mode_combo")
        if mc:
            mc.set_active(0 if profile.get("macro_mode", "toggle") == "toggle" else 1)
        bc = app_state.get("macro_btn_combo")
        if bc:
            bvals = ["left", "right", "middle"]
            bv = profile.get("macro_button", "left")
            bc.set_active(bvals.index(bv) if bv in bvals else 0)

    app_state["_loading_profile"] = False


def apply_all_to_device():
    """Apply all current profile settings to the device with a single rivalcfg call."""
    save_active_profile()

    args = []

    dpi_vals = app_state.get("dpi_values")
    if dpi_vals:
        args.extend(["--sensitivity", ",".join(str(v) for v in dpi_vals)])

    polling_hz = app_state.get("polling_hz")
    if polling_hz:
        args.extend(["--polling-rate", str(polling_hz)])

    z1 = app_state.get("z1_hex")
    z2 = app_state.get("z2_hex")
    z3 = app_state.get("z3_hex")
    z4 = app_state.get("z4_hex")
    effect = app_state.get("selected_effect")
    if z1:
        args.extend(["--strip-top-color", z1])
    if z2:
        args.extend(["--strip-middle-color", z2])
    if z3:
        args.extend(["--strip-bottom-color", z3])
    if z4:
        args.extend(["--logo-color", z4])
    if effect:
        args.extend(["--light-effect", effect])

    mapping = app_state.get("button_mapping")
    if mapping:
        btn_arg = (
            f"buttons(button1={mapping['button1']}; button2={mapping['button2']}; "
            f"button3={mapping['button3']}; button4={mapping['button4']}; "
            f"button5={mapping['button5']}; button6={mapping['button6']}; "
            f"scrollup={mapping['scrollup']}; scrolldown={mapping['scrolldown']}; "
            f"layout=qwerty)"
        )
        args.extend(["--buttons", btn_arg])

    if args:
        run_rivalcfg(args)


def create_settings_page():
    """Create Settings page."""
    page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    page.set_margin_top(24)
    page.set_margin_bottom(24)
    page.set_margin_start(24)
    page.set_margin_end(24)

    title = Gtk.Label(label=_("Settings"))
    title.get_style_context().add_class("page-title")
    title.set_halign(Gtk.Align.START)
    page.pack_start(title, False, False, 0)

    # --- BEHAVIOR CARD ---
    behavior_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    behavior_card.get_style_context().add_class("card")
    page.pack_start(behavior_card, False, False, 0)

    behavior_title = Gtk.Label(label=_("BEHAVIOR"))
    behavior_title.get_style_context().add_class("card-title")
    behavior_title.set_halign(Gtk.Align.START)
    behavior_card.pack_start(behavior_title, False, False, 0)

    # Startup Minimize
    sm_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
    sm_row.get_style_context().add_class("setting-row")

    sm_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    sm_text.set_hexpand(True)
    sm_label = Gtk.Label(label=_("Startup Minimize"))
    sm_label.get_style_context().add_class("setting-label")
    sm_label.set_halign(Gtk.Align.START)
    sm_desc = Gtk.Label(label=_("Launch minimized to system tray"))
    sm_desc.get_style_context().add_class("setting-desc")
    sm_desc.set_halign(Gtk.Align.START)
    sm_text.pack_start(sm_label, False, False, 0)
    sm_text.pack_start(sm_desc, False, False, 0)
    sm_row.pack_start(sm_text, True, True, 0)

    sm_switch = Gtk.Switch()
    sm_switch.set_active(app_state["settings"]["startup_minimize"])
    sm_row.pack_start(sm_switch, False, False, 0)

    def on_startup_minimize(s, *a):
        val = sm_switch.get_active()
        app_state["settings"]["startup_minimize"] = val
        logging.info("Settings: startup_minimize = %s", val)
        save_settings()
    sm_switch.connect("notify::active", on_startup_minimize)
    behavior_card.pack_start(sm_row, False, False, 0)

    # Auto-Apply on Change
    aa_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
    aa_row.get_style_context().add_class("setting-row")

    aa_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    aa_text.set_hexpand(True)
    aa_label = Gtk.Label(label=_("Auto-Apply on Change"))
    aa_label.get_style_context().add_class("setting-label")
    aa_label.set_halign(Gtk.Align.START)
    aa_desc = Gtk.Label(label=_("Apply settings immediately when changed"))
    aa_desc.get_style_context().add_class("setting-desc")
    aa_desc.set_halign(Gtk.Align.START)
    aa_text.pack_start(aa_label, False, False, 0)
    aa_text.pack_start(aa_desc, False, False, 0)
    aa_row.pack_start(aa_text, True, True, 0)

    aa_switch = Gtk.Switch()
    aa_switch.set_active(app_state["settings"]["auto_apply"])
    aa_row.pack_start(aa_switch, False, False, 0)

    def on_auto_apply(s, *a):
        val = aa_switch.get_active()
        app_state["settings"]["auto_apply"] = val
        logging.info("Settings: auto_apply = %s", val)
        save_settings()
    aa_switch.connect("notify::active", on_auto_apply)
    behavior_card.pack_start(aa_row, False, False, 0)

    # --- LANGUAGE CARD ---
    language_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    language_card.get_style_context().add_class("card")
    page.pack_start(language_card, False, False, 0)

    language_title = Gtk.Label(label=_("LANGUAGE"))
    language_title.get_style_context().add_class("card-title")
    language_title.set_halign(Gtk.Align.START)
    language_card.pack_start(language_title, False, False, 0)

    lang_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
    lang_row.get_style_context().add_class("setting-row")

    lang_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    lang_text.set_hexpand(True)
    lang_label = Gtk.Label(label=_("Language"))
    lang_label.get_style_context().add_class("setting-label")
    lang_label.set_halign(Gtk.Align.START)
    lang_desc = Gtk.Label(label=_("Select application display language"))
    lang_desc.get_style_context().add_class("setting-desc")
    lang_desc.set_halign(Gtk.Align.START)
    lang_text.pack_start(lang_label, False, False, 0)
    lang_text.pack_start(lang_desc, False, False, 0)
    lang_row.pack_start(lang_text, True, True, 0)

    lang_combo = Gtk.ComboBoxText()
    languages = [
        ("en", "🇺🇲 English"),
        ("de", "🇩🇪 Deutsch"),
        ("es", "🇪🇸 Español"),
        ("fr", "🇫🇷 Français"),
        ("it", "🇮🇹 Italiano"),
        ("pl", "🇵🇱 Polski"),
        ("pt_BR", "🇧🇷 Português (Brasil)"),
        ("ru", "🇷🇺 Русский"),
        ("tr", "🇹🇷 Türkçe"),
        ("zh_CN", "🇨🇳 简体中文"),
    ]
    current_lang = app_state["settings"].get("language", "en")
    for code, name in languages:
        lang_combo.append_text(name)
        if code == current_lang:
            lang_combo.set_active(languages.index((code, name)))
    if lang_combo.get_active() == -1:
        lang_combo.set_active(0)
    lang_row.pack_start(lang_combo, False, False, 0)

    def on_lang_changed(combo):
        selected_idx = combo.get_active()
        lang_code = languages[selected_idx][0]
        app_state["settings"]["language"] = lang_code
        logging.info("Settings: language = %s", lang_code)
        save_settings()
        _set_language(lang_code)
        rebuild_ui()

    lang_combo.connect("changed", on_lang_changed)
    language_card.pack_start(lang_row, False, False, 0)

    # --- APPEARANCE CARD ---
    appearance_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    appearance_card.get_style_context().add_class("card")
    page.pack_start(appearance_card, False, False, 0)

    appearance_title = Gtk.Label(label=_("APPEARANCE"))
    appearance_title.get_style_context().add_class("card-title")
    appearance_title.set_halign(Gtk.Align.START)
    appearance_card.pack_start(appearance_title, False, False, 0)

    # Accent Color
    ac_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
    ac_row.get_style_context().add_class("setting-row")

    ac_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    ac_text.set_hexpand(True)
    ac_label = Gtk.Label(label=_("Accent Color"))
    ac_label.get_style_context().add_class("setting-label")
    ac_label.set_halign(Gtk.Align.START)
    ac_desc = Gtk.Label(label=_("UI highlight and button color"))
    ac_desc.get_style_context().add_class("setting-desc")
    ac_desc.set_halign(Gtk.Align.START)
    ac_text.pack_start(ac_label, False, False, 0)
    ac_text.pack_start(ac_desc, False, False, 0)
    ac_row.pack_start(ac_text, True, True, 0)

    current_accent = app_state["settings"]["accent_color"]
    rgba = Gdk.RGBA()
    rgba.parse(current_accent)

    ac_color_btn = Gtk.ColorButton()
    ac_color_btn.set_rgba(rgba)
    ac_color_btn.set_size_request(50, 30)
    ac_row.pack_start(ac_color_btn, False, False, 0)

    ac_preview = Gtk.DrawingArea()
    ac_preview.set_size_request(60, 24)
    ac_preview.get_style_context().add_class("color-preview")
    ac_row.pack_start(ac_preview, False, False, 0)

    def on_accent_draw(widget, cr):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        r = int(current_accent[1:3], 16) / 255.0
        g = int(current_accent[3:5], 16) / 255.0
        b = int(current_accent[5:7], 16) / 255.0
        cr.set_source_rgb(r, g, b)
        cr.rectangle(0, 0, w, h)
        cr.fill()
        return False

    ac_preview.connect("draw", on_accent_draw)

    def on_accent_color_set(button):
        nonlocal current_accent
        col = button.get_rgba()
        current_accent = f"#{int(col.red * 255):02x}{int(col.green * 255):02x}{int(col.blue * 255):02x}"
        app_state["settings"]["accent_color"] = current_accent
        logging.info("Settings: accent_color = %s", current_accent)
        ac_preview.queue_draw()
        update_accent_color(current_accent)
        save_settings()

    ac_color_btn.connect("color-set", on_accent_color_set)
    appearance_card.pack_start(ac_row, False, False, 0)

    # Reset to Default button
    reset_accent_btn = Gtk.Button(label=_("Reset to Default"))
    reset_accent_btn.get_style_context().add_class("reset-btn")
    reset_accent_btn.set_halign(Gtk.Align.START)
    reset_accent_btn.set_margin_top(8)

    def on_reset_accent(btn):
        nonlocal current_accent
        current_accent = DEFAULT_SETTINGS["accent_color"]
        app_state["settings"]["accent_color"] = current_accent
        logging.info("Settings: accent_color reset to default")
        rgba = Gdk.RGBA()
        rgba.parse(current_accent)
        ac_color_btn.set_rgba(rgba)
        ac_preview.queue_draw()
        update_accent_color(current_accent)
        save_settings()

    reset_accent_btn.connect("clicked", on_reset_accent)
    appearance_card.pack_start(reset_accent_btn, False, False, 0)

    # --- DIAGNOSTICS CARD ---
    diagnostics_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    diagnostics_card.get_style_context().add_class("card")
    page.pack_start(diagnostics_card, False, False, 0)

    diagnostics_title = Gtk.Label(label=_("Mouse Settings"))
    diagnostics_title.get_style_context().add_class("card-title")
    diagnostics_title.set_halign(Gtk.Align.START)
    diagnostics_card.pack_start(diagnostics_title, False, False, 0)

    diag_btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    diag_btn_box.set_halign(Gtk.Align.START)

    check_btn = Gtk.Button(label=_("CHECK MOUSE"))
    check_btn.get_style_context().add_class("apply-btn")

    def on_check_mouse(btn):
        def on_detect(success, msg):
            if success and "184c" in msg:
                GLib.idle_add(set_status, "ok", "✓ " + _("Mouse connected"))
            else:
                GLib.idle_add(set_status, "error", "✗ " + _("Mouse not found"))

        def on_list(success, msg):
            GLib.idle_add(app_state["devices_buffer"].set_text, msg if msg else _("No device found."))

        run_rivalcfg(["--print-debug"], on_detect)
        run_rivalcfg(["--list"], on_list)

    check_btn.connect("clicked", on_check_mouse)
    diag_btn_box.pack_start(check_btn, False, False, 0)

    fw_btn = Gtk.Button(label=_("FIRMWARE VERSION"))
    fw_btn.get_style_context().add_class("apply-btn")

    def on_firmware(btn):
        def cb(success, msg):
            if success:
                GLib.idle_add(set_status, "ok", "✓ " + _("Firmware: %s") % msg)
            else:
                GLib.idle_add(set_status, "error", "✗ " + _("Mouse not connected"))
        run_rivalcfg(["--firmware-version"], cb)

    fw_btn.connect("clicked", on_firmware)
    diag_btn_box.pack_start(fw_btn, False, False, 0)

    reset_btn = Gtk.Button(label=_("FACTORY RESET"))
    reset_btn.get_style_context().add_class("danger-btn")

    def on_factory_reset(btn):
        dialog = Gtk.MessageDialog(
            parent=app_state.get("window"),
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            message_format=_("All settings will be restored to factory defaults. Are you sure?")
        )
        dialog.set_title(_("Factory Reset"))
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.OK:
            logging.info("Factory reset executed")
            def cb(success, msg):
                if not success:
                    GLib.idle_add(set_status, "error", "✗ " + _("Mouse not connected"))
                    return
                orange = "ff6600"
                for key in ["z1_hex", "z2_hex", "z3_hex", "z4_hex"]:
                    app_state[key] = orange
                    if key in app_state.get("color_buttons", {}):
                        rgba = Gdk.RGBA()
                        rgba.parse(f"#{orange}")
                        app_state["color_buttons"][key].set_rgba(rgba)
                    if key in app_state.get("color_previews", {}):
                        app_state["color_previews"][key].queue_draw()
                z1 = app_state["z1_hex"]
                z2 = app_state["z2_hex"]
                z3 = app_state["z3_hex"]
                z4 = app_state["z4_hex"]
                def after_z1(success, msg):
                    if not success:
                        return
                    run_rivalcfg(["--strip-middle-color", z2], after_z2)
                def after_z2(success, msg):
                    if not success:
                        return
                    run_rivalcfg(["--strip-bottom-color", z3], after_z3)
                def after_z3(success, msg):
                    if not success:
                        return
                    run_rivalcfg(["--logo-color", z4], after_z4)
                def after_z4(success, msg):
                    if not success:
                        return
                    run_rivalcfg(["--light-effect", "steady"])
                run_rivalcfg(["--strip-top-color", z1], after_z1)
                save_active_profile()
            run_rivalcfg(["--reset"], cb)

    reset_btn.connect("clicked", on_factory_reset)
    diag_btn_box.pack_start(reset_btn, False, False, 0)

    diagnostics_card.pack_start(diag_btn_box, False, False, 0)

    return page


def update_accent_color(accent):
    """Update the CSS accent color dynamically."""
    r = int(accent[1:3], 16) / 255.0
    g = int(accent[3:5], 16) / 255.0
    b = int(accent[5:7], 16) / 255.0
    rgb = f"{r:.2f}, {g:.2f}, {b:.2f}"
    css_accent = f"""
    .nav-active {{
        background: rgba({rgb}, 0.13);
        color: {accent};
    }}
    .apply-btn {{
        background: {accent};
    }}
    .apply-btn:hover {{
        background: rgba({rgb}, 0.8);
    }}
    .card-title {{
        color: {accent};
    }}
    scale trough highlight {{
        background: {accent};
    }}
    .danger-btn {{
        border: 1px solid {accent};
        color: {accent};
    }}
    .danger-btn:hover {{
        background: {accent};
    }}
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css_accent.encode('utf-8'))
    context = Gtk.StyleContext()
    screen = Gdk.Screen.get_default()
    context.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)


def rebuild_ui():
    """Rebuild the entire UI with the new language."""
    logging.info("UI rebuilt (language changed)")
    window = app_state["window"]
    current_page = app_state["stack"].get_visible_child_name()
    current_status_text = app_state["status_label"].get_text()
    current_status_classes = app_state["status_dot"].get_style_context().list_classes()

    for child in window.get_children():
        window.remove(child)

    window.set_wmclass("rivalcfg-gui", "RivalCFG GUI")
    icon_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets", "logo.png")
    if os.path.exists(icon_path):
        icon_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_path, 128, 128, True)
        window.set_icon(icon_pixbuf)
        Gtk.Window.set_default_icon_from_file(icon_path)

    engine = app_state.get("macro_engine")
    if engine:
        engine.stop_toggle_listener()
    app_state["nav_buttons"] = []
    app_state["is_rebuild"] = True
    create_window_content(window)

    window.show_all()

    macro_box = app_state.get("macro_settings_box")
    if macro_box:
        macro_box.set_visible(app_state["settings"].get("macro_enabled", False))

    active = app_state["settings"].get("active_profile", "Default")
    profile_data = load_profile_data(active)
    if profile_data:
        apply_profile_to_ui(profile_data)

    if app_state["settings"]["startup_minimize"]:
        window.iconify()

    def restore_page():
        app_state["stack"].set_visible_child_name(current_page)
        nav_labels = {
            "dpi": _("DPI"),
            "polling": _("POLLING"),
            "rgb": _("RGB"),
            "buttons": _("BUTTONS"),
            "devices": _("DEVICES"),
            "settings": _("SETTINGS"),
            "about": _("ABOUT"),
        }
        target_label = nav_labels.get(current_page, current_page)
        for btn in app_state["nav_buttons"]:
            btn.get_style_context().remove_class("nav-active")
            if btn.get_label() == target_label:
                btn.get_style_context().add_class("nav-active")

        app_state["status_label"].set_text(current_status_text)
        for cls in current_status_classes:
            app_state["status_dot"].get_style_context().add_class(cls)

        return False

    GLib.idle_add(restore_page)


def create_window():
    """Create the main window and its contents."""
    app_state["settings"] = load_settings()
    app_state["is_rebuild"] = False
    lang = app_state["settings"].get("language", None)
    _set_language(lang)

    if PYNPUT_AVAILABLE:
        app_state["macro_engine"] = MacroEngine()

    window = Gtk.Window(title="RivalCFG GUI")
    window.set_default_size(1280, 720)
    window.set_resizable(True)

    def on_destroy(*a):
        if app_state.get("macro_engine"):
            app_state["macro_engine"].stop()
            app_state["macro_engine"].stop_toggle_listener()
        Gtk.main_quit()

    window.connect("destroy", on_destroy)
    window.set_wmclass("rivalcfg-gui", "RivalCFG GUI")

    icon_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets", "logo.png")
    if os.path.exists(icon_path):
        icon_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_path, 128, 128, True)
        window.set_icon(icon_pixbuf)
        Gtk.Window.set_default_icon_from_file(icon_path)

    app_state["window"] = window

    css_provider = Gtk.CssProvider()
    css_provider.load_from_data(CSS.encode('utf-8'))
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    update_accent_color(app_state["settings"]["accent_color"])

    create_window_content(window)

    window.show_all()

    macro_box = app_state.get("macro_settings_box")
    if macro_box:
        macro_box.set_visible(app_state["settings"].get("macro_enabled", False))

    active = app_state["settings"].get("active_profile", "Default")
    profiles = list_profiles()
    if active not in profiles:
        active = "Default"
        app_state["settings"]["active_profile"] = "Default"
        save_settings()
    profile_data = load_profile_data(active)
    if profile_data:
        apply_profile_to_ui(profile_data)

    # Always start with auto-clicker disabled
    app_state["settings"]["macro_enabled"] = False
    sw = app_state.get("macro_switch")
    if sw:
        sw.set_active(False)
    engine = app_state.get("macro_engine")
    if engine:
        engine.stop()

    if app_state["settings"]["startup_minimize"]:
        window.iconify()


def create_window_content(window):
    """Create the main window content. Separated for rebuild_ui."""
    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    window.add(vbox)

    content_grid = Gtk.Grid()
    content_grid.set_column_spacing(0)
    content_grid.set_row_spacing(0)
    content_grid.set_column_homogeneous(False)
    content_grid.set_vexpand(True)
    content_grid.set_hexpand(True)
    vbox.pack_start(content_grid, True, True, 0)

    sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    sidebar.set_size_request(180, -1)
    sidebar.get_style_context().add_class("sidebar")
    sidebar.set_margin_top(16)
    sidebar.set_margin_bottom(16)
    sidebar.set_margin_start(16)
    sidebar.set_margin_end(16)
    sidebar.set_vexpand(True)
    sidebar.set_hexpand(False)
    sidebar.set_halign(Gtk.Align.START)

    content_grid.attach(sidebar, 0, 0, 1, 1)

    icon_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets", "logo.png")
    if os.path.exists(icon_path):
        logo_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_path, 100, 100, True)
        logo_img = Gtk.Image.new_from_pixbuf(logo_pixbuf)
        logo_img.set_margin_bottom(8)
        sidebar.pack_start(logo_img, False, False, 0)

    brand = Gtk.Label(label="RivalCFG GUI")
    brand.get_style_context().add_class("page-title")
    brand.set_margin_bottom(20)
    brand.set_halign(Gtk.Align.CENTER)
    brand.set_hexpand(True)
    sidebar.pack_start(brand, False, False, 0)

    def update_profile_selector_label(name):
        label = app_state.get("profile_label")
        if label:
            label.set_text(name)

    def close_profile_popover():
        popover = app_state.get("profile_popover")
        if popover:
            popover.popdown()

    def select_profile(name, close_popover=False):
        if app_state.get("_loading_profile"):
            return
        profile_data = load_profile_data(name)
        if profile_data:
            apply_profile_to_ui(profile_data)
        app_state["settings"]["active_profile"] = name
        save_settings()
        update_profile_selector_label(name)
        apply_all_to_device()
        logging.info("Profile activated: %s", name)
        if close_popover:
            close_profile_popover()

    def on_delete_profile_named(name):
        if not name:
            return
        close_profile_popover()
        profiles = list_profiles()
        if len(profiles) <= 1:
            dialog = Gtk.MessageDialog(
                parent=app_state["window"],
                flags=Gtk.DialogFlags.MODAL,
                type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                message_format=_("Cannot delete the last profile."),
            )
            dialog.run()
            dialog.destroy()
            return
        dialog = Gtk.MessageDialog(
            parent=app_state["window"],
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            message_format=_('Delete profile "%s"?') % name,
        )
        dialog.set_title(_("Delete Profile"))
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return
        was_active = app_state["settings"].get("active_profile") == name
        delete_profile_file(name)
        logging.info("Profile deleted: %s", name)
        refresh_profile_selector()
        if was_active:
            remaining = list_profiles()
            if remaining:
                select_profile(remaining[0])

    def on_rename_profile_named(name):
        if not name:
            return
        close_profile_popover()
        dialog = Gtk.Dialog(
            title=_("Rename Profile"),
            parent=app_state["window"],
            flags=Gtk.DialogFlags.MODAL,
        )
        dialog.add_buttons(
            _("Cancel"), Gtk.ResponseType.CANCEL,
            _("OK"), Gtk.ResponseType.OK,
        )
        dialog.set_default_size(300, 130)
        box = dialog.get_content_area()
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        lbl = Gtk.Label(label=_("Profile name:"))
        lbl.set_halign(Gtk.Align.START)
        box.pack_start(lbl, False, False, 4)
        entry = Gtk.Entry()
        entry.set_text(name)
        box.pack_start(entry, False, False, 4)
        dialog.show_all()
        response = dialog.run()
        new_name = entry.get_text().strip()
        dialog.destroy()
        if response != Gtk.ResponseType.OK or not new_name or new_name == name:
            return
        if not rename_profile_file(name, new_name):
            err = Gtk.MessageDialog(
                parent=app_state["window"],
                flags=Gtk.DialogFlags.MODAL,
                type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                message_format=_('Could not rename to "%s". Name may already exist.') % new_name,
            )
            err.run()
            err.destroy()
            return
        logging.info("Profile renamed: %s → %s", name, new_name)
        if app_state["settings"].get("active_profile") == name:
            app_state["settings"]["active_profile"] = new_name
            save_settings()
            update_profile_selector_label(new_name)
        refresh_profile_selector()

    def refresh_profile_selector():
        profile_list = app_state.get("profile_list")
        if not profile_list:
            return
        active = app_state["settings"].get("active_profile", "Default")
        profiles = list_profiles()
        for child in profile_list.get_children():
            profile_list.remove(child)
        for p in profiles:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            row.set_margin_start(4)
            row.set_margin_end(4)
            row.get_style_context().add_class("profile-popover-row")
            name_btn = Gtk.Button(label=p)
            name_btn.set_relief(Gtk.ReliefStyle.NONE)
            name_btn.set_halign(Gtk.Align.START)
            name_btn.set_hexpand(True)
            name_btn.get_style_context().add_class("profile-menu-select")
            name_btn.connect("clicked", lambda _w, profile_name=p: select_profile(profile_name, close_popover=True))
            edit_btn_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets", "pencil.svg"),
                16, 16, True)
            edit_btn = Gtk.Button()
            edit_btn.set_image(Gtk.Image.new_from_pixbuf(edit_btn_pixbuf))
            edit_btn.set_relief(Gtk.ReliefStyle.NONE)
            edit_btn.get_style_context().add_class("profile-menu-action")
            edit_btn.connect("clicked", lambda _w, profile_name=p: on_rename_profile_named(profile_name))
            delete_btn_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets", "trash.svg"),
                16, 16, True)
            delete_btn = Gtk.Button()
            delete_btn.set_image(Gtk.Image.new_from_pixbuf(delete_btn_pixbuf))
            delete_btn.set_relief(Gtk.ReliefStyle.NONE)
            delete_btn.get_style_context().add_class("profile-menu-action")
            delete_btn.get_style_context().add_class("profile-menu-delete")
            delete_btn.connect("clicked", lambda _w, profile_name=p: on_delete_profile_named(profile_name))
            row.pack_start(name_btn, True, True, 0)
            row.pack_start(edit_btn, False, False, 0)
            row.pack_start(delete_btn, False, False, 0)
            profile_list.pack_start(row, False, False, 0)
        profile_list.show_all()
        if active in profiles:
            update_profile_selector_label(active)
        elif profiles:
            select_profile(profiles[0])
        else:
            update_profile_selector_label("Default")

    def on_new_profile(btn):
        dialog = Gtk.Dialog(
            title=_("New Profile"),
            parent=app_state["window"],
            flags=Gtk.DialogFlags.MODAL,
        )
        dialog.add_buttons(
            _("Cancel"), Gtk.ResponseType.CANCEL,
            _("OK"), Gtk.ResponseType.OK,
        )
        dialog.set_default_size(300, 130)
        box = dialog.get_content_area()
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        lbl = Gtk.Label(label=_("Profile name:"))
        lbl.set_halign(Gtk.Align.START)
        box.pack_start(lbl, False, False, 4)
        entry = Gtk.Entry()
        box.pack_start(entry, False, False, 4)
        dialog.show_all()
        response = dialog.run()
        name = entry.get_text().strip()
        dialog.destroy()
        if response == Gtk.ResponseType.OK and name:
            save_profile(name)
            logging.info("Profile created: %s", name)
            app_state["settings"]["active_profile"] = name
            save_settings()
            refresh_profile_selector()
            select_profile(name)

    profile_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    profile_section.set_margin_bottom(16)
    profile_section.set_hexpand(True)
    profile_section.set_halign(Gtk.Align.FILL)

    profile_title = Gtk.Label(label=_("PROFILES"))
    profile_title.get_style_context().add_class("card-title")
    profile_title.set_halign(Gtk.Align.START)
    profile_section.pack_start(profile_title, False, False, 0)

    combo_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    profile_selector_btn = Gtk.Button()
    profile_selector_btn.set_hexpand(True)
    profile_selector_btn.set_halign(Gtk.Align.FILL)
    profile_selector_btn.set_relief(Gtk.ReliefStyle.NONE)
    profile_selector_btn.get_style_context().add_class("profile-selector")
    profile_selector_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    profile_label = Gtk.Label(label=app_state["settings"].get("active_profile", "Default"))
    profile_label.set_halign(Gtk.Align.START)
    profile_label.set_hexpand(True)
    profile_arrow = Gtk.Label(label="▾")
    profile_arrow.get_style_context().add_class("profile-arrow")
    profile_selector_box.pack_start(profile_label, True, True, 0)
    profile_selector_box.pack_start(profile_arrow, False, False, 0)
    profile_selector_btn.add(profile_selector_box)
    profile_popover = Gtk.Popover.new(profile_selector_btn)
    profile_popover.set_position(Gtk.PositionType.BOTTOM)
    profile_popover.get_style_context().add_class("profile-popover")
    profile_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    profile_list.set_size_request(200, -1)
    profile_popover.add(profile_list)
    def toggle_profile_popover(_btn):
        if profile_popover.get_visible():
            profile_popover.popdown()
        else:
            profile_popover.popup()

    profile_selector_btn.connect("clicked", toggle_profile_popover)
    combo_row.pack_start(profile_selector_btn, True, True, 0)
    new_btn = Gtk.Button(label="+")
    new_btn.set_size_request(32, -1)
    new_btn.get_style_context().add_class("reset-btn")
    new_btn.connect("clicked", on_new_profile)
    combo_row.pack_start(new_btn, False, False, 0)
    profile_section.pack_start(combo_row, True, True, 0)

    sidebar.pack_start(profile_section, False, False, 0)
    app_state["profile_popover"] = profile_popover
    app_state["profile_list"] = profile_list
    app_state["profile_selector_btn"] = profile_selector_btn
    app_state["profile_label"] = profile_label
    refresh_profile_selector()

    stack = Gtk.Stack()
    stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
    stack.set_hexpand(True)
    stack.set_vexpand(True)

    stack_scroll = Gtk.ScrolledWindow()
    stack_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    stack_scroll.set_vexpand(True)
    stack_scroll.set_hexpand(True)
    stack_scroll.add(stack)
    content_grid.attach(stack_scroll, 1, 0, 1, 1)
    app_state["stack"] = stack

    pages = [
        ("dpi", _("DPI"), create_dpi_page()),
        ("polling", _("POLLING"), create_polling_page()),
        ("rgb", _("RGB"), create_rgb_page()),
        ("buttons", _("BUTTONS"), create_buttons_page()),
        ("devices", _("DEVICES"), create_devices_page()),
        ("settings", _("SETTINGS"), create_settings_page()),
        ("about", _("ABOUT"), create_about_page()),
    ]

    for name, title, page in pages:
        stack.add_named(page, name)

    app_state["nav_buttons"] = []

    def on_nav_clicked(button, page_name):
        for btn in app_state["nav_buttons"]:
            btn.get_style_context().remove_class("nav-active")
        button.get_style_context().add_class("nav-active")
        stack.set_visible_child_name(page_name)

    nav_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

    for i, (name, title, __page) in enumerate(pages):
        btn = Gtk.Button(label=title)
        btn.get_style_context().add_class("nav-btn")
        if i == 0:
            btn.get_style_context().add_class("nav-active")
        btn.set_hexpand(True)
        btn.set_halign(Gtk.Align.FILL)
        btn.connect("clicked", on_nav_clicked, name)
        nav_box.pack_start(btn, False, False, 0)
        app_state["nav_buttons"].append(btn)

    nav_scroll = Gtk.ScrolledWindow()
    nav_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    nav_scroll.set_vexpand(True)
    nav_scroll.add(nav_box)
    sidebar.pack_start(nav_scroll, True, True, 0)

    status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    status_bar.set_size_request(-1, 32)
    status_bar.get_style_context().add_class("status-bar")
    vbox.pack_end(status_bar, False, False, 0)

    dot = Gtk.Label(label="●")
    dot.get_style_context().add_class("status-running")
    status_bar.pack_start(dot, False, False, 0)
    app_state["status_dot"] = dot

    status_label = Gtk.Label(label=_("Starting..."))
    status_label.set_halign(Gtk.Align.START)
    status_bar.pack_start(status_label, False, False, 0)
    app_state["status_label"] = status_label

    app_state["no_save"] = False
    no_save_check = Gtk.CheckButton(label=_("Don't save (--no-save)"))
    status_bar.pack_end(no_save_check, False, False, 0)

    def on_no_save_toggled(button):
        val = button.get_active()
        app_state["no_save"] = val
        logging.info("Settings: no_save = %s", val)

    no_save_check.connect("toggled", on_no_save_toggled)

    if not app_state.get("is_rebuild"):
        def startup_check():
            def cb(success, msg):
                if success and "184c" in msg:
                    logging.info("Startup: mouse connected")
                    set_status("ok", "✓ " + _("Mouse connected"))
                else:
                    logging.warning("Startup: mouse not found")
                    set_status("error", "✗ " + _("Mouse not found"))
            run_rivalcfg(["--print-debug"], cb)

        GLib.idle_add(startup_check)


def main():
    GLib.set_prgname("rivalcfg-gui")
    setup_logging()
    logging.info("Application started")
    create_window()
    Gtk.main()


main()