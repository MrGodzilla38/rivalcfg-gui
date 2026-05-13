# RivalCFG GUI

# 🇺🇸 English

A Linux desktop configuration tool for the SteelSeries Rival 3 mouse.

## What It Does

This application lets you configure your SteelSeries Rival 3 using the `rivalcfg` command-line tool:

- **DPI:** Adjust 5 preset values via slider (200–8500, in 100-step increments)
- **Polling Rate:** Choose 125 / 250 / 500 / 1000 Hz
- **RGB Lighting:** Set logo and wheel colors, and select light effects (steady, breath, breath-slow, rainbow-shift, disco)
- **Reset All Settings:** Restore mouse factory defaults

## Supported Devices

- SteelSeries Rival 3

> Note: Other SteelSeries devices may be supported by `rivalcfg`, but this GUI is currently tested only against the Rival 3 command set.

## Installation

### 1. Install dependencies

```bash
# rivalcfg 
yay -S install rivalcfg

# python-gobject (GTK3 bindings)
# Arch Linux / Manjaro:
pacman -S python-gobject python-cairo

# Debian / Ubuntu:
# sudo apt install python3-gi python3-cairo
```

### 2. Run the application

```bash
python rivalcfg_gui.py
```

If no mouse is connected or `rivalcfg` is not found, the application will exit immediately with an error message.

## Requirements

- Python 3
- GTK3
- python-gobject (`gi`)
- python-cairo (`cairo`)
- `rivalcfg` command-line tool

# 🇹🇷 Türkçe

SteelSeries Rival 3 faresi için Linux masaüstü yapılandırma aracı.

## Ne İşe Yarar

Bu uygulama, `rivalcfg` komut satırı aracını kullanarak SteelSeries Rival 3 faresinin aşağıdaki ayarlarını yapmanızı sağlar:

- **DPI:** 5 adet preset değerini slider ile ayarlayın (200–8500 arası, 100'lük adımlarla)
- **Polling Rate:** 125 / 250 / 500 / 1000 Hz seçimi
- **RGB Aydınlatma:** Logo ve tekerlek renkleri, ışık efekti (steady, breath, breath-slow, rainbow-shift, disco)
- **Tüm Ayarları Sıfırlama:** Fareyi fabrika ayarlarına döndürme

## Desteklenen Cihazlar

- SteelSeries Rival 3

> Not: Diğer SteelSeries cihazlar `rivalcfg` tarafından destekleniyor olabilir, ancak bu GUI şu an yalnızca Rival 3 komut setiyle test edilmiştir.

## Kurulum

### 1. Bağımlılıkları yükleyin

```bash
# rivalcfg
yay -S rivalcfg

# python-gobject (GTK3 bağlamları)
# Arch Linux / Manjaro:
pacman -S python-gobject python-cairo

# Debian / Ubuntu:
# sudo apt install python3-gi python3-cairo
```

### 2. Uygulamayı çalıştırın

```bash
python rivalcfg_gui.py
```

Fare bağlı değilse veya `rivalcfg` bulunamazsa uygulama başlangıçta hata vererek kapanacaktır.

## Gereksinimler

- Python 3
- GTK3
- python-gobject (`gi`)
- python-cairo (`cairo`)
- `rivalcfg` komut satırı aracı
