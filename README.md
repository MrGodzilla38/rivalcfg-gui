# RivalCFG GUI
<img width="1291" height="750" alt="image" src="https://github.com/user-attachments/assets/98d0daf0-7061-481e-a4a7-ab4bcfa5f7a6" />

# 🇺🇸 English

A Linux desktop configuration tool for SteelSeries mice (via the `rivalcfg` CLI).

## Features

- **DPI Settings** — 5 adjustable presets via sliders (200–8500, in 100-step increments)
- **Polling Rate** — 125 / 250 / 500 / 1000 Hz selection
- **RGB Lighting** — 4 independent zones (top strip, middle strip, bottom strip, logo) with 7 effects (steady, breath, breath-slow, breath-fast, rainbow-shift, rainbow-breath, disco)
- **Button Mapping** — remap all 8 buttons (left, right, middle, back, forward, DPI, scroll up/down) with an interactive mouse diagram
- **Auto-Clicker** — software auto-clicker with configurable CPS (1–50), trigger key (keyboard or mouse), toggle/hold modes, and toggle key shortcut
- **Profiles** — save, load, rename, and delete named profiles containing all settings
- **Auto-Apply** — optionally apply settings immediately on change
- **Device Info** — list connected devices and check firmware version
- **Mouse Status** — real-time connection status in the status bar
- **Language Switching** — switch UI language at runtime
- **Accent Color** — customizable UI accent color
- **Factory Reset** — restore all mouse settings to defaults
- **Startup Minimize** — option to launch minimized to system tray
- **Logging** — daily rotating logs kept for 7 days in `~/.config/rivalcfg-gui/logs/`

## Language Support

| Language | Code |
|----------|------|
| English (reference) | `en` |
| German | `de` |
| Spanish | `es` |
| French | `fr` |
| Italian | `it` |
| Polish | `pl` |
| Portuguese (Brazil) | `pt_BR` |
| Russian | `ru` |
| Turkish | `tr` |
| Chinese (Simplified) | `zh_CN` |

To contribute a new translation, copy `locales/en/LC_MESSAGES/rivalcfg_gui.po`, translate the strings, and submit a pull request.

## Supported Devices

Works with all devices supported by `rivalcfg` — Rival 100/300/500/600/700 series,
Sensei, Kinzu, Aerox, Prime, and more.

> Full list: https://github.com/flozz/rivalcfg#supported-devices
>
> Currently designed and tested against the Rival 3.
> Feature availability (RGB zones, button count, polling rates) depends on device.

## Installation

### Arch Linux (AUR)

```bash
yay -S rivalcfg-gui
```

**Upgrade:**
```bash
yay -Suy rivalcfg-gui
```

**Uninstall:**
```bash
yay -Rns rivalcfg-gui
```

## Requirements

| Package | Purpose |
|---------|---------|
| Python 3 | Runtime |
| GTK3 | UI framework |
| python-gobject (`gi`) | Python GTK3 bindings |
| python-cairo (`cairo`) | Python Cairo bindings |
| `rivalcfg` | SteelSeries CLI tool |
| python-evdev (`evdev`) | Linux input event monitoring |
| python-pynput (`pynput`) | Mouse control and event capture |
| python-xlib (`Xlib`) | X11 keycode resolution |

If no mouse is connected or `rivalcfg` is not found, the application will exit immediately with an error message.

## License
GPL-3.0-or-later

# 🇹🇷 Türkçe

SteelSeries fareler için Linux masaüstü yapılandırma aracı (`rivalcfg` CLI üzerinden).

## Özellikler

- **DPI Ayarları** — 5 preset değer, slider ile 200–8500 arası (100'lük adımlar)
- **Polling Rate** — 125 / 250 / 500 / 1000 Hz seçimi
- **RGB Aydınlatma** — 4 bağımsız bölge (üst şerit, orta şerit, alt şerit, logo), 7 efekt (steady, breath, breath-slow, breath-fast, rainbow-shift, rainbow-breath, disco)
- **Buton Eşlemeleri** — 8 butonun tamamını yeniden eşleme (sol, sağ, orta, geri, ileri, DPI, scroll yukarı/aşağı), etkileşimli fare diyagramı ile
- **Otomatik Tıklayıcı** — yapılandırılabilir CPS (1–50), tetik tuşu (klavye/fare), toggle/hold modları ve kısayol tuşu ile yazılım tıklayıcı
- **Profiller** — tüm ayarları içeren profilleri kaydetme, yükleme, yeniden adlandırma ve silme
- **Otomatik Uygula** — değişiklikleri anında fareye uygulama seçeneği
- **Cihaz Bilgisi** — bağlı cihazları listeleme, firmware sürümü sorgulama
- **Fare Durumu** — durum çubuğunda anlık bağlantı kontrolü
- **Dil Değiştirme** — çalışma anında arayüz dilini değiştirme
- **Vurgu Rengi** — özelleştirilebilir arayüz vurgu rengi
- **Fabrika Sıfırlama** — tüm fare ayarlarını varsayılana döndürme
- **Küçültülmüş Başlatma** — sistem tepsisine küçültülmüş olarak başlatma seçeneği
- **Günlük Kaydı** — `~/.config/rivalcfg-gui/logs/` dizininde 7 günlük döner günlükler

## Dil Desteği

| Dil | Kod |
|-----|-----|
| İngilizce (referans) | `en` |
| Almanca | `de` |
| İspanyolca | `es` |
| Fransızca | `fr` |
| İtalyanca | `it` |
| Lehçe | `pl` |
| Portekizce (Brezilya) | `pt_BR` |
| Rusça | `ru` |
| Türkçe | `tr` |
| Çince (Basitleştirilmiş) | `zh_CN` |

Yeni bir çeviri eklemek için `locales/en/LC_MESSAGES/rivalcfg_gui.po` dosyasını kopyalayın, dizeleri çevirin ve bir pull request gönderin.

## Desteklenen Cihazlar

`rivalcfg` tarafından desteklenen tüm cihazlarla çalışır — Rival 100/300/500/600/700
serileri, Sensei, Kinzu, Aerox, Prime ve daha fazlası.

> Tam liste: https://github.com/flozz/rivalcfg#supported-devices
>
> Şu an Rival 3 ile tasarlanmış ve test edilmiştir.
> Özellik kullanılabilirliği (RGB bölgeleri, buton sayısı, polling rate) cihaza göre değişir.

## Kurulum

### Arch Linux (AUR)

```bash
yay -S rivalcfg-gui
```

**Güncelleme:**
```bash
yay -Suy rivalcfg-gui
```

**Kaldırma:**
```bash
yay -Rns rivalcfg-gui
```

## Gereksinimler

| Paket | Amaç |
|-------|------|
| Python 3 | Çalışma ortamı |
| GTK3 | Arayüz iskeleti |
| python-gobject (`gi`) | Python GTK3 bağlantısı |
| python-cairo (`cairo`) | Python Cairo bağlantısı |
| `rivalcfg` | SteelSeries CLI aracı |
| python-evdev (`evdev`) | Linux girdi olay izleme |
| python-pynput (`pynput`) | Fare kontrolü ve olay yakalama |
| python-xlib (`Xlib`) | X11 tuş kodu çözümleme |

Fare bağlı değilse veya `rivalcfg` bulunamazsa uygulama başlangıçta hata vererek kapanacaktır.

## Lisans
GPL-3.0-or-later
