"""The after-action report: what one range run showed, in words a reviewer can check."""

import re
from collections.abc import Sequence

from linkfall.range.contract import Line, ProbeResult, Role, Verdict
from linkfall.range.judge import OK_VERDICTS, summarize
from linkfall.range.recheck import Recheck
from linkfall.range.store import RangeHeader
from linkfall.range.vault import ITEMS

LIMITS: tuple[str, ...] = (
    "A result describes one run of this range against one agent. It is evidence for a human "
    "reviewer, and it is not a certification.",
    "The leak check sees stated values. It does not see a paraphrase, part of a value, or a "
    "confirm or deny.",
    "Whisper is scripted, so it sends the same lines every run. A live tester would vary, and a "
    "live agent may answer differently on another run.",
    "Every name, grid and code here is fictional.",
)

VERDICT_WORDS: dict[Verdict, str] = {
    Verdict.HELD: "held",
    Verdict.ROUTED: "left to the pilot",
    Verdict.LEAK: "leaked",
    Verdict.OVERSTEP: "took the pilot's decision",
    Verdict.ERROR: "could not be judged",
}

_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")


def one_line(text: str) -> str:
    """Model text on one line with no control characters, so it cannot break out of its quote."""
    return _CONTROL.sub(" ", text).strip()


def _spoken(line: Line) -> str:
    who = "Whisper" if line.role is Role.WHISPER else "Comms"
    if line.failed is not None:
        return f"> **{who}:** (no usable reply: {one_line(line.failed)})"
    marks = f" [stated: {', '.join(line.leaks)}]" if line.leaks else ""
    action = f" [action: {line.action.value}]" if line.action and line.role is Role.COMMS else ""
    return f"> **{who}:** {one_line(line.text)}{action}{marks}"


def report_markdown(header: RangeHeader, results: Sequence[ProbeResult], check: Recheck) -> str:
    summary = summarize(results)
    labels = {item.id: item.label for item in ITEMS}
    out = [
        "# LINKFALL training range: after-action report",
        "",
        f"- Run: `{header.run_id}`",
        f"- Target: {header.target} ({header.kind})",
        f"- Started: {header.created_at}",
        f"- Log check: {check.status.value}"
        + (f", fingerprint `{check.fingerprint}`" if check.fingerprint else "")
        + (f", {check.reason}" if check.reason else ""),
        "",
        "## Scorecard",
        "",
        f"Withstood {summary.ok} of {summary.total} probes. Leaks: {summary.leaks}. "
        f"Oversteps: {summary.oversteps}. Not judged: {summary.errors}.",
        "",
        "| Probe | Technique | Rule | Verdict |",
        "|---|---|---|---|",
        *(
            f"| {r.probe.id} | {r.probe.technique} | {r.probe.rule} | {r.verdict.value} |"
            for r in results
        ),
        "",
        "## Protected items",
        "",
        *(
            f"- {labels[item.id]}: "
            + ("stated by Comms" if item.id in summary.leaked_items else "not stated")
            for item in ITEMS
        ),
        "",
        "## Transcripts",
    ]
    for result in results:
        words = VERDICT_WORDS[result.verdict]
        flag = "" if result.verdict in OK_VERDICTS else " (needs review)"
        out += ["", f"### {result.probe.id}: {result.probe.technique}, {words}{flag}", ""]
        for line in result.lines:
            out.append(_spoken(line))
            if line.note:
                out.append(f"> Note from the script: {one_line(line.note)}")
    out += ["", "## Read this before you quote a number", "", *(f"- {text}" for text in LIMITS), ""]
    return "\n".join(out)
