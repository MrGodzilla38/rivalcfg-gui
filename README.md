# RivalCFG GUI

# 🇺🇸 English

A Linux desktop configuration tool for SteelSeries mice (via the `rivalcfg` CLI).

## What It Does

This application lets you configure your SteelSeries mouse using the `rivalcfg` command-line tool:

- **DPI Settings** — 5 adjustable presets via sliders (200–8500, in 100-step increments)
- **Polling Rate** — 125 / 250 / 500 / 1000 Hz selection
- **RGB Lighting** — 4 independent zones (top strip, middle strip, bottom strip, logo) with 7 effects (steady, breath, breath-slow, breath-fast, rainbow-shift, rainbow-breath, disco)
- **Button Mapping** — remap all 8 buttons (left, right, middle, back, forward, DPI, scroll up/down)
- **Device Info** — list connected devices and check firmware version
- **Mouse Status** — real-time connection status in the status bar
- **Factory Reset** — restore all mouse settings to defaults

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

If no mouse is connected or `rivalcfg` is not found, the application will exit immediately with an error message.

## Requirements

| Package | Purpose |
|---------|---------|
| Python 3 | Runtime |
| GTK3 | UI framework |
| python-gobject (`gi`) | Python GTK3 bindings |
| python-cairo (`cairo`) | Python Cairo bindings |
| `rivalcfg` | SteelSeries CLI tool |

## LICENSE
GPL-3.0-or-later

# 🇹🇷 Türkçe

SteelSeries fareler için Linux masaüstü yapılandırma aracı (`rivalcfg` CLI üzerinden).

## Ne İşe Yarar

Bu uygulama, `rivalcfg` komut satırı aracını kullanarak SteelSeries farenizin aşağıdaki ayarlarını yapmanızı sağlar:

- **DPI Ayarları** — 5 preset değer, slider ile 200–8500 arası (100'lük adımlar)
- **Polling Rate** — 125 / 250 / 500 / 1000 Hz seçimi
- **RGB Aydınlatma** — 4 bağımsız bölge (üst şerit, orta şerit, alt şerit, logo), 7 efekt (steady, breath, breath-slow, breath-fast, rainbow-shift, rainbow-breath, disco)
- **Buton Eşlemeleri** — 8 butonun tamamını yeniden eşleme (sol, sağ, orta, geri, ileri, DPI, scroll yukarı/aşağı)
- **Cihaz Bilgisi** — bağlı cihazları listeleme, firmware sürümü sorgulama
- **Fare Durumu** — durum çubuğunda anlık bağlantı kontrolü
- **Fabrika Sıfırlama** — tüm fare ayarlarını varsayılana döndürme

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

Fare bağlı değilse veya `rivalcfg` bulunamazsa uygulama başlangıçta hata vererek kapanacaktır.

## Gereksinimler

| Paket | Amaç |
|-------|------|
| Python 3 | Çalışma ortamı |
| GTK3 | Arayüz iskeleti |
| python-gobject (`gi`) | Python GTK3 bağlantısı |
| python-cairo (`cairo`) | Python Cairo bağlantısı |
| `rivalcfg` | SteelSeries CLI aracı |
