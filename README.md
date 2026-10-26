# Git Séance

**Every function you ever deleted is still in your git history. Git Séance lets you call it back by describing it.**

You remember *that you wrote it*: "the thing that pulled pasted images out of the clipboard", deleted sometime in July.
You don't remember its name, so `git log -S` can't help you. Git Séance walks every version of every file on every
branch, finds the functions that no longer exist at HEAD, and lets you search them by meaning with
[EmbeddingGemma 2](https://huggingface.co/google/embeddinggemma-2), an open-weight model running on your laptop.

```
$ seance summon "paste images from the clipboard" -k 2
   17  0.82  imageFilesFromClipboard      arivu-agent/desktop/renderer/src/App.tsx
             born 2026-06-21, died 2026-07-03 in f2e18500 "Add drag-and-drop image attachments"
   15  0.69  pullRequestCheckLogCommand   arivu-agent/src/agent/taskWorktree.ts
             born 2026-07-04, died 2026-07-05 in 39d376bc "Broaden PR check evidence capture"

$ seance raise 17
// imageFilesFromClipboard from desktop/renderer/src/App.tsx, last seen in f2e18500^ (git -C ~/Documents/arivu-agent show f2e18500^:desktop/renderer/src/App.tsx)
function imageFilesFromClipboard(clipboard: DataTransfer) {
  const files = Array.from(clipboard.files).filter((file) => SUPPORTED_IMAGE_TYPES.has(file.type));
  ...
```

## Install

Python 3.10+. Tested on macOS with an Apple GPU; elsewhere it runs on the CPU, slower. The first run downloads
EmbeddingGemma 2 (about 1.5 GB).

```bash
git clone https://github.com/shashankbudem/git-seance && cd git-seance
pip install -e .
```

## Use

```bash
seance index ~/code/app ~/code/lib            # find every deleted function (read-only; stored in ~/.seance)
seance summon "retry with exponential backoff"
seance raise 42                               # print its last living version
seance raise 42 --to retry.ts                 # or write it to a new file (never overwrites)
```

Git Séance never touches your repos: it only reads `git log` and blobs. Searches reuse a running
[`dejavu serve`](https://github.com/shashankbudem/code-dejavu) if there is one (same model, same settings), so a
summon takes about 0.1 to 0.3 s instead of the ~13 s it takes to load the model.

Each `seance index` replaces the previous index, so list every repo you want searched.

## Who counts as a ghost

The hard part isn't finding old code, it's *not* drowning in it: every edit leaves an old version of a still-living
function behind. So a function is a ghost only if:

- nothing with its name still lives in that file (or a file with the same name) at HEAD, so it wasn't just edited or its file moved,
- its exact body (comments and whitespace ignored) isn't anywhere at HEAD, so it wasn't moved to another file,
- and it isn't still alive at the tip of some other branch.

Each ghost is shown at its **last living version**, with the commit that created that version and the commit that
removed it. Test files are skipped.

1. `git log --all --raw` lists every version (blob) of every TypeScript, JavaScript, Python and Rust file, with the
   commit that created it and the commit that replaced it.
2. One `git cat-file --batch` stream reads them all; tree-sitter pulls out every function of 5+ lines.
3. Ghosts are embedded with EmbeddingGemma 2 (`title: {path} | text: {code}`, first 256 Matryoshka dimensions); your
   description is embedded with the `task: code retrieval` prompt.

The function extractor and model settings come from my earlier project,
[Code Déjà Vu](https://github.com/shashankbudem/code-dejavu), where they were tuned.

## How well does it work?

My coding agent described 18 real deleted functions from four repos (three of mine, one open-source project), reading
each one before describing it. They came from a random sample, with trivial ones dropped and a few more picked by name. I checked where the right one ranked among 229 unique ghosts ([`eval/summon_eval.py`](eval/summon_eval.py),
[`eval/summon_report.txt`](eval/summon_report.txt)):

| | right function first | in the top 5 |
|---|---|---|
| Git Séance | **17/18** | **18/18** |
| Keyword matching (rank by query words found in the code) | 5/18 | 14/18 |

**Caveats:** 18 queries, 229 candidates, descriptions written by someone who had just read the code. A bigger history
makes it harder. Treat it as a first measurement, not a benchmark.

## A word of warning

Deleted code is where old API keys go to die. Anything `seance raise` prints came out of your history, so check it
before you paste it anywhere public.

## Built for

The [DEV Hacktoberfest 2026 Open-Source AI Challenge](https://dev.to/challenges/hacktoberfest-week4-2026-10-26), Week 4, "Ghost in the Machine",
October 26 to November 1, 2026. Any commits after the deadline will be listed here.

## License

Apache 2.0
