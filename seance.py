"""Git Séance: summon deleted functions back from your git history by describing them."""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

import numpy as np

from extract import LANGS, excluded, functions_in

HOME = os.path.expanduser(os.environ.get("SEANCE_HOME", "~/.seance"))
MODEL = "google/embeddinggemma-2"
QUERY_PREFIX = "task: code retrieval | query: "
DIM = 256
PORT = int(os.environ.get("DEJAVU_PORT", "7878"))  # reuse a running `dejavu serve` (same model, same settings)
TEST = re.compile(r"(^|/)(tests?|__tests__|e2e)/|\.test\.|\.spec\.|_test\.py")
NULL = "0" * 40

_model = None


def embed(texts, prefix=""):
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/embed", json.dumps({"texts": texts, "prefix": prefix}).encode(),
                                     {"Content-Type": "application/json"})
        return np.array(json.load(urllib.request.urlopen(req, timeout=300)), np.float32)
    except OSError:
        return embed_here(texts, prefix)


def embed_here(texts, prefix=""):
    global _model
    if _model is None:
        import torch
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL, device="mps" if torch.backends.mps.is_available() else "cpu",
                                     config_kwargs={"vision_config": None, "audio_config": None},
                                     model_kwargs={"torch_dtype": torch.float32})
        _model.max_seq_length = 1024
    e = _model.encode([prefix + t for t in texts], normalize_embeddings=True, batch_size=16,
                      show_progress_bar=len(texts) > 200)[:, :DIM]
    return (e / np.linalg.norm(e, axis=1, keepdims=True)).astype(np.float32)


def git(repo, *args, **kw):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, check=True, **kw).stdout


def supported(path):
    ext = os.path.splitext(path)[1]
    return ext in LANGS and not path.endswith((".d.ts", ".min.js")) and not TEST.search(path) and not excluded(path) \
        and not any(p in ("node_modules", "vendor") or p.startswith("dist") for p in path.split("/"))


def blob_history(repo):
    """{(path, blob): {"born": commit, "died": commit}} for every version of every supported file on any branch."""
    seen, commit = {}, None
    out = git(repo, "log", "--all", "--raw", "--no-renames", "--no-abbrev", "--format=%x00%H %at %s").decode(errors="replace")
    for line in out.splitlines():
        if line.startswith("\0"):
            sha, at, msg = (line[1:].split(" ", 2) + [""])[:3]
            commit = {"sha": sha, "time": int(at), "msg": msg}
        elif line.startswith(":"):
            meta, path = line.split("\t", 1)
            old, new = meta.split()[2:4]
            if not supported(path):
                continue
            if new != NULL:  # this commit gave birth to blob `new`; keep the earliest birth
                v = seen.setdefault((path, new), {})
                if "born" not in v or commit["time"] < v["born"]["time"]:
                    v["born"] = commit
            if old != NULL:  # and ended blob `old`; keep the latest end
                v = seen.setdefault((path, old), {})
                if "died" not in v or commit["time"] > v["died"]["time"]:
                    v["died"] = commit
    return seen


def read_blobs(repo, shas):
    """Blob contents in one `git cat-file --batch` stream."""
    raw = git(repo, "cat-file", "--batch", input="".join(s + "\n" for s in shas).encode())
    blobs, i = {}, 0
    for sha in shas:
        nl = raw.index(b"\n", i)
        size = int(raw[i:nl].split()[2])
        blobs[sha] = raw[nl + 1:nl + 1 + size]
        i = nl + 2 + size
    return blobs


def ghosts(repo):
    """Functions that once lived in the repo and are gone from HEAD, at their last living version."""
    history = blob_history(repo)
    living = {}  # path -> names at HEAD, and every function hash at HEAD
    alive_hashes = set()
    for path in git(repo, "ls-tree", "-r", "--name-only", "HEAD").decode().splitlines():
        if supported(path):
            fns = list(functions_in(git(repo, "show", f"HEAD:{path}"), LANGS[os.path.splitext(path)[1]]))
            living[path] = {f["name"] for f in fns}
            alive_hashes |= {f["hash"] for f in fns}
    alive_names = {(os.path.basename(p), n) for p, names in living.items() for n in names}

    blobs = read_blobs(repo, sorted({b for _, b in history}))
    last, born = {}, {}  # (path, name) -> latest version, earliest birth of any version
    for (path, blob), when in history.items():
        if "born" not in when:  # born on a branch `--all` never reached
            continue
        try:
            fns = functions_in(blobs[blob], LANGS[os.path.splitext(path)[1]])
            for f in fns:
                key = (path, f["name"])
                if key not in born or when["born"]["time"] < born[key]["time"]:
                    born[key] = when["born"]
                end = when.get("died", {"time": float("inf")})["time"]
                if key not in last or end > last[key]["_end"]:
                    last[key] = {**f, "file": path, "born": when["born"], "died": when.get("died"), "_end": end}
        except Exception as e:  # one unparsable version shouldn't stop the séance
            print("skip", path, blob[:8], e, file=sys.stderr)

    out = []
    for (path, name), f in last.items():
        # Changed, moved or still alive on some branch tip: not a ghost.
        if name in living.get(path, ()) or (os.path.basename(path), name) in alive_names \
                or f["hash"] in alive_hashes or f["died"] is None:
            continue
        f.pop("_end")
        f["born"] = born[(path, name)]
        out.append(f)
    return out


def index(repos):
    os.makedirs(HOME, exist_ok=True)
    meta = []
    for repo in repos:
        repo = os.path.abspath(os.path.expanduser(repo))
        t = time.time()
        try:
            found = ghosts(repo)
        except subprocess.CalledProcessError as e:  # not a git repo, or no commits yet
            print(f"{os.path.basename(repo)}: skipped ({e.stderr.decode().strip()[:80]})")
            continue
        for f in found:
            f["repo"] = repo
        print(f"{os.path.basename(repo)}: {len(found)} ghosts ({time.time() - t:.0f} s)")
        meta += found
    # identical bodies embed once
    texts = sorted({f"title: {m['file']} | text: {m['code']}" for m in meta})
    print(f"embedding {len(texts)} unique ghosts…")
    vecs = embed_here(texts) if texts else np.zeros((0, DIM), np.float32)
    row = {t: i for i, t in enumerate(texts)}
    doc = np.stack([vecs[row[f"title: {m['file']} | text: {m['code']}"]] for m in meta]) if meta else vecs
    with open(f"{HOME}/ghosts.jsonl", "w") as fh:
        fh.writelines(json.dumps(m) + "\n" for m in meta)
    np.save(f"{HOME}/ghosts.npy", doc)
    print(f"{len(meta)} ghosts -> {HOME}")


def load():
    if not os.path.exists(f"{HOME}/ghosts.jsonl"):
        sys.exit("no séance yet: run `seance index <repo> ...` first")
    return [json.loads(l) for l in open(f"{HOME}/ghosts.jsonl")], np.load(f"{HOME}/ghosts.npy")


def day(c):
    return time.strftime("%Y-%m-%d", time.localtime(c["time"]))


def summon(query, k=5):
    meta, doc = load()
    scores = doc @ embed([query], QUERY_PREFIX)[0]
    shown = set()
    for i in np.argsort(-scores):
        m = meta[i]
        if m["hash"] in shown:
            continue
        shown.add(m["hash"])
        print(f"{i:>5}  {scores[i]:.2f}  {m['name']:<28} {os.path.basename(m['repo'])}/{m['file']}")
        print(f"{'':>13}born {day(m['born'])}, died {day(m['died'])} in {m['died']['sha'][:8]} \"{m['died']['msg'][:60]}\"")
        if len(shown) == k:
            break


def raise_(i, to=None):
    m = load()[0][i]
    print(f"// {m['name']} from {m['file']}, last seen in {m['died']['sha'][:8]}^ "
          f"(git -C {m['repo']} show {m['died']['sha'][:8]}^:{m['file']})", file=sys.stderr)
    if to:
        with open(to, "x") as fh:  # never overwrite
            fh.write(m["code"] + "\n")
        print(f"raised into {to}", file=sys.stderr)
    else:
        print(m["code"])


def main():
    p = argparse.ArgumentParser(prog="seance", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("index", help="find every deleted function in these repos (read-only)").add_argument("repos", nargs="+")
    s = sub.add_parser("summon", help="describe a deleted function")
    s.add_argument("query")
    s.add_argument("-k", type=int, default=5)
    r = sub.add_parser("raise", help="print a summoned function's code")
    r.add_argument("id", type=int)
    r.add_argument("--to", help="write it to this new file instead")
    a = p.parse_args()
    if a.cmd == "index":
        index(a.repos)
    elif a.cmd == "summon":
        summon(a.query, a.k)
    else:
        raise_(a.id, a.to)


if __name__ == "__main__":
    main()
