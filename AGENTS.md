# AGENTS.md — دليل أي ذكاء اصطناعي يعمل على FilmCraft Studio

> هذا الملف هو تعليمات مساحة العمل وذاكرتها. اقرأه كاملاً قبل أي تعديل، ثم نفّذ ما فيه.
> اللغة: عربي، والمصطلحات التقنية بالإنجليزية كما في الكود.

---

## 0. ما هذا المشروع؟

**FilmCraft Studio** إضافة (Plugin) لـ DeepSeek Harness تستطيع تحويل فيديوهات أي مجلد
إلى مونتاج FilmCraft كامل: مشروع `.fcproj` محفوظ + فيديو MP4 نهائي، مع عناوين عربية،
لوور ثيرد، كارت نهاية، تصحيح لوني، زووم، فيدات، ونسخ صوتي عربي محلي (Whisper) لبناء
الترجمة والنصوص من الكلام.

المخرجات تُكتب **داخل مجلد المستخدم**، والمشروع يبقى قابلاً لإعادة الفتح والتعديل في
تطبيق FilmCraft.

---

## 1. البنية (من الطلب إلى الملف النهائي)

```text
المستخدم: "اعمل مونتاج لفيديوهات هذا المجلد"
        │
        ▼
أداة Harness: filmcraft_montage            (dsh-bundle/index.js)
        │  spawn python
        ▼
المحرك: filmcraft_studio.py
        │  يستدعي
        ├── bridge.py ──► filmcraft-cli.exe ──► FilmCraft Engine
        │                                    (مشروع .fcproj + رندر)
        └── transcribe.py (Whisper محلي) ──► transcript.set ──► captions
        │
        ▼
مخرجات: <workspace>/<name>.fcproj
        <workspace>/out/<name>.mp4
        <workspace>/renders/  (صور تحقق)
        <workspace>/<name>_manifest.json
```

| الملف | المسؤولية | نقاط الدخول |
|---|---|---|
| `dsh-bundle/index.js` | طبقة Harness: تعريف الأداة، القيم الافتراضية، spawn، الأخطاء | `apply(ctx)`, `execute(args, exec)` |
| `dsh-bundle/cordis.patch.yml` | صف الإضافة في الـ Loader | `insert: filmcraft-studio` |
| `filmcraft_studio.py` | المحرك الكامل (تحليل → تصميم → حفظ → تصدير → تحقق) | `Studio.build()`, `main()` |
| `bridge.py` | جسر JSON إلى CLI: `run_script`, `exec`, `import`, `render`, `export`, `probe` | `FilmCraftBridge` |
| `transcribe.py` | Whisper محلي عبر `transformers`+`torch`، يخرج حمولة `transcript.set` | `transcribe()`, `to_filmcraft_payload()` |

دوال المحرك المهمة: `discover()` (اكتشاف الوسائط)، `probe_media()`، `pick_theme()`،
`transcribe_sequence()`، `build_graphics()`، `build_lower_third()`، `build_picture()`
(اللون/الزووم/الفيدات)، `save_and_export()`، `verify()`، `persist_verification()`.

---

## 2. الثوابت (لا تُخالفها)

1. **كل شيء داخل مساحة العمل**: المدخلات، `.fcproj`، الرندرات، MP4. لا تكتب خارج المجلد
   إلا في `%TEMP%`.
2. **الأصل لا يُعدّل ولا يُحذف**: اقرأ الفيديو كما هو. لا تحذف ملفات المستخدم.
3. **لكل تعديل مشروع محفوظ** قابل لإعادة الفتح؛ استخدم `--save` في `bridge.run_script`.
4. **لا تخترع معرّفات**: `clip`/`item` تُقرأ من ردود الأوامر أو `inspect`، لا تُخمَّن.
5. **افترض أن كل إدخال خبيث**: أطوال غير متوقعة، مسارات بمقاطع عربية/مسافات، فيديو تالف،
   مساحة قرص. لا تتوقف بـ traceback غير مفهوم؛ أعِد خطأً مفهوماً.
6. **التحقق قبل التسليم**: `verify()` يعيد استيراد MP4 ويقارن إطارات. لا تُبلّغ عن نجاح
   بدونه (أو مع سبب واضح لتعذّره).
7. **لا تنشر** (git push / GitHub / npm) ولا تغيّر `remotes` دون موافقة صريحة من صاحب المشروع.
8. **لا تُضف أصولاً غير مرخّصة** (صور/خطوط/موسيقى): الخطوط هنا من نظام المستخدم، والأيقونة
   أصلية مرسومة في `dsh-bundle/icon.svg`.

---

## 3. كيف بُني هذا المشروع (ملخص التجربة — لتفهم القيود)

1. **الجسر عبر CLI لا Socket**: التحكم في FilmCraft تم عبر `filmcraft-cli.exe` (subprocess،
   JSON على stdout). مستقر، بلا جدار حماية.
2. **صيغة `run -`**: سكربت JSONL من الأوامر يُرسل مرة واحدة إلى CLI، فتبقى حالة التحرير
   (الاختيار/المؤشر/ترتيب الطبقات) كجلسة بشرية، ثم `--save` يكتب المشروع مرة واحدة.
   هذا هو سبب وجود `bridge.run_script` بدل أوامر منفصلة.
3. **صعوبة الجرافيك**: `graphics.newText` / `graphics.newShape` تنشئ **كليب** جديد على أول
   مسار فوق الفيديو؛ لإضافة طبقات لنفس الكليب مرّر `clip=<id>` بدل `track`. الترتيب: الطبقة
   0 خلف، وتزيد للأمام. `graphics.set` يضبط `props` للطبقة.
4. **الأنيميشن**: `effects.setParam(..., "keyframe": true)` عند أول قيمة ثم قيم عند أزمنة
   لاحقة. في `effects.setParam` الزمن `seconds`، وفي `graphics.set` الزمن `time` بالـ ticks.
5. **العربية تعمل أصلاً** في FilmCraft 0.19.0: تشكيل الحروف + RTL + bidi + أرقام هندية +
   تشكيل حركات. القاعدة الذهبية: **لا `tracking` للعربية** (يكسر الوصل)، واضبط
   `align: "center"` صراحةً لأن الافتراضي يسار.
6. **النصوص/التأثيرات في الرندرة النهائية**: أُثبت بقياس (فرق 1–2 وحدة لونية = ضغط H.264).
   سابقاً كان الفشل بسبب أوامر غير موجودة/أسماء معاملات خاطئة، لا بسبب المحرك.
7. **النسخ الصوتي**: النسخة المدمجة في FilmCraft معطّلة (`built without whisper`) → الحل:
   تصدير الصوت WAV من FilmCraft، ثم Whisper محلي، ثم `transcript.set`، ثم
   `transcript.createCaptions`، ثم تصدير بـ `burnCaptions`.
8. **ffmpeg**: أداة الجهاز كانت stub من panda3d؛ ثُبّتت نسخة حقيقية 9.0.2 لاحقاً. المحرك
   لا يحتاجها (FilmCraft يصدّر الصوت) لكنها مفيدة للفحص/القص الخارجي.

---

## 4. كيف تعدّل (Recipes)

### 4.1 تغيير نص/موضوع
- `THEMES` في `filmcraft_studio.py`: أضف موضوعاً بمفاتيح `ar_title, ar_kicker, en_kicker,
  ar_lower, en_lower, ar_sub, ar_end` وكلمات مفتاحية في `words`.
- `PHRASE_RULES`: اجعل نص الجرافيك مقتبساً من كلام المتحدث (مثال: «خط الدفاع الأول»).
- من الأداة: `filmcraft_montage {"theme": "security"}` أو `{"brief": "..."}` أو
  `--title/--subtitle` عبر CLI.

### 4.2 تعديل التصميم
- الخطوط: `FONTS` (الافتراضي `Dubai` للعناوين و`Segoe UI` للنص).
- الألوان: `COLORS`.
- الأبعاد نسبية لـ 1280 عبر `px()`؛ راجع `build_graphics` / `build_lower_third`.
- التوقيت: `title_end`, `lower_start`, `lower_end`, `end_start` محسوبة من مدة الفيلم في
  `build_graphics`.

### 4.3 إضافة عنصر جديد (مثل شارة أعلى الشاشة)
1. أنشئ `graphics.newShape`/`newText` في كليب جرافيك جديد (`track` مناسب).
2. أضف `graphics.set` للأنماط.
3. أضف فيد بـ `fade_graphic(...)` أو حركة بـ `slide_graphic(...)`.
4. اختبر على مساحة عمل تجريبية ثم `render` على إطارين.

### 4.4 إضافة خيار للأداة (Harness)
1. أضف الخاصية في `PARAMETERS` داخل `dsh-bundle/index.js`.
2. حوّلها إلى argument في `execute` (`if (args.x) argv.push('--x', ...)`).
3. أضف `--x` في `argparse` داخل `filmcraft_studio.py`.
4. سجّل الخيار في README.
5. أعد التركيب/التفعيل: `set_bundle enabled:false` ثم `true` (رابط حي، لا يحتاج إعادة تركيب).

### 4.5 إضافة نمط تصميم كامل (Template)
الأفضل: استخرج دالة `build_<template>()` من `build_graphics` واختر القالب من `theme`.
كل قالب يستقبل `(W, H, t, total)` ويعيد أزمنة العناصر.

### 4.6 تغيير نموذج Whisper
`--transcribe-model openai/whisper-tiny|base|small|medium`. النماذج تُحمَّل في كاش
HuggingFace (`%USERPROFILE%\.cache\huggingface`). أول تشغيل قد يستغرق دقائق (تنزيل ~1GB
لموديل small). لا تُضمّن الأوزان في المشروع.

---

## 5. مرجع أوامر FilmCraft المستخدمة

```text
file.newProject, file.newSequence, file.import, timeline.place
graphics.newText, graphics.newShape, graphics.set, graphics.list
effects.apply, effects.setParam, sequence.applyVideoTransition
transcript.set, transcript.createCaptions, transcript.inspect
file.exportMedia
```

- الزمن: 254,016,000,000 tick/ثانية (`bridge.seconds()`).
- `timeline.place`: `{item, track:"V1", seconds}` → يعيد `clips` (صورة + صوت).
- `graphics.newText`: `{text, size, font, fontStyle, position:[x,y], seconds, time, track, clip}`.
- `effects.setParam`: ينجح مع `keyframes: 0` (قيمة ثابتة) — هذا ليس فشلاً.

> للحصول على أي أمر: `filmcraft-cli describe <id>` (المصدر الموثوق) و
> `filmcraft-cli commands <filter>`. لا تعتمد على الذاكرة.

---

## 6. اختبار أي تعديل (إلزامي)

1. **مساحة عمل مؤقتة**: انسخ مقطعاً قصيراً إلى `%TEMP%\fc_test`، ثم
   `python filmcraft_studio.py --workspace "%TEMP%\fc_test" --no-transcribe` (سريع).
2. **رندر إطارات**: `filmcraft-cli --project <p> render --seconds <t> --out <png>` ثم
   `read_image` للحكم بصرياً.
3. **تصدير كامل + تحقق**: شغّل الأداة/المحرك بدون `--no-export`، وتأكد
   `verified: true` في الـ manifest أو السجل.
4. **فحص مستقل (اختياري)**: `ffprobe` للخصائص و`ffmpeg -i out.mp4 -f null -` لفك الترميز.
5. **لا تختبر على مساحة المستخدم النهائية** إذا كان الاختبار سيعيد بناء المشروع ويحذف
   النص المحفوظ (المحرك يمسح المشروع ويعيده من الصفر).

---

## 7. استكشاف الأخطاء

| العرض | السبب المرجّح | الحل |
|---|---|---|
| `command not available` / `enabled:false` | لا يوجد مشروع/سيكوينس مفتوح | افتح `--project` أو أنشئ سيكوينس أولاً |
| `V2 is not free here` | تريد إنشاء كليب جرافيك جديد فوق فيديو موجود | مرّر `clip=<id>` لإضافة طبقة، أو استخدم مساراً حراً |
| النص العربي مقطّع | `tracking` > 0 | اجعله 0 |
| النص غير متمركز | `align` افتراضي يسار | `graphics.set props {"align":"center"}` |
| لا تظهر النصوص في MP4 | تعديل لم يُحفظ/لم يُصدَّر منه | `--save` ثم `export`، وتحقق بـ `verify()` |
| فشل Whisper | لا يوجد torch/transformers أو الشبكة | `pip install torch transformers` (موجودان عادة) |
| بطء شديد | تحميل موديل Whisper أول مرة | استخدم `--no-transcribe` أو `tiny` للاختبار |
| `timeline.place: no such item` | معرّف item من مشروع آخر | اقرأ item id من `import` الحالي |
| PowerShell يمزق JSON | تمرير `exec '<json>'` | استخدم `bridge.run_script` أو `key=value` |

---

## 8. بيئة الجهاز المرجعية

- FilmCraft CLI: `C:\Program Files\ArtCraft\FilmCraft\filmcraft-cli.exe` (v0.19.0).
- Python: 3.13 مع `torch` + `transformers` + `numpy` (Whisper يعمل CPU).
- ffmpeg/ffprobe: `C:\ffmpeg\bin` (9.0.2) — اختياري للمحرك.
- مساحة عمل تجريبية: `C:\Users\hany_\Desktop\TestVideo` (فيها المشروعان والمخرجات النهائية).
- الإضافة مثبتة في بروفايل `desktop` كرابط: `dsh-bundle/` هو مصدر الحزمة.

---

## 9. حدود معروفة

- تعدد المقاطع مُختبر على مقطعين من نفس المصدر (4+4 ثوانٍ)؛ لم يُختبر على مصادر متباينة أطول.
- `transcript.removePauses` يعمل لكن على كلام متصل لا يجد فواصل (يعيد `removed: 0`).
- لا موسيقى خلفية/ducking، ولا كشف مشاهد تلقائي بعد، ولا واجهة Client (Sidebar) — كلها
  خطوات تالية محتملة.
- `filmcraft_edit_captions.fcproj` لا يعرض caption track في `inspect sequence` عبر CLI، لكن
  الترجمات محفوظة في الملف وتظهر في الرندر والتصدير (اختُبر).
