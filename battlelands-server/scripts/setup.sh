#!/bin/bash
# Auto-install all dependencies for Battlelands Private Server
# Tested on Linux Mint / Ubuntu 24.04

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err() { echo -e "${RED}[✗]${NC} $1"; }

ANDROID_HOME="${ANDROID_HOME:-$HOME/android-sdk}"
SUDO_CMD=""

# Check if sudo is available
if command -v sudo &> /dev/null; then
    SUDO_CMD="sudo"
fi

echo "=========================================="
echo " Battlelands Private Server - Setup"
echo "=========================================="
echo ""

# --- Java ---
echo "--- Java ---"
if command -v java &> /dev/null; then
    log "Java $(java -version 2>&1 | head -1)"
else
    warn "Java not found, installing OpenJDK 17..."
    $SUDO_CMD apt-get install -y openjdk-17-jdk
    log "Java installed"
fi

# --- Python packages ---
echo ""
echo "--- Python ---"
if command -v python3 &> /dev/null; then
    log "Python $(python3 --version)"
else
    err "Python3 not found. Install it first."
    exit 1
fi

# Create venv if not exists
VENV_DIR="$(dirname "$0")/../venv"
if [ ! -d "$VENV_DIR" ]; then
    $SUDO_CMD apt-get install -y python3-venv python3-pip
    python3 -m venv "$VENV_DIR"
    log "Virtual environment created"
fi

source "$VENV_DIR/bin/activate"
pip install flask flask-cors gunicorn -q
log "Python dependencies installed"

# --- Git ---
echo ""
echo "--- Git ---"
if command -v git &> /dev/null; then
    log "Git $(git --version)"
else
    $SUDO_CMD apt-get install -y git
    log "Git installed"
fi

# --- Android SDK ---
echo ""
echo "--- Android SDK ---"
if [ -d "$ANDROID_HOME/cmdline-tools/latest" ]; then
    log "Android SDK cmdline-tools found"
else
    mkdir -p "$ANDROID_HOME"
    cd /tmp
    warn "Downloading Android cmdline-tools..."
    wget -q "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip" -O cmdline-tools.zip
    unzip -q cmdline-tools.zip
    mkdir -p "$ANDROID_HOME/cmdline-tools"
    mv cmdline-tools "$ANDROID_HOME/cmdline-tools/latest"
    rm cmdline-tools.zip
    log "Android cmdline-tools installed"
fi

export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"

# Accept licenses + install packages
yes | $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager --licenses > /dev/null 2>&1 || true

echo ""
echo "--- Android SDK Packages ---"
PACKAGES="platform-tools emulator platforms;android-30"

# Install x86 (32-bit) system image (compatible with CPUs without AVX)
if [ ! -d "$ANDROID_HOME/system-images/android-30/google_apis/x86" ]; then
    PACKAGES="$PACKAGES system-images;android-30;google_apis;x86"
fi

$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager $PACKAGES 2>&1 | tail -3
log "Android SDK packages installed"

# Create AVD if not exists
if ! $ANDROID_HOME/emulator/emulator -list-avds 2>/dev/null | grep -q battlelands; then
    echo "no" | $ANDROID_HOME/cmdline-tools/latest/bin/avdmanager create avd \
        -n battlelands \
        -k "system-images;android-30;google_apis;x86" \
        -d pixel_6 -f
    log "AVD 'battlelands' created"
else
    log "AVD 'battlelands' already exists"
fi

# --- Add to PATH ---
BASHRC="$HOME/.bashrc"
if ! grep -q "ANDROID_HOME" "$BASHRC" 2>/dev/null; then
    cat >> "$BASHRC" << 'EOF'

# Android SDK
export ANDROID_HOME=$HOME/android-sdk
export PATH=$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH
EOF
    log "Added Android SDK to ~/.bashrc"
fi

echo ""
echo "=========================================="
echo -e "${GREEN} Setup complete!${NC}"
echo ""
echo "Start developing:"
echo "  cd battlelands-server && source venv/bin/activate"
echo "  python app.py"
echo ""
echo "Start the emulator:"
echo "  battlelands-server/scripts/start-emulator.sh"
echo ""
echo "Install the game:"
echo "  battlelands-server/scripts/install-game.sh"
echo "=========================================="
