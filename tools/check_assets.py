"""Checks every .json and .gltf file in the repo: each parses as JSON, and each glTF's
buffers and images exist beside it, with buffers at least as long as it says and no
buffer view running past its buffer. Exits 1 with a list of problems."""
import json
import os
import subprocess
import sys
import urllib.parse


def main():
    files = subprocess.run(["git", "ls-files", "*.json", "*.gltf"], capture_output=True,
                           text=True, check=True).stdout.split("\n")
    problems = []
    for path in filter(None, files):
        try:
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, ValueError) as err:
            problems.append(f"{path}: {err}")
            continue
        if not path.endswith(".gltf"):
            continue
        folder = os.path.dirname(path)
        if doc.get("asset", {}).get("version") != "2.0":
            problems.append(f"{path}: asset.version is not 2.0")
        sizes = []
        for kind in ("buffers", "images"):
            for i, entry in enumerate(doc.get(kind, [])):
                uri = entry.get("uri")
                if uri is None or uri.startswith("data:"):
                    sizes.append(entry.get("byteLength", 0))
                    continue
                target = os.path.join(folder, urllib.parse.unquote(uri))
                if not os.path.isfile(target):
                    problems.append(f"{path}: {kind}[{i}] names {uri}, which is missing")
                    sizes.append(0)
                    continue
                if kind == "buffers":
                    size = os.path.getsize(target)
                    sizes.append(size)
                    if size < entry.get("byteLength", 0):
                        problems.append(f"{path}: {uri} is shorter than its byteLength")
            if kind == "buffers":
                for i, view in enumerate(doc.get("bufferViews", [])):
                    b = view.get("buffer", 0)
                    end = view.get("byteOffset", 0) + view.get("byteLength", 0)
                    if b >= len(sizes) or end > sizes[b]:
                        problems.append(f"{path}: bufferViews[{i}] runs past its buffer")
    for p in problems:
        print(p)
    print(f"checked {len([f for f in files if f])} files, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
