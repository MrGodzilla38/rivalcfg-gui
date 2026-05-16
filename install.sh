#!/bin/bash

# RivalCFG GUI - Automatic Installer
# Installs the RivalCFG GUI application system-wide

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

INSTALL_DIR="/usr/local/share/rivalcfg-gui"
BIN_LINK="/usr/local/bin/rivalcfg-gui"
DESKTOP_FILE="/usr/share/applications/rivalcfg-gui.desktop"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

print_banner() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║              RivalCFG GUI - Installer                  ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_info() {
    echo -e "${YELLOW}[i]${NC} $1"
}

print_ok() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_info "Requesting root privileges..."
        exec sudo bash "$0" "$@"
    fi
}

detect_distro() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        DISTRO="$ID"
        DISTRO_VERSION="$VERSION_ID"
        DISTRO_LIKE="$ID_LIKE"
    elif type lsb_release &>/dev/null; then
        DISTRO="$(lsb_release -si | tr '[:upper:]' '[:lower:]')"
        DISTRO_VERSION="$(lsb_release -sr)"
        DISTRO_LIKE=""
    else
        print_error "Could not detect Linux distribution."
        exit 1
    fi

    # Normalize: use ID_LIKE to determine package manager family
    if [[ -z "$DISTRO_LIKE" ]]; then
        DISTRO_FAMILY="$DISTRO"
    elif [[ "$DISTRO_LIKE" == *"arch"* ]]; then
        DISTRO_FAMILY="arch"
    elif [[ "$DISTRO_LIKE" == *"debian"* ]]; then
        DISTRO_FAMILY="debian"
    elif [[ "$DISTRO_LIKE" == *"fedora"* ]]; then
        DISTRO_FAMILY="fedora"
    elif [[ "$DISTRO_LIKE" == *"suse"* ]]; then
        DISTRO_FAMILY="suse"
    else
        DISTRO_FAMILY="$DISTRO"
    fi

    print_ok "Detected: $DISTRO $DISTRO_VERSION (family: $DISTRO_FAMILY)"
}

install_deps() {
    print_info "Installing dependencies..."

    case "$DISTRO_FAMILY" in
        arch)
            pacman -Syu --noconfirm
            pacman -S --noconfirm python python-pip python-gobject python-cairo
            if ! pacman -Qi rivalcfg &>/dev/null; then
                if command -v yay &>/dev/null; then
                    yay -S --noconfirm rivalcfg
                elif command -v paru &>/dev/null; then
                    paru -S --noconfirm rivalcfg
                else
                    print_error "rivalcfg is in AUR. Install yay or paru first."
                    exit 1
                fi
            fi
            ;;
        debian)
            apt update
            apt install -y python3 python3-pip python3-gi python3-cairo
            if ! dpkg -l rivalcfg &>/dev/null; then
                print_info "rivalcfg not found in repos, installing via pip..."
                pip3 install rivalcfg
            fi
            ;;
        fedora)
            dnf install -y python3 python3-gobject python3-cairo python3-pip
            if ! rpm -q rivalcfg &>/dev/null; then
                print_info "rivalcfg not found in repos, installing via pip..."
                pip3 install rivalcfg
            fi
            ;;
        suse)
            zypper install -y python3 python3-gobject python3-cairo python3-pip
            pip3 install rivalcfg
            ;;
        *)
            print_error "Unsupported distribution: $DISTRO (family: $DISTRO_FAMILY)"
            echo "Supported: Arch Linux (and derivatives), Debian/Ubuntu (and derivatives), Fedora, openSUSE"
            exit 1
            ;;
    esac

    print_ok "Dependencies installed."
}

install_files() {
    print_info "Creating install directory..."
    mkdir -p "$INSTALL_DIR"

    print_info "Copying files..."
    cp "$SCRIPT_DIR/rivalcfg_gui.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/logo.png" "$INSTALL_DIR/"
    if [[ -f "$SCRIPT_DIR/rival3.png" ]]; then
        cp "$SCRIPT_DIR/rival3.png" "$INSTALL_DIR/"
    fi
    chmod +x "$INSTALL_DIR/rivalcfg_gui.py"
    print_ok "Files copied to $INSTALL_DIR"

    print_info "Creating symlink..."
    ln -sf "$INSTALL_DIR/rivalcfg_gui.py" "$BIN_LINK"
    print_ok "Symlink created: $BIN_LINK"

    print_info "Creating desktop entry..."
    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=RivalCFG GUI
Comment=SteelSeries mouse configuration tool
Exec=$INSTALL_DIR/rivalcfg_gui.py
Icon=$INSTALL_DIR/logo.png
Terminal=false
Categories=Utility;Settings;
StartupWMClass=rivalcfg_gui.py
EOF
    print_ok "Desktop entry created: $DESKTOP_FILE"
}

uninstall() {
    print_info "Removing desktop entry..."
    rm -f "$DESKTOP_FILE"
    print_ok "Removed: $DESKTOP_FILE"

    print_info "Removing symlink..."
    rm -f "$BIN_LINK"
    print_ok "Removed: $BIN_LINK"

    print_info "Removing install directory..."
    rm -rf "$INSTALL_DIR"
    print_ok "Removed: $INSTALL_DIR"

    echo ""
    echo -e "${GREEN}RivalCFG GUI has been uninstalled.${NC}"
    exit 0
}

show_help() {
    echo "Usage: ./install.sh [OPTION]"
    echo ""
    echo "Options:"
    echo "  --uninstall    Remove RivalCFG GUI from the system"
    echo "  --help         Show this help message"
    echo ""
    echo "Without any option, the script installs RivalCFG GUI."
    exit 0
}

main() {
    case "${1:-}" in
        --uninstall)
            check_root "$@"
            print_banner
            uninstall
            ;;
        --help)
            print_banner
            show_help
            ;;
        "")
            check_root "$@"
            print_banner
            print_info "Starting installation..."
            echo ""
            detect_distro
            install_deps
            install_files
            echo ""
            print_ok "Installation complete!"
            echo -e "  Run:  ${CYAN}rivalcfg-gui${NC}"
            echo ""

            read -p "$(echo -e "${YELLOW}Launch RivalCFG GUI now? (y/N): ${NC}")" -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                print_info "Launching..."
                exec "$INSTALL_DIR/rivalcfg_gui.py"
            fi
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information."
            exit 1
            ;;
    esac
}

main "$@"
