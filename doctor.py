#!/usr/bin/env python3
"""BeatViz doctor — checks every dependency and every look, fixes what it can.

Usage: python3 doctor.py [--fast]
"""
import importlib
import os
import shutil
import subprocess
import sys
import tempfile

BOLD, GREEN, RED, YEL, CYAN, OFF = ("\033[1m", "\033[32m", "\033[31m",
                                    "\033[33m", "\033[36m", "\033[0m")
PASS, FAIL, FIXED = "PASS", "FAIL", "FIXED"
results = []


def report(status, en, fa, detail=""):
    color = {"PASS": GREEN, "FAIL": RED, "FIXED": YEL}[status]
    print(f"  {color}[{status}]{OFF} {en} | {fa}" + (f"  ({detail})" if detail else ""))
    results.append(status)


def check_import(mod, pip_name=None, fa_name=""):
    """Check importable; try pip install to fix."""
    try:
        importlib.import_module(mod)
        report(PASS, f"python module '{mod}'", fa_name or f"ماژول {mod}")
        return True
    except ImportError:
        pass
    pip_name = pip_name or mod
    print(f"  {YEL}...{OFF} missing '{mod}' — attempting pip install | در حال نصب")
    for extra in ([], ["--break-system-packages"]):
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                            *extra, pip_name], check=True, timeout=300)
            try:
                importlib.import_module(mod)
                report(FIXED, f"python module '{mod}' (installed)", f"ماژول {mod} نصب شد")
                return True
            except ImportError:
                continue
        except Exception:
            continue
    report(FAIL, f"python module '{mod}'", f"ماژول {mod} — نصب نشد",
           f"pip install {pip_name}")
    return False


def check_cmd(cmd, hint_fa, fix_pkgs=None):
    if shutil.which(cmd):
        report(PASS, f"command '{cmd}'", f"دستور {cmd} موجود است")
        return True
    if fix_pkgs:
        print(f"  {YEL}...{OFF} '{cmd}' missing — attempting install | در حال نصب")
        for installer in (["apt-get", "install", "-y"], ["dnf", "install", "-y"],
                          ["brew", "install"]):
            if shutil.which(installer[0]):
                try:
                    subprocess.run(["sudo", *installer, *fix_pkgs] if
                                   shutil.which("sudo") else [*installer, *fix_pkgs],
                                   check=True, timeout=900)
                    if shutil.which(cmd):
                        report(FIXED, f"command '{cmd}' (installed)", f"{cmd} نصب شد")
                        return True
                except Exception:
                    pass
    report(FAIL, f"command '{cmd}'", hint_fa,
           f"install {cmd}: https://ffmpeg.org / package manager")
    return False


def check_looks():
    """Import every look module and render one test frame at 540x960."""
    os.chdir(os.path.dirname(os.path.abspath(__file__)) or ".")
    sys.path.insert(0, os.getcwd())
    try:
        import looks as looks_mod
        report(PASS, "looks.py imports", "ماژول looks")
    except Exception as e:
        report(FAIL, "looks.py imports", "ماژول looks", str(e))
        return
    mods = {"looks.py": looks_mod}
    for name in ("looks_music", "templates_pack1", "templates_pack2", "looks_graph"):
        try:
            mods[name + ".py"] = importlib.import_module(name)
            report(PASS, f"{name}.py imports", f"ماژول {name}")
        except Exception as e:
            report(FAIL, f"{name}.py imports", f"ماژول {name}", str(e))
    try:
        import midilib
        report(PASS, "midilib.py imports", "ماژول midilib")
    except Exception as e:
        report(FAIL, "midilib.py imports", "ماژول midilib", str(e))

    from looks import Ctx
    all_looks = []
    for m in mods.values():
        all_looks += list(getattr(m, "LOOKS", {}).items())
    print(f"  {CYAN}→{OFF} rendering one 540x960 test frame per look "
          f"({len(all_looks)} looks) | رندر فریم آزمایشی برای همه‌ی قالب‌ها")
    mono = [0.0] * 2048
    bad = []
    for name, fn in all_looks:
        try:
            c = Ctx(540, 960, 1.0, 0.5, 0.7, None, [])
            c.mono = mono
            c.sr = 22050
            c.bpm = 120
            c.duration = 7.0
            img = fn(c)
            if img.size != (540, 960):
                raise ValueError(f"bad size {img.size}")
        except Exception as e:
            bad.append((name, str(e)[:80]))
    if bad:
        report(FAIL, f"{len(all_looks) - len(bad)}/{len(all_looks)} looks render",
               "رندر قالب‌ها", "; ".join(f"{n}: {e}" for n, e in bad))
    else:
        report(PASS, f"all {len(all_looks)} looks render 540x960",
               "همه‌ی قالب‌ها رندر شدند")
    return len(all_looks), bad


def check_ffmpeg_encode():
    """Verify a real x264 yuv420p encode works."""
    if not shutil.which("ffmpeg"):
        report(FAIL, "ffmpeg encode test", "تست انکود ffmpeg", "ffmpeg not on PATH")
        return
    try:
        tmp = tempfile.mkdtemp(prefix="beatviz_doctor_")
        png = os.path.join(tmp, "f.png")
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (540, 960), (20, 20, 40))
        ImageDraw.Draw(img).ellipse([200, 400, 340, 540], fill=(0, 245, 212))
        img.save(png)
        out = os.path.join(tmp, "t.mp4")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", png,
                        "-t", "0.2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        out], check=True, timeout=120)
        info = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                               "-show_entries", "stream=pix_fmt,codec_name",
                               "-of", "csv=p=0", out],
                              capture_output=True, text=True).stdout.strip()
        if "yuv420p" in info and "h264" in info:
            report(PASS, "ffmpeg x264 yuv420p encode", "انکود ffmpeg سالم است")
        else:
            report(FAIL, "ffmpeg encode", "انکود ffmpeg", info)
        for f in os.listdir(tmp):
            os.unlink(os.path.join(tmp, f))
        os.rmdir(tmp)
    except Exception as e:
        report(FAIL, "ffmpeg encode test", "تست انکود ffmpeg", str(e))


def main():
    fast = "--fast" in sys.argv
    print(f"{BOLD}BeatViz Doctor | دکتر بیت‌ویز{OFF}")
    print("=" * 60)

    # 1. python
    v = f"{sys.version_info.major}.{sys.version_info.minor}"
    report(PASS if sys.version_info >= (3, 8) else FAIL,
           f"python {v}", f"پایتون {v}")

    # 2. deps
    check_import("PIL", "pillow", "کتابخانه pillow")
    check_cmd("ffmpeg", "ffmpeg نصب نشده — برای خروجی ویدیو لازم است",
              fix_pkgs=["ffmpeg"] if not fast else None)
    if shutil.which("ffmpeg"):
        check_cmd("ffprobe", "ffprobe (بخشی از ffmpeg)")

    # 3. looks
    look_info = check_looks()

    # 4. encode
    check_ffmpeg_encode()

    print("=" * 60)
    n_pass = results.count(PASS) + results.count(FIXED)
    total = len(results)
    if all(r in (PASS, FIXED) for r in results):
        print(f"{GREEN}{BOLD}✔ ALL CHECKS PASSED | همه‌ی بررسی‌ها موفق بود "
              f"({n_pass}/{total}){OFF}")
        return 0
    print(f"{RED}{BOLD}✘ {results.count(FAIL)} CHECK(S) FAILED | "
          f"{results.count(FAIL)} مورد ناموفق ({n_pass}/{total} OK){OFF}")
    print(f"  run: {CYAN}bash install.sh{OFF} to fix | برای رفع مشکل install.sh را اجرا کنید")
    return 1


if __name__ == "__main__":
    sys.exit(main())
