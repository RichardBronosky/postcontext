"""Drive a real, logged-in Chrome/Chromium through agent-browser (CDP).

You bring the browser: start Chrome/Chromium with `--remote-debugging-port=9222`
(a dedicated profile is best), log in to Instagram/Facebook in it yourself, and
postcontext reads pages in one labelled tab of its own. It never logs in, solves
checks or clicks consent dialogs; a login wall is reported as an error.

Settings (environment):
  POSTCONTEXT_CDP_PORT   DevTools port (default 9222)
  POSTCONTEXT_SESSION    agent-browser session name (default "postcontext")
  POSTCONTEXT_TAB_SCRIPTS  directory with tab-new / session-done / browser-up helper
                         scripts (the collaborative-chromium skill). Used when present,
                         so a shared browser never has its other tabs taken over."""

import json
import logging
import os
import subprocess
import time
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

JS_DIR = Path(__file__).parent / "js"
LABEL = "postcontext"
DEFAULT_SCRIPTS = Path.home() / ".agents/skills/collaborative-chromium/scripts"


class BrowserError(Exception):
    pass


class Browser:
    def __init__(self, session: str | None = None, port: int | None = None):
        self.session = session or os.environ.get("POSTCONTEXT_SESSION", "postcontext")
        self.port = int(port or os.environ.get("POSTCONTEXT_CDP_PORT", "9222"))
        scripts = Path(os.environ.get("POSTCONTEXT_TAB_SCRIPTS", DEFAULT_SCRIPTS))
        self.scripts = scripts if (scripts / "tab-new").exists() else None
        self.started = False

    def _ab(self, *args: str, timeout: int = 60) -> str:
        cmd = ["agent-browser", "--cdp", str(self.port), "--pin-tab", "--session", self.session, *args]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError as e:
            raise BrowserError("agent-browser is not installed (npm i -g agent-browser)") from e
        if p.returncode != 0:
            err = (p.stderr or p.stdout).strip()
            if "tab_gone" in err or "bound tab is gone" in err:
                self.started = False
            raise BrowserError(f"agent-browser {args[0]}: {err[-300:]}")
        return p.stdout

    def _pages(self) -> list[dict]:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/list", timeout=5) as r:
                return json.load(r)
        except OSError as e:
            raise BrowserError(f"no browser with remote debugging on port {self.port}") from e

    def _own_tab_alive(self) -> bool:
        """Is the tab recorded for our label still open? Checked through DevTools, not
        agent-browser: asking agent-browser about a session with no tab would make it
        adopt someone else's tab."""
        labels = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "agent-browser" / f"{self.session}.hub-labels"
        try:
            target = json.loads(labels.read_text()).get(LABEL)
        except (OSError, ValueError):
            return False
        return bool(target) and any(p.get("id") == target for p in self._pages())

    def start(self, url: str) -> None:
        if self.scripts:
            subprocess.run([str(self.scripts / "browser-up")], capture_output=True, timeout=60)
        self._pages()  # fail early with a clear message if no browser is listening
        if self._own_tab_alive():
            self._ab("tab", LABEL)
            self._ab("open", url)
        elif self.scripts:
            p = subprocess.run([str(self.scripts / "tab-new"), self.session, LABEL, url],
                               capture_output=True, text=True, timeout=60)
            if p.returncode != 0:
                raise BrowserError(f"tab-new: {(p.stderr or p.stdout).strip()[-300:] or 'failed'}")
        else:
            self._ab("tab", "new", "--label", LABEL, url)
        self.started = True

    def open(self, url: str, settle: float = 5.0) -> None:
        if not self.started:
            self.start(url)
        else:
            try:
                self._ab("open", url)
            except BrowserError:
                if self.started:
                    raise
                self.start(url)  # our tab was closed; make a new one
        time.sleep(settle)

    def eval(self, js: str):
        out = self._ab("eval", js).strip()
        val = json.loads(out) if out else None
        # Scripts return JSON.stringify(...), so values come back as a JSON string.
        return json.loads(val) if isinstance(val, str) and val[:1] in "{[" else val

    def script(self, name: str):
        return self.eval((JS_DIR / name).read_text())

    def url(self) -> str:
        return self._ab("get", "url").strip()

    def close(self) -> None:
        if self.scripts:
            subprocess.run([str(self.scripts / "session-done"), self.session, LABEL], capture_output=True, timeout=60)
        else:
            subprocess.run(["agent-browser", "--cdp", str(self.port), "--session", self.session, "close"],
                           capture_output=True, timeout=60)
        self.started = False
