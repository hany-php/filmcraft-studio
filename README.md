# FilmCraft Studio

> إضافة (Plugin) لـ **DeepSeek Harness** تحوّل فيديوهات أي مجلد إلى مونتاج **FilmCraft**
> جاهز: مشروع `.fcproj` محفوظ + فيديو MP4 نهائي، بعناوين عربية، وترجمة من الكلام.

**النسخة:** 0.1.0 · **المنصة:** Windows · **الترخيص:** اختياري قبل النشر (غير محدد بعد) · **الحالة:** يعمل ومُختبر

---

# 🇪🇬 الجزء العربي

## ما الذي تفعله الإضافة؟

تعطي الـ Agent أداة واحدة اسمها `filmcraft_montage`. عند استدعائها على مجلد:

1. **تحلل** كل الفيديوهات فيه (المدة، المقاس، معدل الإطارات، وجود صوت).
2. **تنسخ الكلام** محلياً (Whisper على CPU، بلا إنترنت بعد أول تحميل للنموذج).
3. **تستنتج الموضوع والنصوص** من طلب المستخدم ومن كلام المتحدث نفسه.
4. **تبني التصميم**: تايتل افتتاحي، لوور ثيرد، كارت نهاية، تصحيح لوني (Lumetri)،
   Vignette، Push-in بطيء، فيدات صورة وصوت.
5. **تحفظ المشروع** `.fcproj` داخل مجلد المستخدم — قابل لإعادة الفتح والتعديل في FilmCraft.
6. **تصدّر MP4** وتتحقق منه: تعيد استيراده وتقارن إطارات منه بإطارات المشروع لتثبت أن
   النصوص والتأثيرات موجودة فعلاً في الملف النهائي.
7. **تكتب manifest** فيه كل الأوامر والمعرّفات ونتيجة التحقق — للمراجعة والتعديل.

## الميزات

- ✅ **عربي كامل**: تشكيل الحروف، RTL، bidi، أرقام هندية، تشكيل حركات (فتحة/شدة).
- ✅ **ترجمة عربية** اختيارية محروقة من الكلام المنطوق.
- ✅ **تصميم تلقائي** حسب مدة الفيلم (تايتل، لوور ثيرد، كارت نهاية) بمقاسات نسبية.
- ✅ **مقاطع متعددة**: ترتيب على V1 مع Cross Dissolve بينها.
- ✅ **تحقق تلقائي** لكل مخرج قبل التسليم.
- ✅ **تشغيل كامل من أداة واحدة** أو من سطر الأوامر.
- ✅ **لا يعدّل الأصل**: يقرأ فقط ويكتب مخرجاته في المجلد.

## كيف تستدعي الإضافة؟ (ابدأ من هنا)

الإضافة **ليست زراً في الواجهة** — إنها أداة (Tool) يستخدمها الـ Agent. خطوات الاستدعاء:

1. افتح **جلسة جديدة** في Harness تكون **مساحة عملها = مجلد الفيديوهات**
   (مثلاً `C:\Users\hany_\Desktop\TestVideo`).
   > مهم: مساحة العمل يجب أن تكون مجلد الفيديوهات، وليست مجلد الإضافة.
2. اكتب طلبك بلغة طبيعية، مثل:
   - «اعمل مونتاج لفيديوهات المجلد الحالي»
   - «اعمل فيديو توعية عن الأمن السيبراني من الفيديوهات هنا مع ترجمة عربية»
   - «حوّل مقاطع هذا المجلد إلى مونتاج احترافي مدته القصوى 30 ثانية»
3. الـ Agent سيستدعي تلقائياً أداة **`filmcraft_montage`** ويخبرك بالمخرجات.

وإذا أردت تسمية الأداة صراحةً:

```text
استخدم أداة filmcraft_montage على المسار C:\Users\hany_\Desktop\TestVideo
مع captions: true و name: promo_01
```

```text
Use filmcraft_montage on this folder with language "en".
```

**ماذا يحدث بعد الطلب؟** تحليل الفيديوهات → نسخ الكلام (اختياري) → بناء التصميم →
حفظ `.fcproj` → تصدير MP4 → تحقق تلقائي. المخرجات داخل نفس المجلد:
`<name>.fcproj` و`out/<name>.mp4` و`renders/` وملف manifest.

**ملاحظات سريعة:**

- أول تشغيل قد يستغرق دقائق (تنزيل/تحميل نموذج Whisper ثم التحليل والتصدير). للسرعة:
  `noTranscribe: true`.
- إعادة التشغيل بنفس `name` **تعيد بناء المشروع من الصفر**؛ استخدم اسماً جديداً أو خذ نسخة.
- لتحديد ملفات معينة: `media: ["a.mp4","b.mp4"]`.
- إن قال الوكيل إن الأداة غير موجودة: افتح **Plugins** وتأكد أن «استوديو FilmCraft»
  (`filmcraft-studio`) مثبّت ومفعّل، ثم أعد المحاولة في جلسة جديدة.

## المتطلبات

| المتطلب | التفاصيل |
|---|---|
| Windows | تم تطويره واختباره على Windows |
| FilmCraft | v0.19.0 أو أحدث مثبّت، مع `filmcraft-cli.exe` |
| Python | 3.10+ مع `numpy` (و`torch` + `transformers` إن أردت الترجمة) |
| ffmpeg | اختياري (للتحقق الخارجي فقط) |
| DeepSeek Harness | مثبّت، بروفايل `desktop` (الافتراضي) |

## التركيب

### أولاً: التركيب باستخدام الذكاء الاصطناعي (موصى به ومُختبر)

الطريقة هي التي بُنيت بها الإضافة فعلاً. افتح Harness في أي مساحة عمل واطلب من الـ Agent:

```text
ثبّت إضافة FilmCraft Studio من المسار:
C:\Users\hany_\Documents\DeepSeek Harness\workspace\plugins\workspaces\FilmCraft-Plugin\dsh-bundle
```

الـ Agent يستدعي أداة `plugin_manager`:

```jsonc
{
  "action": "install_bundle",
  "target": "C:\\Users\\hany_\\Documents\\DeepSeek Harness\\workspace\\plugins\\workspaces\\FilmCraft-Plugin\\dsh-bundle"
}
```

النتيجة المتوقعة: `"application": "applied"` ثم تظهر أداة `filmcraft_montage` مباشرة
في أدوات الـ Agent (دون إعادة تشغيل).

> إن كانت لديك نسخة قديمة مثبتة: `remove_bundle` ثم `install_bundle` من جديد.

### ثانياً: التركيب اليدوي

هناك ثلاث طرق يدوية، مرتبة من الأسهل:

**1) من صفحة Plugins في Harness:** افتح القائمة الجانبية ← **Plugins** ← خيار تركيب/إضافة
bundle، وأدخل المسار المطلق لمجلد `dsh-bundle` (تركيب محلي من نوع `link:`). بعد التركيب
فعّل الحزمة `filmcraft-studio` إن لم تُفعّل تلقائياً.

**2) من الطرفية عبر CLI:** أضف الحزمة كاعتماد مرتبط (link) في البروفايل، ثم فعّلها:

```powershell
dsh plugin --profile desktop add "link:C:\Users\hany_\Documents\DeepSeek Harness\workspace\plugins\workspaces\FilmCraft-Plugin\dsh-bundle"
```

ثم افتح Harness ← Plugins وفعّل `filmcraft-studio` (اختيار الحزمة يضيفها إلى
`dsh.profile.bundles`). إن طلب التطبيق إعادة تشغيل، فأعد تشغيل Harness.

**3) نسخ يدوي إلى بروفايل آخر:** انسخ مجلد المشروع إلى مكان دائم، ثم كرر الخطوة 2 بمساره
الجديد. لا تعدّل `package.json` أو `cordis.patch.yml` للبروفايل يدوياً؛ استخدم مدير
الإضافات (صفحة Plugins أو `plugin_manager`).

**التحقق من التركيب:**

```text
- تظهر إضافة «استوديو FilmCraft» في صفحة Plugins.
- تظهر أداة filmcraft_montage لدى الـ Agent.
- السجل: dsh-bundle → filmcraft-studio → include:filmcraft-studio فعّال.
```

## الاستخدام

### من داخل Harness (الأداة `filmcraft_montage`)

| المعامل | النوع | الوصف |
|---|---|---|
| `workspace` | string | مسار المجلد (اختياري؛ الافتراضي مجلد الجلسة) |
| `brief` | string | طلب المستخدم بالعربية/الإنجليزية — يحدد الموضوع والنصوص |
| `media` | string[] | ملفات محددة بدل كل فيديوهات المجلد |
| `language` | `ar` \| `en` | لغة التصميم (افتراضي `ar`) |
| `theme` | `auto` \| `security` \| `generic` | القالب (افتراضي تلقائي) |
| `captions` | bool | ترجمة عربية محروقة من الكلام |
| `tighten` | number | حذف فترات الصمت الأطول من هذه الثواني |
| `name` | string | اسم المشروع/الملف (افتراضي `filmcraft_edit`) |
| `export` | bool | تصدير MP4 (افتراضي true) |
| `noTranscribe` | bool | تخطي النسخ الصوتي (أسرع) |

مثال:

```jsonc
{ "workspace": "C:\\Users\\hany\\Desktop\\TestVideo",
  "brief": "فيديو توعية عن الأمن السيبراني",
  "language": "ar",
  "captions": true }
```

### من سطر الأوامر (بدون Harness)

```powershell
cd "C:\Users\hany_\Documents\DeepSeek Harness\workspace\plugins\workspaces\FilmCraft-Plugin"

# مونتاج كامل + ترجمة
python filmcraft_studio.py --workspace "C:\path\to\videos" --brief "فيديو تعريفي"

# بدون ترجمة (أسرع)
python filmcraft_studio.py --workspace "C:\path\to\videos" --language en --no-transcribe

# تصميم فقط بلا تصدير (للاختبار)
python filmcraft_studio.py --workspace "C:\path\to\videos" --no-export
```

## المخرجات

كل شيء داخل `workspace`:

```text
<workspace>/
├── <name>.fcproj                المشروع (افتحه في FilmCraft لتعديله)
├── <name>_manifest.json         سجل الأوامر + المعرّفات + نتيجة التحقق
├── out/<name>.mp4               الفيديو النهائي
└── renders/                     صور تحقق (من المشروع ومن MP4)
```

## التحقق

المحرك يتحقق ذاتياً: يعيد استيراد MP4 كوسيط جديد، ويرندر إطارات في 3 نقاط زمنية، ويقارنها
بإطارات المشروع. النتيجة في `manifest`:

```json
"verified": true,
"verification": [
  { "seconds": 0.6, "mean_abs_diff": [1.93, 1.19, 2.09], "match": true },
  { "seconds": 3.6, "mean_abs_diff": [2.31, 1.27, 2.2],  "match": true },
  { "seconds": 7.8, "mean_abs_diff": [2.06, 1.39, 2.03], "match": true }
]
```

فرق 1–2 وحدة لونية = ضغّط H.264 فقط، أي أن النصوص والتأثيرات **موجودة داخل الملف النهائي**.

## بنية المشروع

```text
FilmCraft-Plugin/
├── AGENTS.md               دليل أي ذكاء اصطناعي يعمل على المشروع (اقرأه أولاً)
├── README.md               هذا الملف
├── filmcraft_studio.py     المحرك: تحليل → تصميم → حفظ → تصدير → تحقق
├── bridge.py               جسر JSON إلى filmcraft-cli
├── transcribe.py           Whisper محلي → transcript.set
└── dsh-bundle/             حزمة إضافة Harness (أداة filmcraft_montage)
    ├── package.json        مانيفست الحزمة (bundle patch + exports)
    ├── cordis.patch.yml    صف الإضافة في الـ Loader
    ├── index.js            تعريف الأداة وتنفيذها
    ├── icon.svg            أيقونة أصلية
    └── locale/{ar,en}.json اسم ووصف الإضافة
```

## استكشاف الأخطاء

| المشكلة | الحل |
|---|---|
| الأداة لا تظهر | تأكد أن التركيب أعطى `applied`، ثم أعد التفعيل: `set_bundle enabled:false` ثم `true` |
| `filmcraft-cli` غير موجود | تأكد من مسار التثبيت `C:\Program Files\ArtCraft\FilmCraft\filmcraft-cli.exe` |
| فشل الترجمة | `pip install torch transformers`، وتأكد من مساحة القرص (موديل small ~1GB) |
| خروج بخطأ لكن الملفات سليمة | اقرأ `manifest`؛ أحياناً stderr فقط (تحذيرات) وليست فشلاً |
| العربية مقطّعة | لا ترفع `tracking` أبداً للنص العربي |
| مشروع موجود ولا أريد مسحه | بدّل `name` أو انسخه قبل إعادة التشغيل (المحرك يبدأ من مشروع جديد) |

## النشر (رفع المشروع)

المشروع الآن **محلي** (`private: true`) وغير منشور على أي منصة. الرفع قرار مالك، ويتطلب:

1. **اختيار ترخيص** (مقترح: MIT) وإضافة ملف `LICENSE`.
2. **إنشاء مستودع Git**:

```powershell
cd "C:\Users\hany_\Documents\DeepSeek Harness\workspace\plugins\workspaces\FilmCraft-Plugin"
git init
git add .
git commit -m "FilmCraft Studio 0.1.0: Arabic montage plugin for DeepSeek Harness"
git remote add origin https://github.com/<OWNER>/<REPO>.git
git branch -M main
git push -u origin main
```

3. **النشر كحزمة npm** (اختياري): أزل `"private": true` من `dsh-bundle/package.json`،
   غيّر الاسم إلى نطاق تملكه (مثل `@owner/filmcraft-studio`)، ثم `npm publish`.
4. للتركيب بعد النشر: `install_bundle` بالاسم من المستودع/السجل بدل المسار المحلي.

> ⚠️ لم يُنفَّذ أي رفع (push/publish) حتى الآن: يحتاج موافقة صريحة واسم المستودع/المالك،
> ولا يجب رفع أي ميديا تجريبية أو أوزان نماذج أو ملفات `.fcproj` خاصة.

---

# 🇬🇧 English

## What it does

A **DeepSeek Harness** plugin that turns the videos in a folder into a finished **FilmCraft**
edit: a saved `.fcproj` plus an exported MP4, with Arabic titles, a lower third, an end card,
colour grading, push-in motion, audio fades, and optional Arabic captions transcribed from the
spoken audio. One tool call, `filmcraft_montage`, drives the whole pipeline.

Every run analyses the media, builds the timeline, designs the graphics, saves the project,
exports the video, and then **verifies the export**: it re-imports the MP4 and compares rendered
frames with the project frames, so titles and effects are proven to be in the final file.

## How to invoke it

The plugin is not a UI button; it is an **agent tool**. To use it:

1. Open a **new session** whose workspace is the **video folder**
   (for example `C:\Users\hany_\Desktop\TestVideo`).
2. Ask in natural language: “Edit the videos in this folder”, or
   «اعمل مونتاج لفيديوهات المجلد الحالي».
3. The agent calls **`filmcraft_montage`** automatically and reports the outputs.

Name the tool explicitly if you prefer:

```text
Use filmcraft_montage on C:\Users\hany_\Desktop\TestVideo with captions: true and name: promo_01
```

**What happens:** analyse media → transcribe speech (optional) → build the design →
save `.fcproj` → export MP4 → self-verify. Outputs land in the workspace:
`<name>.fcproj`, `out/<name>.mp4`, `renders/`, and a manifest.

**Notes:**

- The first run is slow (Whisper model download/load, analysis, export). Pass
  `noTranscribe: true` for speed.
- Re-running with the same `name` rebuilds the project from scratch — use a new name or keep a copy.
- Limit the inputs with `media: [...]`.
- If the agent reports the tool is missing, check **Plugins** that `filmcraft-studio` is
  installed and enabled, then retry in a new session.

## Requirements

- Windows (developed and tested there)
- FilmCraft v0.19.0+ with `filmcraft-cli.exe`
- Python 3.10+ with `numpy`; `torch` + `transformers` for transcription
- ffmpeg (optional, external verification only)
- DeepSeek Harness, `desktop` profile

## Installation

### AI-assisted (recommended, verified)

Open Harness and tell the agent:

```text
Install the FilmCraft Studio plugin from:
C:\Users\hany_\Documents\DeepSeek Harness\workspace\plugins\workspaces\FilmCraft-Plugin\dsh-bundle
```

The agent calls `plugin_manager` with `{"action":"install_bundle","target":"<absolute dir>"}`.
A successful install reports `"application": "applied"` and `filmcraft_montage` appears in the
agent's toolset immediately (no restart).

### Manual

1. **Plugins page:** sidebar → Plugins → install bundle → paste the absolute folder path of
   `dsh-bundle` (a local `link:` install) → enable `filmcraft-studio` if needed.
2. **CLI:** add the linked package to the profile, then enable it in the Plugins page:

```powershell
dsh plugin --profile desktop add "link:C:\Users\hany_\Documents\DeepSeek Harness\workspace\plugins\workspaces\FilmCraft-Plugin\dsh-bundle"
```

3. To move the plugin elsewhere, copy the whole project folder and repeat the command with its
   new path. Do not hand-edit the profile's `package.json` / `cordis.patch.yml`; use the plugin
   manager instead.

## Usage

Tool parameters: `workspace` (defaults to the session folder), `brief`, `media[]`,
`language` (`ar`/`en`), `theme` (`auto`/`security`/`generic`), `captions`, `tighten`, `name`,
`export`, `noTranscribe`.

```jsonc
{ "workspace": "C:\\Users\\hany\\Desktop\\TestVideo",
  "brief": "cybersecurity awareness video",
  "language": "ar",
  "captions": true }
```

Command line:

```powershell
python filmcraft_studio.py --workspace "C:\path\to\videos" --brief "intro video"
python filmcraft_studio.py --workspace "C:\path\to\videos" --language en --no-transcribe
```

## Outputs

```text
<workspace>/<name>.fcproj        editable FilmCraft project
<workspace>/<name>_manifest.json command log, ids and verification result
<workspace>/out/<name>.mp4       final video (H.264 + AAC, source size/rate)
<workspace>/renders/             verification frames (project and MP4)
```

## Verification

`verified: true` in the manifest means three re-rendered frames of the exported MP4 matched the
project frames (`mean_abs_diff` 1–2 = H.264 compression noise only).

## Arabic support

FilmCraft 0.19.0 shapes Arabic natively: contextual forms, RTL, bidi, Arabic-Indic digits and
tashkeel. Rules learned by measurement: never apply `tracking` to Arabic (it breaks the joins),
and set `align: "center"` explicitly (default is left). Display font: Dubai; secondary: Segoe UI.

## Publishing

The project is local (`private: true`) and not published. Publishing needs the owner's decision:

1. Pick a license (MIT suggested) and add `LICENSE`.
2. `git init`, commit, add the remote, push.
3. Optional npm publish: remove `private`, rename to a scope you own, `npm publish`.
4. After publishing, install with `install_bundle` by package/repo name.

> No push or publish has been performed. Do not publish sample media, Whisper weights or private
> `.fcproj` files.

---

## License

No license chosen yet. The plugin code is the project owner's; fonts and the FilmCraft application
remain under their own licenses. Choose a license before publishing.
