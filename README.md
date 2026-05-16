# RivalCFG GUI

# 🇺🇸 English

A Linux desktop configuration tool for the SteelSeries Rival 3 mouse.

## What It Does

This application lets you configure your SteelSeries Rival 3 using the `rivalcfg` command-line tool:

- **DPI Settings** — 5 adjustable presets via sliders (200–8500, in 100-step increments)
- **Polling Rate** — 125 / 250 / 500 / 1000 Hz selection
- **RGB Lighting** — 4 independent zones (top strip, middle strip, bottom strip, logo) with 7 effects (steady, breath, breath-slow, breath-fast, rainbow-shift, rainbow-breath, disco)
- **Button Mapping** — remap all 8 buttons (left, right, middle, back, forward, DPI, scroll up/down)
- **Device Info** — list connected devices and check firmware version
- **Mouse Status** — real-time connection status in the status bar
- **Factory Reset** — restore all mouse settings to defaults

## Supported Devices

- SteelSeries Rival 3

> Note: Other SteelSeries devices may be supported by `rivalcfg`, but this GUI is currently tested only against the Rival 3 command set.

## Installation

### Automatic (Recommended)

An automated installer script is included. It detects your distribution, installs dependencies, copies the application system-wide, creates a desktop entry, and sets up a `rivalcfg-gui` command.

```bash
chmod +x install.sh
sudo ./install.sh
```

**What it does:**
- Detects your distro (Arch, Debian, Fedora, openSUSE and derivatives)
- Installs required packages (`rivalcfg`, `python-gobject`, `python-cairo`)
- Copies files to `/usr/local/share/rivalcfg-gui/`
- Creates symlink at `/usr/local/bin/rivalcfg-gui`
- Creates desktop entry at `/usr/share/applications/rivalcfg-gui.desktop`

**Uninstall:**
```bash
sudo ./install.sh --uninstall
```

### Manual

```bash
# 1. Install dependencies

# rivalcfg (Arch via AUR)
yay -S rivalcfg

# rivalcfg (Debian/Ubuntu)
sudo apt install rivalcfg

# python-gobject & python-cairo (Arch)
sudo pacman -S python-gobject python-cairo

# python-gobject & python-cairo (Debian/Ubuntu)
sudo apt install python3-gi python3-cairo

# 2. Run
python rivalcfg_gui.py
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

# 🇹🇷 Türkçe

SteelSeries Rival 3 faresi için Linux masaüstü yapılandırma aracı.

## Ne İşe Yarar

Bu uygulama, `rivalcfg` komut satırı aracını kullanarak SteelSeries Rival 3 faresinin aşağıdaki ayarlarını yapmanızı sağlar:

- **DPI Ayarları** — 5 preset değer, slider ile 200–8500 arası (100'lük adımlar)
- **Polling Rate** — 125 / 250 / 500 / 1000 Hz seçimi
- **RGB Aydınlatma** — 4 bağımsız bölge (üst şerit, orta şerit, alt şerit, logo), 7 efekt (steady, breath, breath-slow, breath-fast, rainbow-shift, rainbow-breath, disco)
- **Buton Eşlemeleri** — 8 butonun tamamını yeniden eşleme (sol, sağ, orta, geri, ileri, DPI, scroll yukarı/aşağı)
- **Cihaz Bilgisi** — bağlı cihazları listeleme, firmware sürümü sorgulama
- **Fare Durumu** — durum çubuğunda anlık bağlantı kontrolü
- **Fabrika Sıfırlama** — tüm fare ayarlarını varsayılana döndürme

## Desteklenen Cihazlar

- SteelSeries Rival 3

> Not: Diğer SteelSeries cihazlar `rivalcfg` tarafından destekleniyor olabilir, ancak bu GUI şu an yalnızca Rival 3 komut setiyle test edilmiştir.

## Kurulum

### Otomatik Kurulum (Tavsiye Edilen)

Projeye dahil edilen `install.sh` scripti, dağıtımınızı algılayıp bağımlılıkları kurar, uygulamayı sistem geneline kopyalar, masaüstü kısayolu oluşturur ve `rivalcfg-gui` komutunu kullanıma sunar.

```bash
chmod +x install.sh
sudo ./install.sh
```

**Yaptıkları:**
- Dağıtımınızı algılar (Arch, Debian, Fedora, openSUSE ve türevleri)
- Gerekli paketleri kurar (`rivalcfg`, `python-gobject`, `python-cairo`)
- Dosyaları `/usr/local/share/rivalcfg-gui/` dizinine kopyalar
- `/usr/local/bin/rivalcfg-gui` sembolik bağı oluşturur
- `/usr/share/applications/rivalcfg-gui.desktop` kısayolunu oluşturur

**Kaldırma:**
```bash
sudo ./install.sh --uninstall
```

### Manuel Kurulum

```bash
# 1. Bağımlılıkları yükleyin

# rivalcfg (Arch - AUR)
yay -S rivalcfg

# rivalcfg (Debian/Ubuntu)
sudo apt install rivalcfg

# python-gobject & python-cairo (Arch)
sudo pacman -S python-gobject python-cairo

# python-gobject & python-cairo (Debian/Ubuntu)
sudo apt install python3-gi python3-cairo

# 2. Çalıştırın
python rivalcfg_gui.py
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
