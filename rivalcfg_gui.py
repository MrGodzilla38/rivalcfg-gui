#!/usr/bin/env python3

# GTK3 bağımlılığı kontrolü
import sys
import os
import subprocess
import threading
import math

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, Gdk, GLib, GdkPixbuf
    import cairo
except ImportError:
    print("python-gobject kurulu değil. Kur: pacman -S python-gobject")
    sys.exit(1)

# rivalcfg CLI aracının varlığını kontrol et
try:
    subprocess.run(["rivalcfg"], capture_output=True, timeout=5)
except FileNotFoundError:
    print("rivalcfg kurulu değil. Kur: pip install rivalcfg")
    sys.exit(1)

# Uygulama durumunu tutan tek global sözlük
app_state = {}

CSS = """
window {
    background: #0a0a0f;
}

.sidebar {
    background: #0d0d14;
    border-right: 1px solid #1e1e2e;
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
"""


def set_status(status_type, message):
    """Durum çubuğunu güncelle; GUI thread'inden çağrılmalıdır."""
    dot = app_state["status_dot"]
    label = app_state["status_label"]

    dot.get_style_context().remove_class("status-running")
    dot.get_style_context().remove_class("status-ok")
    dot.get_style_context().remove_class("status-error")
    dot.get_style_context().add_class(f"status-{status_type}")

    label.set_text(message)


def run_rivalcfg(args, on_done=None):
    """rivalcfg komutunu arka plan thread'inde çalıştır."""
    def target():
        GLib.idle_add(set_status, "running", "İşlem yapılıyor...")
        try:
            cmd = ["rivalcfg"]
            if app_state.get("no_save"):
                cmd.append("--no-save")
            cmd.extend(args)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                err = result.stderr.strip() if result.stderr.strip() else "Bilinmeyen hata"
                GLib.idle_add(set_status, "error", f"✗ Hata: {err}")
                if on_done:
                    GLib.idle_add(on_done, False, err)
            else:
                out = result.stdout.strip()
                GLib.idle_add(set_status, "ok", "✓ Tamamlandı")
                if on_done:
                    GLib.idle_add(on_done, True, out)
        except FileNotFoundError:
            msg = "rivalcfg kurulu değil. Kur: pip install rivalcfg"
            GLib.idle_add(set_status, "error", f"✗ Hata: {msg}")
            if on_done:
                GLib.idle_add(on_done, False, msg)
        except subprocess.TimeoutExpired:
            msg = "Zaman aşımı (10s)"
            GLib.idle_add(set_status, "error", f"✗ Hata: {msg}")
            if on_done:
                GLib.idle_add(on_done, False, msg)
        except Exception as e:
            msg = f"Beklenmeyen hata: {e}"
            GLib.idle_add(set_status, "error", f"✗ Hata: {msg}")
            if on_done:
                GLib.idle_add(on_done, False, msg)

    threading.Thread(target=target, daemon=True).start()


def rgba_to_hex(rgba):
    """Gdk.RGBA değerini # işaretsiz küçük harfli hex stringe çevirir."""
    r = int(rgba.red * 255)
    g = int(rgba.green * 255)
    b = int(rgba.blue * 255)
    return f"{r:02x}{g:02x}{b:02x}"


def create_dpi_page():
    """DPI ayarları sayfasını oluşturur."""
    page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    page.set_margin_top(24)
    page.set_margin_bottom(24)
    page.set_margin_start(24)
    page.set_margin_end(24)

    title = Gtk.Label(label="DPI Ayarları")
    title.get_style_context().add_class("page-title")
    title.set_halign(Gtk.Align.START)
    page.pack_start(title, False, False, 0)

    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    card.get_style_context().add_class("card")
    page.pack_start(card, True, True, 0)

    defaults = [400, 800, 1600, 3200, 6400]
    app_state["dpi_scales"] = []
    app_state["dpi_labels"] = []
    app_state["dpi_values"] = list(defaults)

    for i in range(5):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.set_margin_bottom(8)

        lbl = Gtk.Label(label=f"Preset {i + 1}")
        lbl.set_size_request(80, -1)
        lbl.set_halign(Gtk.Align.START)
        row.pack_start(lbl, False, False, 0)

        val_label = Gtk.Label(label=str(defaults[i]))
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
        scale.set_value(defaults[i])
        scale.set_hexpand(True)

        def on_dpi_changed(sc, idx=i, vl=val_label):
            v = int(sc.get_value())
            vl.set_text(str(v))
            app_state["dpi_values"][idx] = v

        scale.connect("value-changed", on_dpi_changed)
        row.pack_start(scale, True, True, 0)
        app_state["dpi_scales"].append(scale)

        card.pack_start(row, False, False, 0)

    btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    btn_row.set_halign(Gtk.Align.START)

    apply_btn = Gtk.Button(label="UYGULA")
    apply_btn.get_style_context().add_class("apply-btn")

    def on_apply_dpi(btn):
        vals = app_state["dpi_values"]
        arg = ",".join(str(v) for v in vals)
        run_rivalcfg(["--sensitivity", arg])

    apply_btn.connect("clicked", on_apply_dpi)
    btn_row.pack_start(apply_btn, False, False, 0)

    reset_btn = Gtk.Button(label="SIFIRLA")
    reset_btn.get_style_context().add_class("reset-btn")

    def on_reset_dpi(btn):
        defaults = [400, 800, 1600, 3200, 6400]
        for idx, val in enumerate(defaults):
            app_state["dpi_scales"][idx].set_value(val)

    reset_btn.connect("clicked", on_reset_dpi)
    btn_row.pack_start(reset_btn, False, False, 0)

    card.pack_start(btn_row, False, False, 0)

    return page


def create_polling_page():
    """Polling Rate sayfasını oluşturur."""
    page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    page.set_margin_top(24)
    page.set_margin_bottom(24)
    page.set_margin_start(24)
    page.set_margin_end(24)

    title = Gtk.Label(label="Polling Rate")
    title.get_style_context().add_class("page-title")
    title.set_halign(Gtk.Align.START)
    page.pack_start(title, False, False, 0)

    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    card.get_style_context().add_class("card")
    page.pack_start(card, True, True, 0)

    rates = [125, 250, 500, 1000]
    app_state["polling_hz"] = 1000
    group = None

    radio_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

    for hz in rates:
        if group is None:
            rb = Gtk.RadioButton(label=f"{hz} Hz")
            group = rb
            rb.set_active(hz == 1000)
        else:
            rb = Gtk.RadioButton(label=f"{hz} Hz", group=group)
            rb.set_active(hz == 1000)

        def on_polling_toggled(button, val=hz):
            if button.get_active():
                app_state["polling_hz"] = val
                ms = 1000.0 / val
                app_state["polling_display"].set_text(f"{val} Hz  →  {ms:.1f} ms")

        rb.connect("toggled", on_polling_toggled)
        radio_box.pack_start(rb, False, False, 0)

    card.pack_start(radio_box, False, False, 0)

    display = Gtk.Label(label="1000 Hz  →  1.0 ms")
    display.get_style_context().add_class("value-display")
    display.set_halign(Gtk.Align.START)
    card.pack_start(display, False, False, 0)
    app_state["polling_display"] = display

    apply_btn = Gtk.Button(label="UYGULA")
    apply_btn.get_style_context().add_class("apply-btn")
    apply_btn.set_halign(Gtk.Align.START)

    def on_apply_polling(btn):
        run_rivalcfg(["--polling-rate", str(app_state["polling_hz"])])

    apply_btn.connect("clicked", on_apply_polling)
    card.pack_start(apply_btn, False, False, 0)

    return page


def create_rgb_page():
    """RGB Aydınlatma sayfasını oluşturur."""
    page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    page.set_margin_top(24)
    page.set_margin_bottom(24)
    page.set_margin_start(24)
    page.set_margin_end(24)

    title = Gtk.Label(label="RGB Aydınlatma")
    title.get_style_context().add_class("page-title")
    title.set_halign(Gtk.Align.START)
    page.pack_start(title, False, False, 0)

    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    card.get_style_context().add_class("card")
    page.pack_start(card, True, True, 0)

    colors_title = Gtk.Label(label="RENKLER")
    colors_title.get_style_context().add_class("card-title")
    colors_title.set_halign(Gtk.Align.START)
    card.pack_start(colors_title, False, False, 0)

    app_state["z1_hex"] = "ff0000"
    app_state["z2_hex"] = "00ff00"
    app_state["z3_hex"] = "0000ff"
    app_state["z4_hex"] = "aa00ff"

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

        preview = Gtk.DrawingArea()
        preview.set_size_request(40, 24)
        preview.get_style_context().add_class("card")
        row.pack_start(preview, False, False, 0)

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

        color_btn.connect("color-set", on_color_set)
        return row

    card.pack_start(make_color_row("Z1 - Üst Şerit", "ff0000", "z1_hex"), False, False, 0)
    card.pack_start(make_color_row("Z2 - Orta Şerit", "00ff00", "z2_hex"), False, False, 0)
    card.pack_start(make_color_row("Z3 - Alt Şerit", "0000ff", "z3_hex"), False, False, 0)
    card.pack_start(make_color_row("Z4 - Logo", "aa00ff", "z4_hex"), False, False, 0)

    effect_title = Gtk.Label(label="EFEKT")
    effect_title.get_style_context().add_class("card-title")
    effect_title.set_halign(Gtk.Align.START)
    effect_title.set_margin_top(12)
    card.pack_start(effect_title, False, False, 0)

    effects = [
        ("steady", "steady"),
        ("breath", "breath"),
        ("breath-slow", "breath-slow"),
        ("breath-fast", "breath-fast"),
        ("rainbow-shift", "rainbow-shift"),
        ("rainbow-breath", "rainbow-breath"),
        ("disco", "disco")
    ]
    app_state["selected_effect"] = "steady"
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

        def on_effect_toggled(button, val=value):
            if button.get_active():
                app_state["selected_effect"] = val

        rb.connect("toggled", on_effect_toggled)
        eff_box.pack_start(rb, False, False, 0)

    card.pack_start(eff_box, False, False, 0)

    apply_btn = Gtk.Button(label="UYGULA")
    apply_btn.get_style_context().add_class("apply-btn")
    apply_btn.set_halign(Gtk.Align.START)
    apply_btn.set_margin_top(8)

    def on_apply_rgb(btn):
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
    """Buton eşleme sayfasını oluşturur."""
    page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    page.set_margin_top(24)
    page.set_margin_bottom(24)
    page.set_margin_start(24)
    page.set_margin_end(24)

    title = Gtk.Label(label="Buton Eşlemeleri")
    title.get_style_context().add_class("page-title")
    title.set_halign(Gtk.Align.START)
    page.pack_start(title, False, False, 0)

    content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
    page.pack_start(content, True, True, 0)

    # --- SOL PANEL ---
    left_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    left_card.set_size_request(280, -1)
    left_card.get_style_context().add_class("card")
    content.pack_start(left_card, False, False, 0)

    card_title = Gtk.Label(label="BUTON ATAMALARI")
    card_title.get_style_context().add_class("card-title")
    card_title.set_halign(Gtk.Align.START)
    left_card.pack_start(card_title, False, False, 0)

    button_options = [
        "button1", "button2", "button3", "button4", "button5",
        "button6", "dpi", "scrollup", "scrolldown", "disable"
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
    app_state["button_combos"] = {}

    labels = {
        "button1": "Sol Tık (B1)",
        "button2": "Sağ Tık (B2)",
        "button3": "Orta Tık (B3)",
        "button4": "Geri (B4)",
        "button5": "İleri (B5)",
        "button6": "DPI (B6)",
        "scrollup": "Scroll ↑",
        "scrolldown": "Scroll ↓",
    }

    for btn_name in ["button1", "button2", "button3", "button4", "button5", "button6", "scrollup", "scrolldown"]:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_margin_bottom(6)

        lbl = Gtk.Label(label=labels[btn_name])
        lbl.set_size_request(110, -1)
        lbl.set_xalign(0)
        row.pack_start(lbl, False, False, 0)

        combo = Gtk.ComboBoxText()
        for opt in button_options:
            combo.append_text(opt)
        combo.set_active(button_options.index(defaults[btn_name]))
        combo.set_hexpand(True)
        row.pack_start(combo, True, True, 0)
        app_state["button_combos"][btn_name] = combo

        def on_changed(widget, name=btn_name):
            app_state["button_mapping"][name] = widget.get_active_text()
            if app_state.get("redraw_buttons"):
                app_state["redraw_buttons"]()

        combo.connect("changed", on_changed)
        left_card.pack_start(row, False, False, 0)

    btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    btn_row.set_halign(Gtk.Align.START)
    btn_row.set_margin_top(8)

    apply_btn = Gtk.Button(label="UYGULA")
    apply_btn.get_style_context().add_class("apply-btn")

    def on_apply_buttons(btn):
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

    reset_btn = Gtk.Button(label="SIFIRLA")
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
        all_opts = ["button1", "button2", "button3", "button4", "button5", "button6", "dpi", "scrollup", "scrolldown", "disable"]
        for btn_name, combo in app_state["button_combos"].items():
            combo.set_active(all_opts.index(defaults[btn_name]))

    reset_btn.connect("clicked", on_reset_buttons)
    btn_row.pack_start(reset_btn, False, False, 0)

    left_card.pack_start(btn_row, False, False, 0)

    # --- SAĞ PANEL: FARE GÖRSELİ ---
    right_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    right_card.get_style_context().add_class("card")
    content.pack_start(right_card, True, True, 0)

    img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rival3.png")

    overlay = Gtk.Overlay()
    overlay.set_hexpand(True)
    overlay.set_vexpand(True)

    if os.path.exists(img_path):
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(img_path, 320, 320, True)
        image_widget = Gtk.Image.new_from_pixbuf(pixbuf)
        image_widget.set_halign(Gtk.Align.CENTER)
        image_widget.set_valign(Gtk.Align.CENTER)
        overlay.add(image_widget)
    else:
        fallback = Gtk.Label(label="rival3.png bulunamadı.")
        overlay.add(fallback)

    # Etiket overlay'i - DrawingArea sadece çizgiler ve etiketler için
    lines_area = Gtk.DrawingArea()
    lines_area.set_hexpand(True)
    lines_area.set_vexpand(True)
    lines_area.set_halign(Gtk.Align.FILL)
    lines_area.set_valign(Gtk.Align.FILL)
    # Fare olaylarını geçir
    lines_area.set_app_paintable(True)

    def draw_lines(widget, cr):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()

        # Tamamen şeffaf arkaplan
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()

        # Görselin widget içindeki konumu (320x320, ortalı)
        img_w = 320
        img_h = 320
        img_x = (w - img_w) / 2
        img_y = (h - img_h) / 2

        # Rival 3 buton pozisyonları (320x320 görsel üzerinde)
        btn_positions = {
            "button1": (img_x + 100, img_y + 90),
            "button2": (img_x + 220, img_y + 90),
            "button3": (img_x + 160, img_y + 70),
            "button4": (img_x + 75,  img_y + 170),
            "button5": (img_x + 75,  img_y + 140),
            "button6": (img_x + 160, img_y + 115),
        }

        btn_display_names = {
            "button1": "Sol Tık",
            "button2": "Sağ Tık",
            "button3": "Orta",
            "button4": "Geri",
            "button5": "İleri",
            "button6": "DPI",
        }

        # Etiketler sağ tarafa hizalı
        lw = 115
        lh = 20
        lx = img_x + img_w + 15

        label_ys = {
            "button3": img_y + 40,
            "button1": img_y + 70,
            "button6": img_y + 100,
            "button2": img_y + 130,
            "button5": img_y + 160,
            "button4": img_y + 190,
        }

        for btn_name, (bx, by) in btn_positions.items():
            assigned = app_state["button_mapping"].get(btn_name, btn_name)
            display_name = btn_display_names[btn_name]
            label_text = f"{display_name}: {assigned}"
            ly = label_ys[btn_name]

            # Çizgi
            cr.set_source_rgba(0.4, 0.6, 1.0, 0.7)
            cr.set_line_width(1.2)
            cr.move_to(bx, by)
            cr.line_to(lx, ly + lh / 2)
            cr.stroke()

            # Nokta
            cr.set_source_rgb(0.4, 0.6, 1.0)
            cr.arc(bx, by, 4, 0, 2 * math.pi)
            cr.fill()

            # Kutu
            cr.set_source_rgba(0.08, 0.14, 0.26, 0.95)
            cr.rectangle(lx, ly, lw, lh)
            cr.fill()
            cr.set_source_rgb(0.25, 0.40, 0.70)
            cr.set_line_width(1)
            cr.rectangle(lx, ly, lw, lh)
            cr.stroke()

            # Yazı
            cr.set_source_rgb(1, 1, 1)
            cr.select_font_face("monospace", 0, 0)
            cr.set_font_size(9)
            te = cr.text_extents(label_text)
            cr.move_to(lx + (lw - te[2]) / 2, ly + lh / 2 + te[3] / 2)
            cr.show_text(label_text)

        return False

    lines_area.connect("draw", draw_lines)
    overlay.add_overlay(lines_area)
    app_state["redraw_buttons"] = lambda: lines_area.queue_draw()

    right_card.pack_start(overlay, True, True, 0)

    return page


def create_devices_page():
    page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    page.set_margin_top(24)
    page.set_margin_bottom(24)
    page.set_margin_start(24)
    page.set_margin_end(24)

    title = Gtk.Label(label="Bağlı Cihazlar")
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
    app_state["devices_buffer"].set_text("Taramak için butona bas...")
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scrolled.set_min_content_height(200)
    scrolled.set_vexpand(True)
    scrolled.add(textview)
    card.pack_start(scrolled, True, True, 0)

    refresh_btn = Gtk.Button(label="YENİLE")
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
    """Hakkında sayfasını oluşturur."""
    page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    page.set_margin_top(24)
    page.set_margin_bottom(24)
    page.set_margin_start(24)
    page.set_margin_end(24)

    title = Gtk.Label(label="Hakkında")
    title.get_style_context().add_class("page-title")
    title.set_halign(Gtk.Align.START)
    page.pack_start(title, False, False, 0)

    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    card.get_style_context().add_class("card")
    page.pack_start(card, True, True, 0)

    text = (
        "SteelSeries Rival 3 için Linux GUI yapılandırma aracı.\n"
        "rivalcfg kütüphanesi üzerine inşa edilmiştir.\n\n"
        "Gereksinimler:\n"
        "  pip install rivalcfg\n"
        "  pacman -S python-gobject"
    )
    label = Gtk.Label(label=text)
    label.set_line_wrap(True)
    label.set_halign(Gtk.Align.START)
    label.set_valign(Gtk.Align.START)
    card.pack_start(label, False, False, 0)

    github_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
    github_box.set_halign(Gtk.Align.START)

    github_prefix = Gtk.Label(label="GitHub: ")
    github_prefix.set_halign(Gtk.Align.START)
    github_box.pack_start(github_prefix, False, False, 0)

    link_btn = Gtk.LinkButton(
        uri="https://github.com/MrGodzilla38/rivalcfg-gui",
        label="github.com/MrGodzilla38/rivalcfg-gui"
    )
    link_btn.set_halign(Gtk.Align.START)
    link_btn.set_relief(Gtk.ReliefStyle.NONE)
    github_box.pack_start(link_btn, False, False, 0)

    card.pack_start(github_box, False, False, 0)

    btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    btn_box.set_halign(Gtk.Align.START)

    check_btn = Gtk.Button(label="FAREYI KONTROL ET")
    check_btn.get_style_context().add_class("apply-btn")

    def on_check_mouse(btn):
        def on_detect(success, msg):
            if success and "184c" in msg:
                GLib.idle_add(set_status, "ok", "✓ Fare bağlı")
            else:
                GLib.idle_add(set_status, "error", "✗ Fare bulunamadı")

        def on_list(success, msg):
            GLib.idle_add(app_state["devices_buffer"].set_text, msg if msg else "Cihaz bulunamadı.")

        run_rivalcfg(["--print-debug"], on_detect)
        run_rivalcfg(["--list"], on_list)

    check_btn.connect("clicked", on_check_mouse)
    btn_box.pack_start(check_btn, False, False, 0)

    fw_btn = Gtk.Button(label="FİRMWARE SÜRÜMÜ")
    fw_btn.get_style_context().add_class("apply-btn")

    def on_firmware(btn):
        def cb(success, msg):
            if success:
                GLib.idle_add(set_status, "ok", f"✓ Firmware: {msg}")
            else:
                GLib.idle_add(set_status, "error", "✗ Fare takılı değil")
        run_rivalcfg(["--firmware-version"], cb)

    fw_btn.connect("clicked", on_firmware)
    btn_box.pack_start(fw_btn, False, False, 0)

    reset_btn = Gtk.Button(label="FABRIKA SIFIRLA")
    reset_btn.get_style_context().add_class("danger-btn")

    def on_factory_reset(btn):
        dialog = Gtk.MessageDialog(
            parent=app_state.get("window"),
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            message_format="Tüm ayarlar fabrika değerlerine döndürülecek. Emin misiniz?"
        )
        dialog.set_title("Fabrika Ayarlarına Sıfırla")
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.OK:
            def cb(success, msg):
                if not success:
                    GLib.idle_add(set_status, "error", "✗ Fare takılı değil")
            run_rivalcfg(["--reset"], cb)

    reset_btn.connect("clicked", on_factory_reset)
    btn_box.pack_start(reset_btn, False, False, 0)

    card.pack_start(btn_box, False, False, 0)

    return page


def create_window():
    """Ana pencereyi ve içeriğini oluşturur."""
    window = Gtk.Window(title="RivalCFG GUI")
    window.set_default_size(1280, 720)
    window.set_resizable(True)
    window.connect("destroy", Gtk.main_quit)

    # Pencere simgesi
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
    if os.path.exists(icon_path):
        icon_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_path, 128, 128, True)
        window.set_icon(icon_pixbuf)

    app_state["window"] = window

    # CSS uygula
    css_provider = Gtk.CssProvider()
    css_provider.load_from_data(CSS.encode('utf-8'))
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    window.add(vbox)

    # Ana yatay bölme
    main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    vbox.pack_start(main_box, True, True, 0)

    # Sol sidebar
    sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    sidebar.set_size_request(180, -1)
    sidebar.get_style_context().add_class("sidebar")
    sidebar.set_margin_top(16)
    sidebar.set_margin_bottom(16)
    sidebar.set_margin_start(16)
    sidebar.set_margin_end(16)
    main_box.pack_start(sidebar, False, False, 0)

    # Sidebar logo
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
    if os.path.exists(icon_path):
        logo_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_path, 100, 100, True)
        logo_img = Gtk.Image.new_from_pixbuf(logo_pixbuf)
        logo_img.set_margin_bottom(8)
        sidebar.pack_start(logo_img, False, False, 0)

    # Marka başlığı
    brand = Gtk.Label(label="RivalCFG GUI")
    brand.get_style_context().add_class("page-title")
    brand.set_margin_bottom(20)
    sidebar.pack_start(brand, False, False, 0)

    # Stack
    stack = Gtk.Stack()
    stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
    main_box.pack_start(stack, True, True, 0)
    app_state["stack"] = stack

    # Sayfaları oluştur ve ekle
    pages = [
        ("dpi", "DPI", create_dpi_page()),
        ("polling", "POLLING", create_polling_page()),
        ("rgb", "RGB", create_rgb_page()),
        ("buttons", "BUTONLAR", create_buttons_page()),
        ("devices", "CİHAZLAR", create_devices_page()),
        ("about", "HAKKINDA", create_about_page()),
    ]

    for name, title, page in pages:
        stack.add_named(page, name)

    # Navigasyon butonları
    app_state["nav_buttons"] = []

    def on_nav_clicked(button, page_name):
        for btn in app_state["nav_buttons"]:
            btn.get_style_context().remove_class("nav-active")
        button.get_style_context().add_class("nav-active")
        stack.set_visible_child_name(page_name)

    for i, (name, title, _) in enumerate(pages):
        btn = Gtk.Button(label=title)
        btn.get_style_context().add_class("nav-btn")
        if i == 0:
            btn.get_style_context().add_class("nav-active")
        btn.connect("clicked", on_nav_clicked, name)
        sidebar.pack_start(btn, False, False, 0)
        app_state["nav_buttons"].append(btn)

    # Status bar
    status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    status_bar.set_size_request(-1, 32)
    status_bar.get_style_context().add_class("status-bar")
    vbox.pack_end(status_bar, False, False, 0)

    dot = Gtk.Label(label="●")
    dot.get_style_context().add_class("status-running")
    status_bar.pack_start(dot, False, False, 0)
    app_state["status_dot"] = dot

    status_label = Gtk.Label(label="Başlatılıyor...")
    status_label.set_halign(Gtk.Align.START)
    status_bar.pack_start(status_label, False, False, 0)
    app_state["status_label"] = status_label

    app_state["no_save"] = False
    no_save_check = Gtk.CheckButton(label="Kaydetme (--no-save)")
    status_bar.pack_end(no_save_check, False, False, 0)

    def on_no_save_toggled(button):
        app_state["no_save"] = button.get_active()

    no_save_check.connect("toggled", on_no_save_toggled)

    # Başlangıçta fare durumunu kontrol et
    def startup_check():
        def cb(success, msg):
            if success and "184c" in msg:
                set_status("ok", "✓ Fare bağlı")
            else:
                set_status("error", "✗ Fare bulunamadı")
        run_rivalcfg(["--print-debug"], cb)

    GLib.idle_add(startup_check)

    window.show_all()


def main():
    create_window()
    Gtk.main()


main()
