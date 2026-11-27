"""Checks every .json, .gltf and .glb file in the repo: each parses as JSON (a .glb
by its JSON chunk), and each glTF's buffers and images exist beside it, with buffers
at least as long as it says and no buffer view running past its buffer. A .glb's
first buffer is the file's BIN chunk. Exits 1 with a list of problems."""
import json
import os
import struct
import subprocess
import sys
import urllib.parse


def read_glb(path):
    """Return (json_document, bin_chunk_length or None) for a binary glTF."""
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < 12 or data[:4] != b"glTF":
        raise ValueError("not a glb (missing glTF magic)")
    version, length = struct.unpack_from("<II", data, 4)
    if version != 2:
        raise ValueError(f"glb version {version} is not 2")
    if length != len(data):
        raise ValueError(f"header length {length} does not match the file ({len(data)} bytes)")
    offset = 12
    doc = None
    bin_length = None
    while offset < length:
        if offset + 8 > length:
            raise ValueError("chunk header runs past the end of the file")
        chunk_length, chunk_type = struct.unpack_from("<I4s", data, offset)
        offset += 8
        if offset + chunk_length > length:
            raise ValueError("chunk runs past the end of the file")
        chunk = data[offset:offset + chunk_length]
        offset += chunk_length
        if chunk_type == b"JSON":
            doc = json.loads(chunk.decode("utf-8"))
        elif chunk_type == b"BIN\x00":
            bin_length = chunk_length
    if not isinstance(doc, dict):
        raise ValueError("no JSON chunk")
    return doc, bin_length


def check_gltf(path, doc, embedded_bin):
    """Same buffer and image checks for a text .gltf and for a .glb's JSON chunk.

    embedded_bin is the BIN chunk's length when path is a .glb, else None. The first
    buffer with no uri is that chunk; its views may not run past those bytes.
    """
    problems = []
    folder = os.path.dirname(path)
    if doc.get("asset", {}).get("version") != "2.0":
        problems.append(f"{path}: asset.version is not 2.0")
    sizes = []
    took_bin = False
    for kind in ("buffers", "images"):
        for i, entry in enumerate(doc.get(kind, [])):
            uri = entry.get("uri")
            if uri is None or uri.startswith("data:"):
                size = entry.get("byteLength", 0)
                if kind == "buffers" and uri is None and embedded_bin is not None and not took_bin:
                    took_bin = True
                    size = embedded_bin
                    if embedded_bin < entry.get("byteLength", 0):
                        problems.append(f"{path}: BIN chunk is shorter than buffers[{i}] byteLength")
                sizes.append(size)
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
    if embedded_bin not in (None, 0) and not took_bin:
        problems.append(f"{path}: BIN chunk is not the first buffer")
    return problems


def main():
    files = subprocess.run(["git", "ls-files", "*.json", "*.gltf", "*.glb"], capture_output=True,
                           text=True, check=True).stdout.split("\n")
    problems = []
    checked = [f for f in files if f]
    for path in checked:
        if path.endswith(".glb"):
            try:
                doc, embedded_bin = read_glb(path)
            except (OSError, ValueError, struct.error, UnicodeError) as err:
                problems.append(f"{path}: {err}")
                continue
            problems.extend(check_gltf(path, doc, embedded_bin))
            continue
        try:
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, ValueError) as err:
            problems.append(f"{path}: {err}")
            continue
        if path.endswith(".gltf"):
            problems.extend(check_gltf(path, doc, None))
    for p in problems:
        print(p)
    print(f"checked {len(checked)} files, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
