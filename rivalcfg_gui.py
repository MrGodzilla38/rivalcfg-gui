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

LOCALE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")

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

# Check rivalcfg CLI availability
try:
    subprocess.run(["rivalcfg"], capture_output=True, timeout=5)
except FileNotFoundError:
    logging.critical("rivalcfg is not installed. Install: pip install rivalcfg")
    print(_("rivalcfg is not installed. Install: pip install rivalcfg"))
    sys.exit(1)

# Global dictionary holding application state
app_state = {}

SETTINGS_DIR = os.path.expanduser("~/.config/rivalcfg-gui")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")
LOGS_DIR = os.path.join(SETTINGS_DIR, "logs")

DEFAULT_SETTINGS = {
    "startup_minimize": False,
    "auto_apply": False,
    "accent_color": "#e84545",
    "language": "en",
    "active_profile": "Default",
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
        with open(SETTINGS_FILE, "w") as f:
            json.dump(app_state["settings"], f, indent=4)
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
    profile = {
        "dpi_values": app_state.get("dpi_values", [800, 1600]),
        "polling_hz": app_state.get("polling_hz", 1000),
        "z1_hex": app_state.get("z1_hex", "ff6600"),
        "z2_hex": app_state.get("z2_hex", "ff6600"),
        "z3_hex": app_state.get("z3_hex", "ff6600"),
        "z4_hex": app_state.get("z4_hex", "ff6600"),
        "selected_effect": app_state.get("selected_effect", "steady"),
        "button_mapping": app_state.get("button_mapping", {}),
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
    color: #e84545;
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
    color: #e84545;
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
    color: #e84545;
    font-weight: bold;
}

.value-display {
    font-size: 26px;
    color: #ffffff;
    font-family: monospace;
}

.apply-btn {
    background: #e84545;
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
    color: #e84545;
}

scale trough {
    background: #1a1a2e;
    min-height: 6px;
}

scale trough highlight {
    background: #e84545;
}

scale slider {
    background: #ffffff;
    min-width: 16px;
    min-height: 16px;
}

.danger-btn {
    background: #2a0a0a;
    border: 1px solid #e84545;
    color: #e84545;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
}

.danger-btn:hover {
    background: #e84545;
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
            cmd = ["rivalcfg"]
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

    assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
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

            val_label = Gtk.Label(label=str(val))
            val_label.get_style_context().add_class("value-display")
            val_label.set_size_request(80, -1)
            val_label.set_halign(Gtk.Align.START)
            row.pack_start(val_label, False, False, 0)
            app_state["dpi_labels"].append(val_label)

            scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
            scale.set_range(200, 8500)
            scale.set_increments(100, 100)
            scale.set_draw_value(False)
            scale.set_digits(0)
            scale.set_value(val)
            scale.set_hexpand(True)

            def on_dpi_changed(sc, idx=i, vl=val_label):
                v = int(sc.get_value())
                vl.set_text(str(v))
                app_state["dpi_values"][idx] = v
                if not app_state.get("_loading_profile") and app_state["settings"].get("auto_apply"):
                    vals = app_state["dpi_values"]
                    arg = ",".join(str(val) for val in vals)
                    run_rivalcfg(["--sensitivity", arg])

            scale.connect("value-changed", on_dpi_changed)
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

    img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "rival3.png")

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
        _("Built on top of the rivalcfg library.") + "\n\n" +
        _("Requirements:") + "\n" +
        _("  pip install rivalcfg") + "\n" +
        _("  pacman -S python-gobject python-cairo")
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
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")
    if os.path.exists(icon_path):
        icon_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_path, 128, 128, True)
        window.set_icon(icon_pixbuf)
        Gtk.Window.set_default_icon_from_file(icon_path)

    app_state["nav_buttons"] = []
    app_state["is_rebuild"] = True
    create_window_content(window)

    active = app_state["settings"].get("active_profile", "Default")
    profile_data = load_profile_data(active)
    if profile_data:
        apply_profile_to_ui(profile_data)

    window.show_all()

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

    window = Gtk.Window(title="RivalCFG GUI")
    window.set_default_size(1280, 720)
    window.set_resizable(True)
    window.connect("destroy", Gtk.main_quit)
    window.set_wmclass("rivalcfg-gui", "RivalCFG GUI")

    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")
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

    active = app_state["settings"].get("active_profile", "Default")
    profiles = list_profiles()
    if active not in profiles:
        active = "Default"
        app_state["settings"]["active_profile"] = "Default"
        save_settings()
    profile_data = load_profile_data(active)
    if profile_data:
        apply_profile_to_ui(profile_data)

    window.show_all()

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

    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")
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
    sidebar.pack_start(brand, True, False, 0)

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
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "pencil.svg"),
                16, 16, True)
            edit_btn = Gtk.Button()
            edit_btn.set_image(Gtk.Image.new_from_pixbuf(edit_btn_pixbuf))
            edit_btn.set_relief(Gtk.ReliefStyle.NONE)
            edit_btn.get_style_context().add_class("profile-menu-action")
            edit_btn.connect("clicked", lambda _w, profile_name=p: on_rename_profile_named(profile_name))
            delete_btn_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "trash.svg"),
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

    sidebar.pack_start(profile_section, True, True, 0)
    app_state["profile_popover"] = profile_popover
    app_state["profile_list"] = profile_list
    app_state["profile_selector_btn"] = profile_selector_btn
    app_state["profile_label"] = profile_label
    refresh_profile_selector()

    stack = Gtk.Stack()
    stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
    stack.set_hexpand(True)
    stack.set_vexpand(True)
    content_grid.attach(stack, 1, 0, 1, 1)
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

    for i, (name, title, __page) in enumerate(pages):
        btn = Gtk.Button(label=title)
        btn.get_style_context().add_class("nav-btn")
        if i == 0:
            btn.get_style_context().add_class("nav-active")
        btn.set_hexpand(True)
        btn.set_halign(Gtk.Align.FILL)
        btn.connect("clicked", on_nav_clicked, name)
        sidebar.pack_start(btn, True, True, 0)
        app_state["nav_buttons"].append(btn)

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