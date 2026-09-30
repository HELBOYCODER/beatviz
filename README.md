# 🎵 BeatViz

**BeatViz** یک اپلیکیشن ویژوالایزر موزیک برای آهنگسازها و پروڈیوسرهاست — آهنگت رو وارد کن، از **۵۸ قالب حرفه‌ای** انتخاب کن، و خروجی ویدیوی **Full HD (1080p)** بگیر تا کارهات دیگه خشک و خالی آپلود نشن.

> BeatViz is a music visualizer app for musicians & producers — drop your track, pick from **58 pro templates**, and export a **Full HD video** so your releases never go online as a bare waveform again.

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

## 🛠 اجرا از سورس | Run from source

```bash
git clone https://github.com/HELBOYCODER/beatviz.git
cd beatviz
pip install pillow
# backend needs ffmpeg on PATH
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
