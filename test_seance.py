"""Smoke test: a deleted function is summoned; an edited or moved one is not a ghost."""
import os
import subprocess
import tempfile

RETRY = '''def retry_with_backoff(fn, attempts=5):
    delay = 0.5
    for i in range(attempts):
        try:
            return fn()
        except Exception:
            time.sleep(delay)
            delay *= 2
'''
SLUG = '''def slugify(title):
    title = title.lower().strip()
    title = re.sub(r"[^a-z0-9]+", "-", title)
    title = title.strip("-")
    return title
'''
MOVER = '''def parse_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    return r, g, int(hex_color[4:6], 16)
'''


def run(repo, *cmd):
    subprocess.run(cmd, cwd=repo, check=True, capture_output=True)


def commit(repo, files, msg):
    for name, text in files.items():
        if text is None:
            os.remove(os.path.join(repo, name))
        else:
            open(os.path.join(repo, name), "w").write(text)
    run(repo, "git", "add", "-A")
    run(repo, "git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", msg)


with tempfile.TemporaryDirectory() as repo:
    run(repo, "git", "init", "-q")
    commit(repo, {"util.py": RETRY + "\n" + SLUG, "color.py": MOVER}, "add helpers")
    commit(repo, {"util.py": SLUG.replace("strip()", "strip().replace('_', ' ')"), "color.py": None,
                  "paint.py": MOVER}, "drop retry, tweak slugify, move parse_rgb")
    os.environ["SEANCE_HOME"] = os.path.join(repo, ".seance-home")
    import seance
    seance.HOME = os.environ["SEANCE_HOME"]
    found = {g["name"]: g for g in seance.ghosts(repo)}
    assert set(found) == {"retry_with_backoff"}, found.keys()
    assert found["retry_with_backoff"]["died"]["msg"].startswith("drop retry")
    assert found["retry_with_backoff"]["born"]["msg"] == "add helpers"
    seance.index([repo])
    meta, doc = seance.load()
    q = seance.embed_here(["call a function again and again, waiting longer each time"], seance.QUERY_PREFIX)[0]
    assert meta[int((doc @ q).argmax())]["name"] == "retry_with_backoff"
print("ok")
