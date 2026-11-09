"""filmcraft_studio.py — the FilmCraft creative-montage engine (workspace aware).

One call turns the videos in a workspace folder into a finished, reviewable
FilmCraft project and an exported video:

    analyse media  ->  optional speech transcript  ->  design timeline
    (title card, lower third, end card, grade, push-in, fades)
    ->  save .fcproj  ->  export MP4  ->  verify the MP4 really has the graphics

Everything goes through `bridge.py` (the filmcraft-cli bridge); no sockets, no
external media tools. Works in Arabic and English, with Arabic-first typography
(Dubai / Segoe UI, verified shaping + RTL + bidi in FilmCraft 0.19.0).

Usage:
    python filmcraft_studio.py --workspace "C:\\path\\to\\folder"
    python filmcraft_studio.py --workspace . --brief "فيديو توعية" --captions
    python filmcraft_studio.py --workspace . --media a.mp4 b.mp4 --transition cross_dissolve
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bridge import FilmCraftBridge, Step, seconds, to_seconds, TICKS_PER_SECOND  # noqa: E402

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".mxf", ".mts"}
IGNORED_DIRS = {"out", "renders", "_archive", "archive", "_legacy", "__pycache__", "node_modules", "auto-save"}

# --- Arabic-first design tokens (all verified rendering correctly) -----------
FONTS = {"ar_display": "Dubai", "ar_text": "Segoe UI", "en": "Segoe UI", "latin": "Inter"}
COLORS = {"white": "#FFFFFF", "cyan": "#7FE3FF", "accent": "#22D3EE", "ink": "#04141D", "soft": "#CFE9F5"}

THEMES = {
    "security": {
        "words": ["أمن", "سيبراني", "الأمن", "cyber", "security", "hack", "حماية", "privacy", "بيانات"],
        "ar_title": "الأمن السيبراني",
        "ar_kicker": "جلسة توعية رقمية",
        "en_kicker": "CYBERSECURITY AWARENESS",
        "ar_lower": "الأمن السيبراني",
        "en_lower": "CYBERSECURITY AWARENESS",
        "ar_sub": "حماية مستقبلنا الرقمي",
        "ar_end": "ابقَ آمناً على الإنترنت",
    },
    "generic": {
        "words": [],
        "ar_title": "فيديو تعريفي",
        "ar_kicker": "لقطات مختارة",
        "en_kicker": "A SHORT FILM",
        "ar_lower": "فيديو تعريفي",
        "en_lower": "SHOWCASE",
        "ar_sub": "لقطات من قلب الحدث",
        "ar_end": "شكراً للمشاهدة",
    },
}

# lines heard in the transcript that make better graphics than any default
PHRASE_RULES = [
    (["خط الدفاع الأول", "خط الدفاع الاول"], {"ar_sub": "خط الدفاع الأول"}),
    (["هويتنا رقمية", "هويتنا الرقمية", "هويتك الرقمية"], {"ar_end": "احمِ هويتك الرقمية"}),
    (["بياناتنا", "بيانتنا"], {"ar_lower_sub_alt": "بياناتنا ومستقبلنا"}),
]


def log(msg: str) -> None:
    print(f"[studio] {msg}", flush=True)


class Studio:
    def __init__(self, workspace: str, name: str = "filmcraft_edit", language: str = "ar",
                 media: list[str] | None = None, brief: str = "", theme: str = "auto",
                 transcribe_model: str = "openai/whisper-small", captions: bool = False,
                 tighten: float = 0.0, export: bool = True, transition: str = "cross_dissolve",
                 overrides: dict[str, str] | None = None, transcribe: bool = True):
        self.ws = os.path.abspath(workspace)
        self.name = name
        self.language = language
        self.media = media
        self.brief = brief
        self.theme_name = theme
        self.transcribe_model = transcribe_model
        self.captions = captions
        self.tighten = tighten
        self.do_export = export
        self.transition = transition
        self.overrides = overrides or {}
        self.transcribe_enabled = transcribe

        self.project = os.path.join(self.ws, f"{name}.fcproj")
        self.out_dir = os.path.join(self.ws, "out")
        self.render_dir = os.path.join(self.ws, "renders")
        self.output = os.path.join(self.out_dir, f"{name}.mp4")
        self.manifest_path = os.path.join(self.ws, f"{name}_manifest.json")
        self.b = FilmCraftBridge(project=self.project, workspace=self.ws)
        self.log: list[dict] = []
        self.sequence: dict = {}
        self.clips: list[dict] = []
        self.theme: dict = {}

    # ------------------------------------------------------------------ helpers
    def note(self, kind: str, **data) -> None:
        self.log.append({"step": kind, "at": round(time.time(), 2), **data})
        log(f"{kind}: " + json.dumps(data, ensure_ascii=False)[:400])

    def check(self, reply: list[dict], what: str) -> dict:
        summary = reply[0]
        bad = [ln for ln in summary["lines"] if not ln.get("ok")]
        if bad or not summary["ok"]:
            raise SystemExit(f"FAILED {what}: {json.dumps(summary, ensure_ascii=False, indent=2)[:4000]}")
        result = {ln["id"]: ln.get("result") for ln in summary["lines"]}
        self.note(what, result=result)
        return result

    def run(self, steps: list[Step], what: str, save: bool = True) -> dict:
        return self.check(self.b.run_script(steps, save=save), what)

    # ------------------------------------------------------------------ analysis
    def discover(self) -> list[str]:
        if self.media:
            files = [os.path.abspath(p) for p in self.media]
            missing = [p for p in files if not os.path.exists(p)]
            if missing:
                raise SystemExit(f"media not found: {missing}")
            return files
        found: list[str] = []
        for root, dirs, names in os.walk(self.ws):
            dirs[:] = [d for d in dirs if d.lower() not in IGNORED_DIRS and not d.startswith((".", "_"))]
            for n in sorted(names):
                if os.path.splitext(n)[1].lower() in VIDEO_EXT:
                    found.append(os.path.join(root, n))
        found.sort(key=lambda p: os.path.getmtime(p))
        if not found:
            raise SystemExit(f"no video files found in {self.ws}")
        return found

    def probe_media(self, paths: list[str]) -> list[dict]:
        out = []
        for p in paths:
            r = self.b.probe(p)
            if not r["ok"]:
                raise SystemExit(f"probe failed for {p}: {r['result']}")
            info = r["result"]
            video = info.get("video") or {}
            fps = video.get("frame_rate") or {"num": 24, "den": 1}
            out.append({
                "path": p,
                "name": os.path.basename(p),
                "duration": int(info["duration"]),
                "width": int(video.get("width") or 1920),
                "height": int(video.get("height") or 1080),
                "fps": fps["num"] / fps["den"],
                "has_audio": bool(info.get("audio_streams")),
            })
        return out

    def pick_theme(self, text: str) -> dict:
        if self.theme_name in THEMES:
            base = dict(THEMES[self.theme_name])
        else:
            low = (text or "").lower()
            base = dict(THEMES["generic"])
            for key, theme in THEMES.items():
                if key != "generic" and any(w.lower() in low for w in theme["words"]):
                    base = dict(theme)
                    break
            if self.brief:
                low_brief = self.brief.lower()
                for key, theme in THEMES.items():
                    if key != "generic" and any(w.lower() in low_brief for w in theme["words"]):
                        base = dict(theme)
                        break
        for k, v in self.overrides.items():
            if v:
                base[k] = v
        # speech-driven copy: lines the speaker actually says become the graphics
        low = (text or "")
        for phrases, patch in PHRASE_RULES:
            if any(p in low for p in phrases):
                for k, v in patch.items():
                    if k not in self.overrides:
                        base[k] = v
        return base

    # ------------------------------------------------------------------ speech
    def transcribe_sequence(self) -> dict | None:
        """Export the sequence audio, run local Whisper, import it back into the project."""
        if not self.clips:
            return None
        wav = os.path.join(self.ws, ".fc_audio", f"{self.name}.wav")
        os.makedirs(os.path.dirname(wav), exist_ok=True)
        r = self.b.export(wav, fmt="wav", range_type="entire")
        if not r["ok"]:
            self.note("transcribe.export_failed", error=r["result"])
            return None
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("transcribe", os.path.join(HERE, "transcribe.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            result = mod.transcribe(wav, self.transcribe_model, self.language)
        except Exception as exc:  # noqa: BLE001 - reported, never fatal
            self.note("transcribe.failed", error=str(exc)[:500])
            return None
        payload = mod.to_filmcraft_payload(result)
        item = self.clips[0]["item"]
        imported = self.b.exec("transcript.set", {"item": item, "transcript": payload}, save=True)
        self.note("transcribe.done", words=len(payload["words"]), language=result.get("language"),
                  text=result.get("text", "")[:200], imported=imported["ok"])
        return result

    # ------------------------------------------------------------------ build
    def build(self) -> None:
        os.makedirs(self.out_dir, exist_ok=True)
        os.makedirs(self.render_dir, exist_ok=True)
        for p in (self.project, self.project + ".lock", os.path.join(self.ws, "." + os.path.basename(self.project) + ".lock")):
            if os.path.exists(p):
                os.remove(p)

        sources = self.discover()
        self.note("discover", files=[os.path.basename(p) for p in sources])
        infos = self.probe_media(sources)
        self.note("probe", media=[{k: v for k, v in i.items() if k != "path"} for i in infos])

        first = infos[0]
        fps = first["fps"] if first["fps"] > 0 else 24.0
        width = first["width"] if first["width"] > 0 else 1920
        height = first["height"] if first["height"] > 0 else 1080

        r = self.b.new_project(self.project, self.name.replace("_", " ").title())
        if not r["ok"]:
            raise SystemExit(f"newProject failed: {r}")

        self.run([Step("file.newSequence", {"name": "Main", "width": width, "height": height, "fps": fps})], "sequence")
        imported = self.b.import_media(sources)
        if not imported["ok"]:
            raise SystemExit(f"import failed: {imported}")
        items = imported["result"]["items"]
        self.note("import", items=items)

        # place every source back to back on V1, remembering its picture/audio clips
        cursor = 0
        frame = TICKS_PER_SECOND / fps
        for info, item in zip(infos, items):
            placed = self.run([Step("timeline.place", {"item": item, "track": "V1", "seconds": to_seconds(cursor)})],
                              f"place[{info['name']}]")
            ids = placed["timeline.place"]["clips"]
            dur = int(round(info["duration"] / frame) * round(frame))
            self.clips.append({
                "item": item, "name": info["name"], "path": info["path"],
                "video": ids[0] if ids else None,
                "audio": ids[1] if len(ids) > 1 else None,
                "start": cursor, "duration": dur,
            })
            cursor += dur
        self.note("timeline", clips=[(c["name"], c["video"], c["audio"]) for c in self.clips],
                  total_seconds=round(to_seconds(cursor), 3))

        # speech: transcript (+ silence tightening) before graphics are timed
        transcript = None
        if self.transcribe_enabled and (self.language == "ar" or self.captions or self.tighten):
            transcript = self.transcribe_sequence()
        if transcript and self.tighten > 0:
            r = self.b.exec("transcript.removePauses", {"minSeconds": self.tighten, "keepSeconds": 0.15}, save=True)
            self.note("transcript.removePauses", ok=r["ok"], result=r["result"])
        if transcript and self.captions:
            r = self.b.exec("transcript.createCaptions", {"maxChars": 40, "lines": 2}, save=True)
            self.note("transcript.createCaptions", ok=r["ok"], result=r["result"])
        self.captions_active = bool(transcript and self.captions)

        seq = self.b.inspect("sequence")["result"]
        self.sequence = seq
        total = to_seconds(seq["duration"])
        self.note("sequence.after_speech", frames=seq["durationFrames"], seconds=round(total, 3))

        # theme text: brief, transcript and media name all vote
        sample_text = " ".join([self.brief, os.path.basename(self.ws)] + [c["name"] for c in self.clips]
                               + ([transcript.get("text", "")] if transcript else []))
        self.theme = self.pick_theme(sample_text)
        self.note("theme", theme=self.theme)

        self.build_graphics(total)
        self.build_picture()
        self.save_and_export(bool(transcript and self.captions))
    def build_graphics(self, total: float) -> None:
        W = self.sequence["settings"]["width"]
        H = self.sequence["settings"]["height"]
        fps = self.sequence["settings"]["frame_rate"]["num"] / self.sequence["settings"]["frame_rate"]["den"]

        title_end = min(2.6, max(1.6, total * 0.34))
        lower_start = title_end + 0.3
        lower_end = max(lower_start + 1.0, total - 0.85)
        end_start = max(lower_end + 0.05, total - 0.75)
        end_end = total
        if lower_end - lower_start < 1.2:
            lower_start, lower_end = title_end + 0.1, total

        t = self.theme
        # ---- title card (a dark scrim + 3 type lines) ----
        scrim = self.run([Step("graphics.newShape", {
            "shape": "rectangle", "position": [W / 2, H / 2], "size": [W, H],
            "fill_color": "#000000", "seconds": title_end, "time": 0, "track": 1})], "title.scrim")
        title_clip = scrim["graphics.newShape"]["clip"]
        self.run([
            Step("graphics.newText", {"clip": title_clip, "text": t["ar_title"], "size": self.px(W, 92),
                                      "font": FONTS["ar_display"], "fontStyle": "Bold", "position": [W / 2, H * 0.46]}),
            Step("graphics.newText", {"clip": title_clip, "text": t["ar_kicker"], "size": self.px(W, 42),
                                      "font": FONTS["ar_text"], "fontStyle": "Semibold", "position": [W / 2, H * 0.59]}),
            Step("graphics.newText", {"clip": title_clip, "text": t["en_kicker"], "size": self.px(W, 22),
                                      "font": FONTS["en"], "fontStyle": "Semibold", "position": [W / 2, H * 0.675]}),
        ], "title.layers")
        self.run([
            Step("graphics.set", {"clip": title_clip, "layer": 0, "props": {"fill_color": "#000000", "opacity": 46}}),
            Step("graphics.set", {"clip": title_clip, "layer": 1, "props": {
                "fill_color": COLORS["white"], "align": "center", "tracking": 0,
                "shadow": True, "shadow_color": "#001018", "shadow_opacity": 75,
                "shadow_distance": 4, "shadow_size": 10, "shadow_blur": 28}}),
            Step("graphics.set", {"clip": title_clip, "layer": 2, "props": {
                "fill_color": COLORS["cyan"], "align": "center", "tracking": 0}}),
            Step("graphics.set", {"clip": title_clip, "layer": 3, "props": {
                "fill_color": "#E6F7FF", "align": "center", "tracking": 12}}),
        ], "title.style")
        self.fade_graphic(title_clip, [(0.0, 0), (0.18, 46), (title_end - 0.35, 46), (title_end, 0)], layer=0)
        self.fade_graphic(title_clip, [(0.0, 0), (0.35, 100), (title_end - 0.40, 100), (title_end, 0)], layer=1)
        self.fade_graphic(title_clip, [(0.12, 0), (0.5, 100), (title_end - 0.40, 100), (title_end, 0)], layer=2)
        self.fade_graphic(title_clip, [(0.25, 0), (0.7, 100), (title_end - 0.40, 100), (title_end, 0)], layer=3)
        self.note("title.card", clip=title_clip, seconds=[0, round(title_end, 2)])

        if self.captions_active:
            self.note("lower.third", skipped="captions occupy the lower band")
        else:
            self.build_lower_third(W, H, t, lower_start, lower_end)

        # ---- end card ----
        end_span = max(0.5, end_end - end_start)
        end = self.run([Step("graphics.newText", {
            "text": t["ar_end"], "size": self.px(W, 46), "font": FONTS["ar_display"], "fontStyle": "Bold",
            "position": [W / 2, H * 0.47], "seconds": end_span, "time": seconds(end_start), "track": 2})], "end.text")
        end_clip = end["graphics.newText"]["clip"]
        self.run([
            Step("graphics.newText", {"clip": end_clip, "text": t["en_kicker"], "size": self.px(W, 20),
                                      "font": FONTS["en"], "fontStyle": "Semibold",
                                      "position": [W / 2, H * 0.55]}),
            Step("graphics.set", {"clip": end_clip, "layer": 0, "props": {
                "fill_color": COLORS["white"], "align": "center", "tracking": 0,
                "shadow": True, "shadow_color": "#000000", "shadow_opacity": 70,
                "shadow_distance": 3, "shadow_size": 10, "shadow_blur": 24}}),
            Step("graphics.set", {"clip": end_clip, "layer": 1, "props": {
                "fill_color": COLORS["cyan"], "align": "center", "tracking": 10}}),
        ], "end.style")
        self.fade_graphic(end_clip, [(end_start, 0), (min(end_start + 0.35, end_end), 100)], layer=0)
        self.fade_graphic(end_clip, [(end_start, 0), (min(end_start + 0.45, end_end), 100)], layer=1)
        self.note("end.card", clip=end_clip, seconds=[round(end_start, 2), round(end_end, 2)])

    def build_lower_third(self, W: int, H: int, t: dict, lower_start: float, lower_end: float) -> None:
        """The three-line lower third: a dark bar, a cyan rule and the copy, sliding up."""
        span = lower_end - lower_start
        bar = self.run([Step("graphics.newShape", {
            "shape": "rectangle", "position": [W / 2, H * 0.84], "size": [self.px(W, 900), self.px(W, 152)],
            "fill_color": COLORS["ink"], "seconds": span, "time": seconds(lower_start), "track": 1})], "lower.bar")
        bar_clip = bar["graphics.newShape"]["clip"]
        accent_y = H * 0.84 - self.px(W, 80)
        self.run([
            Step("graphics.newShape", {"clip": bar_clip, "shape": "rectangle",
                                       "position": [W / 2, accent_y], "size": [self.px(W, 900), self.px(W, 5)],
                                       "fill_color": COLORS["accent"]}),
            Step("graphics.newText", {"clip": bar_clip, "text": t["ar_lower"], "size": self.px(W, 46),
                                      "font": FONTS["ar_display"], "fontStyle": "Bold",
                                      "position": [W / 2, H * 0.815]}),
            Step("graphics.newText", {"clip": bar_clip, "text": t["en_lower"], "size": self.px(W, 19),
                                      "font": FONTS["en"], "fontStyle": "Semibold",
                                      "position": [W / 2, H * 0.878]}),
            Step("graphics.newText", {"clip": bar_clip, "text": t["ar_sub"], "size": self.px(W, 24),
                                      "font": FONTS["ar_text"], "fontStyle": "Regular",
                                      "position": [W / 2, H * 0.927]}),
        ], "lower.layers")
        self.run([
            Step("graphics.set", {"clip": bar_clip, "layer": 0, "props": {"fill_color": COLORS["ink"], "opacity": 84}}),
            Step("graphics.set", {"clip": bar_clip, "layer": 1, "props": {"fill_color": COLORS["accent"], "opacity": 95}}),
            Step("graphics.set", {"clip": bar_clip, "layer": 2, "props": {
                "fill_color": COLORS["white"], "align": "center", "tracking": 0}}),
            Step("graphics.set", {"clip": bar_clip, "layer": 3, "props": {
                "fill_color": COLORS["cyan"], "align": "center", "tracking": 10}}),
            Step("graphics.set", {"clip": bar_clip, "layer": 4, "props": {
                "fill_color": COLORS["soft"], "align": "center", "tracking": 0}}),
        ], "lower.style")
        self.fade_graphic(bar_clip, [(lower_start, 0), (lower_start + 0.3, 84),
                                     (lower_end - 0.3, 84), (lower_end, 0)], layer=0)
        self.fade_graphic(bar_clip, [(lower_start, 0), (lower_start + 0.35, 95),
                                     (lower_end - 0.3, 95), (lower_end, 0)], layer=1)
        self.fade_graphic(bar_clip, [(lower_start + 0.05, 0), (lower_start + 0.4, 100),
                                     (lower_end - 0.3, 100), (lower_end, 0)], layer=2)
        self.fade_graphic(bar_clip, [(lower_start + 0.1, 0), (lower_start + 0.45, 100),
                                     (lower_end - 0.3, 100), (lower_end, 0)], layer=3)
        self.fade_graphic(bar_clip, [(lower_start + 0.15, 0), (lower_start + 0.5, 100),
                                     (lower_end - 0.3, 100), (lower_end, 0)], layer=4)
        self.slide_graphic(bar_clip, [0, 1, 2, 3, 4], lower_start, [H * 0.84, accent_y, H * 0.815, H * 0.878, H * 0.927], 26)
        self.note("lower.third", clip=bar_clip, seconds=[round(lower_start, 2), round(lower_end, 2)])

    def px(self, width: int, value: float) -> float:
        """Scale a 1280-wide design value to the actual frame width."""
        return round(value * width / 1280.0, 2)

    def fade_graphic(self, clip: int, points: list[tuple[float, float]], layer: int) -> None:
        steps = []
        for i, (at, value) in enumerate(points):
            params: dict = {"clip": clip, "layer": layer, "props": {"opacity": value}, "time": seconds(at)}
            if i == 0:
                params["keyframe"] = True
            steps.append(Step("graphics.set", params))
        self.run(steps, f"fade[{clip}:{layer}]")

    def slide_graphic(self, clip: int, layers: list[int], start: float, ys: list[float], dy: float) -> None:
        W = self.sequence["settings"]["width"]
        steps = []
        for layer, y in zip(layers, ys):
            steps.append(Step("graphics.set", {"clip": clip, "layer": layer,
                                              "props": {"position": [W / 2, y + dy]},
                                              "time": seconds(start), "keyframe": True}))
            steps.append(Step("graphics.set", {"clip": clip, "layer": layer,
                                              "props": {"position": [W / 2, y]},
                                              "time": seconds(start + 0.4)}))
        self.run(steps, f"slide[{clip}]")

    # ------------------------------------------------------------------ picture
    def build_picture(self) -> None:
        total = to_seconds(self.sequence["duration"])
        fade_out_at = max(0.0, total - 0.7)
        for i, clip in enumerate(self.clips):
            vid = clip["video"]
            if not vid:
                continue
            self.run([
                Step("effects.apply", {"clips": [vid], "effect": "lumetri"}),
                Step("effects.apply", {"clips": [vid], "effect": "vignette"}),
            ], f"picture.effects[{i}]")
            self.run([
                Step("effects.setParam", {"clip": vid, "effect": "lumetri", "param": "look", "value": "Cool Blue"}),
                Step("effects.setParam", {"clip": vid, "effect": "lumetri", "param": "look_intensity", "value": 40}),
                Step("effects.setParam", {"clip": vid, "effect": "lumetri", "param": "contrast", "value": 7}),
                Step("effects.setParam", {"clip": vid, "effect": "lumetri", "param": "saturation", "value": 105}),
                Step("effects.setParam", {"clip": vid, "effect": "lumetri", "param": "shadows", "value": -7}),
                Step("effects.setParam", {"clip": vid, "effect": "lumetri", "param": "highlights", "value": -8}),
                Step("effects.setParam", {"clip": vid, "effect": "lumetri", "param": "sharpen", "value": 10}),
                Step("effects.setParam", {"clip": vid, "effect": "vignette", "param": "amount", "value": -26}),
                Step("effects.setParam", {"clip": vid, "effect": "vignette", "param": "midpoint", "value": 55}),
                Step("effects.setParam", {"clip": vid, "effect": "vignette", "param": "feather", "value": 60}),
            ], f"picture.grade[{i}]")
            start = to_seconds(clip["start"])
            end = to_seconds(clip["start"] + clip["duration"])
            self.run([
                Step("effects.setParam", {"clip": vid, "effect": "motion", "param": "scale",
                                          "value": 100, "seconds": start, "keyframe": True}),
                Step("effects.setParam", {"clip": vid, "effect": "motion", "param": "scale",
                                          "value": 107, "seconds": end - 0.05}),
            ], f"picture.push[{i}]")
            if i == len(self.clips) - 1:
                self.run([
                    Step("effects.setParam", {"clip": vid, "effect": "opacity", "param": "opacity",
                                              "value": 100, "seconds": fade_out_at, "keyframe": True}),
                    Step("effects.setParam", {"clip": vid, "effect": "opacity", "param": "opacity",
                                              "value": 0, "seconds": total - 0.04}),
                ], "picture.fadeout")
        # audio fades on the first and last sound clips
        audio = [c for c in self.clips if c.get("audio")]
        if audio:
            first, last = audio[0], audio[-1]
            steps = [Step("effects.setParam", {"clip": first["audio"], "effect": "volume", "param": "level",
                                               "value": -28, "seconds": to_seconds(first["start"]), "keyframe": True}),
                     Step("effects.setParam", {"clip": first["audio"], "effect": "volume", "param": "level",
                                               "value": 0, "seconds": to_seconds(first["start"]) + 0.5})]
            if last is first:
                steps += [Step("effects.setParam", {"clip": last["audio"], "effect": "volume", "param": "level",
                                                    "value": 0, "seconds": max(0.0, total - 0.8)}),
                          Step("effects.setParam", {"clip": last["audio"], "effect": "volume", "param": "level",
                                                    "value": -45, "seconds": total - 0.05})]
            else:
                steps += [Step("effects.setParam", {"clip": last["audio"], "effect": "volume", "param": "level",
                                                    "value": 0, "seconds": max(0.0, total - 0.85), "keyframe": True}),
                          Step("effects.setParam", {"clip": last["audio"], "effect": "volume", "param": "level",
                                                    "value": -45, "seconds": total - 0.05})]
            self.run(steps, "audio.fades")

        if len(self.clips) > 1 and self.transition == "cross_dissolve":
            frames = 12
            for clip in self.clips[:-1]:
                vid = clip["video"]
                if not vid:
                    continue
                r = self.b.exec("sequence.applyVideoTransition", {"clip": vid, "effect": "cross_dissolve",
                                                                 "frames": frames, "edge": "out"}, save=True)
                self.note("transition", clip=vid, ok=r["ok"])

    # ------------------------------------------------------------------ export
    def save_and_export(self, burn_captions: bool) -> None:
        self.b.run_script([], save=True)
        self.sequence = self.b.inspect("sequence")["result"]
        if self.do_export:
            presets = self.b.list_presets("match source")["result"]
            preset = next((p["name"] for p in presets if "Adaptive High Bitrate" in p["name"]),
                          "Match Source \u2013 Adaptive High Bitrate")
            settings = {"burnCaptions": True} if burn_captions else None
            if settings:
                r = self.b.exec("file.exportMedia", {"path": self.output, "preset": preset,
                                                     "range": "entire", "wait": True, **settings}, save=False)
                self.note("export", ok=r["ok"], output=self.output,
                          bytes=os.path.getsize(self.output) if os.path.exists(self.output) else 0)
            else:
                exported = self.b.export(self.output, preset=preset, range_type="entire")
                self.note("export", ok=exported["ok"], output=self.output,
                          bytes=os.path.getsize(self.output) if os.path.exists(self.output) else 0,
                          reply=exported["result"].get("result") if isinstance(exported["result"], dict) else None)
                if not exported["ok"]:
                    raise SystemExit(f"export failed: {exported}")

        manifest = {
            "workspace": self.ws,
            "project": self.project,
            "output": self.output,
            "sequence": {"id": self.sequence["id"], "name": self.sequence["name"],
                         "frames": self.sequence["durationFrames"],
                         "size": [self.sequence["settings"]["width"], self.sequence["settings"]["height"]],
                         "fps": self.sequence["settings"]["frame_rate"]},
            "clips": [{k: v for k, v in c.items() if k != "path"} for c in self.clips],
            "theme": self.theme,
            "log": self.log,
        }
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        self.note("manifest", path=self.manifest_path)

    # ------------------------------------------------------------------ verify
    def verify(self, times: list[float] | None = None) -> bool:
        """Re-import the exported MP4 and compare its frames with the project renders."""
        if not os.path.exists(self.output):
            return False
        verify_project = os.path.join(self.ws, ".fc_verify", f"{self.name}_check.fcproj")
        os.makedirs(os.path.dirname(verify_project), exist_ok=True)
        for p in (verify_project, verify_project + ".lock",
                  os.path.join(os.path.dirname(verify_project), "." + os.path.basename(verify_project) + ".lock")):
            if os.path.exists(p):
                os.remove(p)
        vb = FilmCraftBridge(project=verify_project, workspace=self.ws)
        vb.new_project(verify_project, "verify")
        vb.run_script([Step("file.newSequence", {"name": "V", "width": self.sequence["settings"]["width"],
                                                 "height": self.sequence["settings"]["height"],
                                                 "fps": self.sequence["settings"]["frame_rate"]["num"]})])
        item = vb.import_media([self.output])["result"]["items"][0]
        vb.run_script([Step("timeline.place", {"item": item, "track": "V1", "seconds": 0})])
        total = to_seconds(self.sequence["duration"])
        checks = times or [0.6, total * 0.45, total - 0.2]
        from PIL import Image, ImageChops, ImageStat
        ok = True
        results = []
        for t in checks:
            exported_png = os.path.join(self.render_dir, f"{self.name}_mp4_{round(t, 2)}.png")
            project_png = os.path.join(self.render_dir, f"{self.name}_proj_{round(t, 2)}.png")
            vb.render(t, exported_png)
            self.b.render(t, project_png)
            diff = ImageStat.Stat(ImageChops.difference(Image.open(exported_png).convert("RGB"),
                                                       Image.open(project_png).convert("RGB"))).mean
            same = max(diff) < 8.0
            ok = ok and same
            results.append({"seconds": round(t, 2), "mean_abs_diff": [round(x, 2) for x in diff], "match": same})
        self.note("verify", match=ok, results=results)
        self.persist_verification(ok, results)
        return ok

    def persist_verification(self, ok: bool, results: list[dict]) -> None:
        """Fold the verification result into the manifest so the delivered files are auditable."""
        try:
            with open(self.manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:  # noqa: BLE001 - the manifest is optional here
            manifest = {"workspace": self.ws, "project": self.project, "output": self.output}
        manifest["verified"] = ok
        manifest["verification"] = results
        manifest["log"] = self.log
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)


def main() -> None:
    ap = argparse.ArgumentParser(description="FilmCraft creative montage engine")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--name", default="filmcraft_edit")
    ap.add_argument("--language", default="ar", choices=["ar", "en"])
    ap.add_argument("--media", nargs="*", default=None, help="explicit files instead of discovery")
    ap.add_argument("--brief", default="", help="natural-language brief, used to pick the theme")
    ap.add_argument("--theme", default="auto", choices=["auto", "security", "generic"])
    ap.add_argument("--transcribe-model", default="openai/whisper-small")
    ap.add_argument("--captions", action="store_true", help="burn captions from the transcript")
    ap.add_argument("--tighten", type=float, default=0.0, help="remove pauses longer than this many seconds")
    ap.add_argument("--no-export", action="store_true")
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--no-transcribe", action="store_true")
    ap.add_argument("--title", default=None)
    ap.add_argument("--subtitle", default=None)
    args = ap.parse_args()

    overrides = {}
    if args.title:
        overrides["ar_title"] = args.title
    if args.subtitle:
        overrides["ar_kicker"] = args.subtitle
    studio = Studio(workspace=args.workspace, name=args.name, language=args.language,
                    media=args.media, brief=args.brief, theme=args.theme,
                    transcribe_model=args.transcribe_model, captions=args.captions,
                    tighten=args.tighten, export=not args.no_export, overrides=overrides,
                    transcribe=not args.no_transcribe)
    studio.build()
    if not args.no_export:
        ok = studio.verify() if not args.no_verify else True
        log(f"DONE project={studio.project} output={studio.output} verified={ok}")
        if not ok:
            raise SystemExit(1)
    else:
        log(f"DONE (no export) project={studio.project}")


if __name__ == "__main__":
    main()
