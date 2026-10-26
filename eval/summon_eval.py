"""Describe 18 real deleted functions (each read before describing) and see where the right one ranks.
Baseline: keyword matching, i.e. rank ghosts by how many query words appear in their code (grep-style)."""
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import seance  # noqa: E402

QUERIES = [
    ("flag dangerous shell commands like rm -rf or sudo", "detectCommandWarnings"),
    ("build the activity feed from chat messages and tool calls", "deriveActivity"),
    ("show the level, number of regions and observation time on the map page", "renderMeta"),
    ("validate a request to add an MCP server, with length limits on each field", "normalizeMcpServerProposalInput"),
    ("propose a new MCP server unless the same proposal is already pending", "proposeMcpServer"),
    ("replace the set of allowed tool names, ignoring blank ones", "setAvailableToolNames"),
    ("parse the flags of the sessions slash command, like pick and search", "parseSessionsCommand"),
    ("turn a slash command typed in the terminal UI into a command object", "parseTuiSlashCommand"),
    ("coloured icon line for a tool call, result or error in the terminal", "formatInlineActivity"),
    ("work out the screenshot scale ratio, ignoring captures clipped at the screen edge", "captureScaleFactor"),
    ("retry the email verification with a different method when it fails", "retry"),
    ("decide whether an email check failed for a reason we already know about", "has_known_errors"),
    ("reuse a cached MongoDB connection between serverless calls", "connectToDatabase"),
    ("get pasted images out of the clipboard", "imageFilesFromClipboard"),
    ("pull the before and after diff out of an approval message", "parseApprovalDiff"),
    ("wait until the window has painted before continuing", "waitForRendererPaint"),
    ("look up a value by name, falling back to a canonical form of the name", "lookupByName"),
    ("fetch current temperatures for regions from their centroids", "temperaturesFor"),
]


def words(s):
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    return set(re.findall(r"[a-z0-9]{3,}", s.lower()))


meta, doc = seance.load()
codes = [words(m["code"]) for m in meta]


def rank(order, want):
    names, seen = [], set()
    for i in order:
        if meta[i]["hash"] not in seen:
            seen.add(meta[i]["hash"])
            names.append(meta[i]["name"])
    return names.index(want) + 1


q = seance.embed_here([t for t, _ in QUERIES], seance.QUERY_PREFIX)
hits = {"seance": [], "keywords": []}
for (text, want), v in zip(QUERIES, q):
    a = rank(np.argsort(-(doc @ v)), want)
    kw = np.array([len(words(text) & c) for c in codes])
    b = rank(np.argsort(-kw, kind="stable"), want)
    hits["seance"].append(a)
    hits["keywords"].append(b)
    print(f"{a:>3} {b:>4}  {want:<32} {text}")
n = len({m['hash'] for m in meta})
for k, r in hits.items():
    print(f"{k:<9} top-1 {sum(x == 1 for x in r)}/{len(r)}  top-5 {sum(x <= 5 for x in r)}/{len(r)}  (out of {n} unique ghosts)")
