#!/usr/bin/env bash
# BeatViz one-command installer — desktop + CLI deps (python3, pillow, ffmpeg).
# Idempotent: safe to run repeatedly. OS-detect: apt / dnf / pacman / brew.
set -u

BOLD="\033[1m"; GREEN="\033[32m"; RED="\033[31m"; YEL="\033[33m"; CYAN="\033[36m"; OFF="\033[0m"
ok()   { echo -e "${GREEN}✓${OFF} $1 | $2"; }
info() { echo -e "${CYAN}→${OFF} $1 | $2"; }
warn() { echo -e "${YEL}!${OFF} $1 | $2"; }

SUDO=""
if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1; then SUDO="sudo"; fi

detect_os() {
  if command -v apt-get >/dev/null 2>&1; then echo apt
  elif command -v dnf >/dev/null 2>&1; then echo dnf
  elif command -v yum >/dev/null 2>&1; then echo yum
  elif command -v pacman >/dev/null 2>&1; then echo pacman
  elif command -v brew >/dev/null 2>&1; then echo brew
  else echo unknown; fi
}

pkg_install() {
  local os="$1"; shift
  case "$os" in
    apt)   $SUDO apt-get update -y && $SUDO apt-get install -y "$@" ;;
    dnf)   $SUDO dnf install -y "$@" ;;
    yum)   $SUDO yum install -y "$@" ;;
    pacman)$SUDO pacman -Sy --noconfirm "$@" ;;
    brew)  brew install "$@" ;;
    *)     warn "cannot auto-install ($os)" | "نمی‌توان خودکار نصب کرد"; return 1 ;;
  esac
}

OS=$(detect_os)
info "detected OS/package manager" | "سیستم تشخیص داده شد: $OS"

# ---- python3 ----
if command -v python3 >/dev/null 2>&1; then
  ok "python3 $(python3 --version 2>&1 | awk '{print $2}')" | "پایتون موجود است"
else
  info "installing python3..." | "در حال نصب پایتون"
  case "$OS" in
    apt) pkg_install "$OS" python3 python3-pip ;;
    dnf|yum) pkg_install "$OS" python3 python3-pip ;;
    pacman) pkg_install "$OS" python python-pip ;;
    brew) pkg_install "$OS" python3 ;;
  esac
fi

# ---- pip ----
if python3 -m pip --version >/dev/null 2>&1; then
  ok "pip available" | "pip موجود است"
else
  info "installing pip..." | "در حال نصب pip"
  case "$OS" in
    apt) pkg_install "$OS" python3-pip ;;
    dnf|yum) pkg_install "$OS" python3-pip ;;
    pacman) pkg_install "$OS" python-pip ;;
    brew) : ;;
  esac
fi

# ---- pillow ----
if python3 -c "import PIL" >/dev/null 2>&1; then
  ok "pillow $(python3 -c 'import PIL; print(PIL.__version__)')" | "پیلو موجود است"
else
  info "installing pillow..." | "در حال نصب pillow"
  python3 -m pip install --quiet pillow || PIP_FAILED=1
  if [ -n "${PIP_FAILED:-}" ]; then
    # PEP 668 externally-managed environments
    info "retrying with --break-system-packages" | "تلاش مجدد"
    python3 -m pip install --quiet --break-system-packages pillow || \
      pkg_install "$OS" python3-pillow || true
  fi
  python3 -c "import PIL" >/dev/null 2>&1 \
    && ok "pillow installed" | "pillow نصب شد" \
    || warn "pillow install failed — run: pip install pillow" | "نصب pillow ناموفق"
fi

# ---- ffmpeg ----
if command -v ffmpeg >/dev/null 2>&1; then
  ok "ffmpeg $(ffmpeg -version 2>/dev/null | head -1 | awk '{print $3}')" | "ffmpeg موجود است"
else
  info "installing ffmpeg..." | "در حال نصب ffmpeg"
  case "$OS" in
    apt) pkg_install "$OS" ffmpeg ;;
    dnf|yum) pkg_install "$OS" ffmpeg ;;
    pacman) pkg_install "$OS" ffmpeg ;;
    brew) pkg_install "$OS" ffmpeg ;;
  esac
  command -v ffmpeg >/dev/null 2>&1 \
    && ok "ffmpeg installed" | "ffmpeg نصب شد" \
    || warn "install ffmpeg manually: https://ffmpeg.org" | "ffmpeg را دستی نصب کنید"
fi

# ---- verify ----
echo
python3 doctor.py 2>/dev/null || python3 "$(dirname "$0")/doctor.py"
