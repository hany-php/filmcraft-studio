"""bridge.py — FilmCraft <-> Python bridge.

Drives the installed FilmCraft CLI (headless engine) so an agent can turn a natural
language request into a real, saved montage project and an exported video.

Design rules (the constitution of this plugin):
  * the CLI (`filmcraft-cli.exe`) is the only transport: one subprocess per call,
    no sockets, no firewall issues;
  * every edit runs inside the user's workspace folder; the .fcproj lives there so
    every change stays reviewable and re-editable;
  * a batch of edits is sent as ONE `run` script so selection/playhead state and the
    undo history behave exactly like a human session in the app.

Time unit: FilmCraft ticks, 254 016 000 000 per second.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

CLI_PATH = r"C:\Program Files\ArtCraft\FilmCraft\filmcraft-cli.exe"

TICKS_PER_SECOND = 254_016_000_000


def seconds(value: float) -> int:
    """Seconds -> FilmCraft ticks (rounded to the tick)."""
    return int(round(float(value) * TICKS_PER_SECOND))


def to_seconds(ticks: int) -> float:
    return float(ticks) / TICKS_PER_SECOND


@dataclass
class Step:
    """One engine command inside a `run` script."""

    id: str
    params: dict[str, Any] = field(default_factory=dict)

    def as_line(self) -> str:
        return json.dumps({"id": self.id, "params": self.params}, ensure_ascii=False)


class FilmCraftBridge:
    """Thin, always-JSON wrapper around filmcraft-cli."""

    def __init__(self, cli_path: str = CLI_PATH, project: str | None = None, workspace: str | None = None):
        self.cli_path = cli_path
        self.project = os.path.abspath(project) if project else None
        self.workspace = os.path.abspath(workspace) if workspace else (os.path.dirname(self.project) if self.project else os.getcwd())

    # ------------------------------------------------------------------ transport
    def _run(self, args: Sequence[str], stdin: str | None = None, timeout: float = 1800.0) -> tuple[int, str, str]:
        proc = subprocess.run(
            [self.cli_path, *args],
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def _json(self, args: Sequence[str], stdin: str | None = None) -> dict[str, Any]:
        code, out, err = self._run(args, stdin)
        try:
            data = json.loads(out) if out.strip() else {}
        except json.JSONDecodeError:
            data = {"raw": out}
        return {"ok": code == 0, "exit": code, "result": data, "stderr": err.strip()}

    def _project_args(self, save: bool, project: str | None) -> list[str]:
        proj = project or self.project
        args: list[str] = []
        if proj:
            args += ["--project", proj]
            if save:
                args.append("--save")
        return args

    # ------------------------------------------------------------------ primitives
    def new_project(self, path: str, name: str) -> dict[str, Any]:
        """Create an empty project and save it at `path`."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        res = self._json(["--save-as", os.path.abspath(path), "exec", "file.newProject", f"name={name}"])
        self.project = os.path.abspath(path)
        return res

    def exec(self, command: str, params: dict[str, Any] | None = None, save: bool = True, project: str | None = None) -> dict[str, Any]:
        """Run one engine command on the project."""
        args = self._project_args(save, project) + ["exec", command]
        if params:
            args.append(json.dumps(params, ensure_ascii=False))
        return self._json(args)

    def run_script(
        self,
        steps: Iterable[Step | dict[str, Any] | tuple[str, dict[str, Any]]],
        save: bool = True,
        keep_going: bool = False,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run ordered commands in ONE headless session (`run -`), saving once at the end."""
        lines: list[str] = []
        for step in steps:
            if isinstance(step, Step):
                lines.append(step.as_line())
            elif isinstance(step, dict):
                lines.append(json.dumps(step, ensure_ascii=False))
            else:
                cmd, params = step
                lines.append(json.dumps({"id": cmd, "params": params or {}}, ensure_ascii=False))
        script = "\n".join(lines) + "\n"
        args = self._project_args(save, project)
        if keep_going:
            args.append("--keep-going")
        args += ["run", "-"]
        code, out, err = self._run(args, stdin=script)
        results = [json.loads(line) for line in out.splitlines() if line.strip().startswith("{")]
        return [{"ok": code == 0, "exit": code, "lines": results, "stderr": err.strip()}]

    def import_media(self, paths: Sequence[str], save: bool = True, project: str | None = None) -> dict[str, Any]:
        args = self._project_args(save, project) + ["import", *[os.path.abspath(p) for p in paths]]
        return self._json(args)

    def inspect(self, what: str = "", project: str | None = None) -> dict[str, Any]:
        args = self._project_args(False, project) + ["inspect"]
        if what:
            args.append(what)
        return self._json(args)

    def probe(self, media: str) -> dict[str, Any]:
        return self._json(["probe", os.path.abspath(media)])

    def render(self, seconds_at: float, out: str, scale: float | None = None, project: str | None = None) -> dict[str, Any]:
        args = self._project_args(False, project) + ["render", "--seconds", str(seconds_at), "--out", os.path.abspath(out)]
        if scale:
            args += ["--scale", str(scale)]
        return self._json(args)

    def export(
        self,
        out: str,
        preset: str | None = None,
        fmt: str | None = None,
        range_type: str = "entire",
        quality: int | None = None,
        project: str | None = None,
    ) -> dict[str, Any]:
        args = self._project_args(False, project) + ["export", os.path.abspath(out), "--range", range_type]
        if preset:
            args += ["--preset", preset]
        if fmt:
            args += ["--format", fmt]
        if quality is not None:
            args += ["--quality", str(quality)]
        return self._json(args)

    def list_presets(self, query: str = "") -> dict[str, Any]:
        args = ["export", "--list-presets"]
        if query:
            args.append(query)
        return self._json(args)

    def commands(self, filter_text: str = "") -> dict[str, Any]:
        args = ["commands", "--json"]
        if filter_text:
            args.append(filter_text)
        return self._json(args)

    def describe(self, command: str) -> dict[str, Any]:
        return self._json(self._project_args(False, None) + ["describe", command])


if __name__ == "__main__":
    b = FilmCraftBridge()
    code, out, err = b._run(["--version"])
    print(out.strip() or err.strip())
