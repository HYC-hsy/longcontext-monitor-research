"""Model-owned, revisable grounds for the latest advice; no semantic matching."""

from __future__ import annotations

import copy
import hashlib
import uuid


ADVICE_PATH = "monitor/advice.md"
ADVICE_PROMPT = """intervene optionally accepts a private basis: a short natural note about the grounds
for your advice and what could change your mind. Only message is sent to the Task Agent. A missing basis
never prevents intervention. The latest advice is saved in monitor/advice.md and brought back when you
resume following it. This is your provisional interpretation, not another task instruction or a verdict.
As you observe the response, reconsider both the requested repair and its grounds. You may revise or clear
this note using the ordinary file tools; retract or clarify advice with an ordinary intervention when
needed. No mandatory experiment or confirmation format is required. This local note is not a list of all
open requirements: retain other concerns and root scope in your working understanding and history."""


def advice_tools(tools):
    result = copy.deepcopy(tools)
    tool = next(t["function"] for t in result if t["function"]["name"] == "intervene")
    tool["parameters"]["properties"]["basis"] = {
        "type": "string",
        "description": "Optional private grounds and uncertainty for this advice; not sent to the Task Agent.",
    }
    return result


class AdviceBasis:
    def __init__(self, workspace, atomic_write):
        self.workspace = workspace
        self.atomic_write = atomic_write
        self.seen = None

    def begin_review(self):
        self.seen = None

    def _archive(self, text):
        path = "audit/advice/" + uuid.uuid4().hex + ".md"
        self.atomic_write(path, text)
        return "monitor/" + path

    def record(self, message, basis):
        path = self.workspace.resolve_private(ADVICE_PATH)
        if path.exists():
            self._archive(path.read_text(encoding="utf-8"))
        text = ("Latest advice (delivery and uptake require separate evidence):\n" + message
                + "\n\nPrivate grounds, open to revision:\n"
                + (basis.strip() or "No separate grounds were recorded; consult the originating dialogue.")
                + "\n")
        self.atomic_write("advice.md", text)
        archive = self._archive(text)
        # Already visible in this tool exchange; restore on the next wake.
        self.seen = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return {"path": ADVICE_PATH, "archive": archive}

    def refresh(self):
        path = self.workspace.resolve_private(ADVICE_PATH)
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if digest == self.seen:
            return None
        archive = self._archive(text)
        self.seen = digest
        # A navigation preview, never a claim to have supplied the entire note.
        preview = text[:6000]
        remainder = ("\n[Preview ends; the rest remains readable in monitor/advice.md.]"
                     if len(text) > len(preview) else "")
        return ("Private revisable advice context, not task evidence. Other root concerns remain in "
                "the original task and working history. Source: " + ADVICE_PATH + "; version: "
                + archive + "\n" + (preview or "The local note has been cleared; this does not approve root completion.")
                + remainder)
