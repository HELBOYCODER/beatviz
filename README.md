# 🎵 BeatViz

**BeatViz** یک اپلیکیشن ویژوالایزر موزیک برای آهنگسازها و پروڈیوسرهاست — آهنگت رو وارد کن، از **۶۱ قالب حرفه‌ای** انتخاب کن، و خروجی ویدیوی **Full HD (1080p)** بگیر تا کارهات دیگه خشک و خالی آپلود نشن.

> BeatViz is a music visualizer app for musicians & producers — drop your track, pick from **61 pro templates**, and export a **Full HD video** so your releases never go online as a bare waveform again.

## ✨ امکانات | Features

| فارسی | English |
|---|---|
| 🎨 ۵۸ قالب ویژوال در ۴ دسته (کلاسیک، موزیکال، حرفه‌ای، خاص) | 58 visual templates in 4 groups (Classic, Musical, Pro, Special) |
| 🧠 تحلیل واقعی طیف فرکانسی (FFT) — نه ویوفرم ساده | Real FFT spectrum analysis — not a fake waveform |
| 🎹 پشتیبانی MIDI: نت‌های واقعی آهنگ رسم می‌شن | MIDI-aware: actual notes are drawn (drop a `.mid` next to the audio) |
| 🕐 تشخیص خودکار BPM از اسم فایل یا خود آهنگ | Auto BPM detection from filename or audio onsets |
| 📱 خروجی ۱۶:۹ Full HD و ۹:۱۶ برای ریلز | 16:9 Full HD and 9:16 vertical export |
| 💻 کاملاً آفلاین — هیچ آپلودی انجام نمی‌شه | 100% offline — nothing ever leaves your machine |

## 📥 دانلود | Download

از صفحه‌ی [Releases](https://github.com/HELBOYCODER/beatviz/releases/latest) آخرین نسخه رو بگیر:

- **macOS**: `BeatViz-1.0.0-arm64.dmg` (Apple Silicon) یا `x64.dmg` (Intel)
- **Windows**: `BeatViz Setup.exe`
- **Linux**: `BeatViz.AppImage`

> macOS اولین اجرا: روی فایل DMG دوبار کلیک کن، اپ رو بکش توی Applications. اگه گیت‌وی هشدار داد: راست‌کلیک → Open.

## 🚀 استفاده | Usage

1. آهنگ (MP3/WAV) رو بکش و توی پنجره رها کن | Drag & drop your track
2. قالب رو از گالری سمت راست انتخاب کن | Pick a template
3. مدت و رزولوشن رو تنظیم کن و «ساخت ویدیو» بزن | Set duration/resolution and hit render
4. ویدیو داخل خود اپ پخش می‌شه — دانلود کن | Preview plays in-app, save the MP4

### قالب‌ها (نمونه) | Templates (sample)

`beatbars` طیف گرادیانی · `aura` حلقه‌های نفس‌کشانه · `melody` حباب‌های نت · `transit` نقشه‌ی مترو · `piano` پیانورول · `radial` انفجار شعاعی · + ذرات، تونل، کالیدوسکوپ، آتش‌بازی، وینیل، نوار کاست، اکو، ماتریکسی، ماندالا، سیت‌سکی و ۴۵ قالب دیگه


### یک‌خطی نصب و سلامت‌سنجی | One-command install & doctor

```bash
bash install.sh    # نصب همه‌ی پیش‌نیازها (پایتون، pillow، ffmpeg) — قابل اجرای مکرر
python3 doctor.py  # بررسی همه‌ی وابستگی‌ها + رندر فریم آزمایشی برای تک‌تک قالب‌ها + تست انکود ffmpeg
```

### کیفیت رندر HD | HD render quality

```bash
# پیش‌فرض: preset=quality → سوپرسمپلینگ ۲x + LANCZOS + CRF 16 + dithering
python3 beatviz.py song.wav --look graph_forced --width 1080 --height 1920 --fps 60
# گزینه‌ها:
#   --preset fast|high|quality   سرعت در برابر کیفیت
#   --ss 1|2|3                  ضریب سوپرسمپلینگ
#   --dither 0..2               حذف باندینگ گرادیان (0=خاموش)
```

### قالب‌های گراف | Graph look family (v1.3.0)

`graph_forced` گراف نیروی‌گرا · `graph_neural` شبکه عصبی · `graph_constellation` صورت فلکی
— گره‌ها = باندهای فرکانسی، یال‌ها = روابط طیفی، چیدمان نیرو-گرا با موسیقی زنده می‌شود.

## 🛠 اجرا از سورس | Run from source

```bash
git clone https://github.com/HELBOYCODER/beatviz.git
cd beatviz
bash install.sh          # one command: installs python3 + pillow + ffmpeg (apt/dnf/pacman/brew)
python3 doctor.py        # health check: every dep + every look + ffmpeg encode test
python3 app_server.py 8765     # http://127.0.0.1:8765
# یا دسکتاپ:
npm install && npm start
```

### CLI (بدون UI)

```bash
python3 beatviz.py track.mp3 --look beatbars --duration 15          # افقی Full HD
python3 beatviz.py track.mp3 --look melody --width 1080 --height 1920   # ریلز عمودی
python3 beatviz.py track.mp3 --list-looks
```

## 🏗 بیلد | Build

پوش به `main` یا یه تگ `v*` بزن — GitHub Actions خودکار `.dmg` مک (Intel + Apple Silicon)، نصب‌کننده‌ی ویندوز و AppImage لینوکس رو می‌سازه و توی Releases می‌ذاره.

## 📄 لایسنس | License

MIT
