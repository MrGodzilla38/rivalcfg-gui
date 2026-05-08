#!/usr/bin/env python3

# GTK3 bağımlılığı kontrolü
import sys
import subprocess
import threading

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, Gdk, GLib
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
            result = subprocess.run(
                ["rivalcfg"] + args,
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

    # Bölüm A — Renkler
    colors_title = Gtk.Label(label="RENKLER")
    colors_title.get_style_context().add_class("card-title")
    colors_title.set_halign(Gtk.Align.START)
    card.pack_start(colors_title, False, False, 0)

    app_state["logo_hex"] = "ff0000"
    app_state["wheel_hex"] = "00ffff"

    def make_color_row(label_text, default_hex, key):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.set_margin_top(4)

        lbl = Gtk.Label(label=label_text)
        lbl.set_size_request(80, -1)
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

    card.pack_start(make_color_row("Logo", "ff0000", "logo_hex"), False, False, 0)
    card.pack_start(make_color_row("Tekerlek", "00ffff", "wheel_hex"), False, False, 0)

    # Bölüm B — Efekt
    effect_title = Gtk.Label(label="EFEKT")
    effect_title.get_style_context().add_class("card-title")
    effect_title.set_halign(Gtk.Align.START)
    effect_title.set_margin_top(12)
    card.pack_start(effect_title, False, False, 0)

    effects = [
        ("steady", "steady"),
        ("breath", "breath"),
        ("breath-slow", "breath-slow"),
        ("rainbow-shift", "rainbow-shift"),
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

    # Uygula butonu
    apply_btn = Gtk.Button(label="UYGULA")
    apply_btn.get_style_context().add_class("apply-btn")
    apply_btn.set_halign(Gtk.Align.START)
    apply_btn.set_margin_top(8)

    def on_apply_rgb(btn):
        logo_hex = app_state["logo_hex"]
        wheel_hex = app_state["wheel_hex"]
        effect = app_state["selected_effect"]

        def after_logo(success, msg):
            if not success:
                return
            run_rivalcfg(["--wheel-color", wheel_hex], after_wheel)

        def after_wheel(success, msg):
            if not success:
                return
            run_rivalcfg(["--light-effect", effect])

        run_rivalcfg(["--logo-color", logo_hex], after_logo)

    apply_btn.connect("clicked", on_apply_rgb)
    card.pack_start(apply_btn, False, False, 0)

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
        "  pacman -S python-gobject\n\n"
        "GitHub: github.com/[kullanıcıadı]/rivalcfg-gui"
    )
    label = Gtk.Label(label=text)
    label.set_line_wrap(True)
    label.set_halign(Gtk.Align.START)
    label.set_valign(Gtk.Align.START)
    card.pack_start(label, True, True, 0)

    check_btn = Gtk.Button(label="FAREYI KONTROL ET")
    check_btn.get_style_context().add_class("apply-btn")
    check_btn.set_halign(Gtk.Align.START)

    def on_check_mouse(btn):
        def cb(success, msg):
            if success:
                GLib.idle_add(set_status, "ok", f"✓ Fare bağlı: {msg}")
        run_rivalcfg(["--list"], cb)

    check_btn.connect("clicked", on_check_mouse)
    card.pack_start(check_btn, False, False, 0)

    return page


def create_window():
    """Ana pencereyi ve içeriğini oluşturur."""
    window = Gtk.Window(title="RivalCFG GUI — Rival 3")
    window.set_default_size(860, 580)
    window.set_resizable(True)
    window.connect("destroy", Gtk.main_quit)

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

    # Marka başlığı
    brand = Gtk.Label(label="RIVAL 3")
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

    # Başlangıçta fare durumunu kontrol et
    def startup_check():
        def cb(success, msg):
            if success:
                set_status("ok", f"✓ Fare bağlı: {msg}")
            else:
                set_status("error", "✗ Fare bulunamadı")
        run_rivalcfg(["--list"], cb)

    GLib.idle_add(startup_check)

    window.show_all()


def main():
    create_window()
    Gtk.main()


main()
