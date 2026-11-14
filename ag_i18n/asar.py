# coding: utf-8
"""Zero-dependency Electron ASAR archive reader, extractor, and integrity-preserving packer."""

import hashlib
import json
import os
import struct
from pathlib import Path
from typing import Dict, Tuple


BLOCK_SIZE = 4 * 1024 * 1024


def compute_integrity(data: bytes) -> dict:
    """Compute Electron ASAR SHA-256 block integrity metadata matching @electron/asar."""
    digest = hashlib.sha256(data).hexdigest()
    if not data:
        blocks = [hashlib.sha256(b"").hexdigest()]
    else:
        blocks = [
            hashlib.sha256(data[i:i + BLOCK_SIZE]).hexdigest()
            for i in range(0, len(data), BLOCK_SIZE)
        ]
    return {
        "algorithm": "SHA256",
        "hash": digest,
        "blockSize": BLOCK_SIZE,
        "blocks": blocks,
    }


def read_asar_header(asar_path: Path) -> Tuple[dict, int]:
    """Parse the ASAR pickle header and return (header_dict, payload_base_offset)."""
    with open(asar_path, "rb") as f:
        pre = f.read(16)
        if len(pre) < 16:
            raise ValueError(f"Invalid ASAR archive (header too short): {asar_path}")
        _magic, size, _u1, header_size = struct.unpack("<4I", pre)
        header_json = f.read(header_size).decode("utf-8")
        return json.loads(header_json), 8 + size


def extract_asar(asar_path: Path, dest_dir: Path) -> Dict[str, dict]:
    """Extract an ASAR archive into dest_dir and return metadata for unpacked entries."""
    unpacked_info: Dict[str, dict] = {}
    with open(asar_path, "rb") as f:
        pre = f.read(16)
        _magic, size, _u1, header_size = struct.unpack("<4I", pre)
        header = json.loads(f.read(header_size).decode("utf-8"))
        base_offset = 8 + size

        def walk(node: dict, current_dir: Path, rel_posix: str) -> None:
            current_dir.mkdir(parents=True, exist_ok=True)
            for name, info in node.items():
                target = current_dir / name
                child_posix = f"{rel_posix}/{name}" if rel_posix else name
                if "files" in info:
                    walk(info["files"], target, child_posix)
                elif info.get("unpacked"):
                    unpacked_info[child_posix] = info
                elif "offset" in info:
                    f.seek(base_offset + int(info["offset"]))
                    payload = f.read(int(info["size"]))
                    target.write_bytes(payload)

        walk(header.get("files", {}), dest_dir, "")
    return unpacked_info


def pack_asar(
    src_dir: Path,
    dest_asar: Path,
    unpacked_info: Dict[str, dict] | None = None,
) -> None:
    """Pack src_dir into dest_asar while preserving unpacked entries and SHA-256 hashes."""
    unpacked_info = unpacked_info or {}
    unpacked_root = Path(f"{dest_asar}.unpacked")
    offset = 0
    chunks = []

    def build_tree(current_dir: Path, rel_posix: str) -> dict:
        nonlocal offset
        files = {}
        for entry in sorted(current_dir.iterdir(), key=lambda p: p.name):
            child_posix = f"{rel_posix}/{entry.name}" if rel_posix else entry.name
            if entry.is_dir():
                files[entry.name] = {"files": build_tree(entry, child_posix)}
            elif entry.is_file():
                buf = entry.read_bytes()
                files[entry.name] = {
                    "size": len(buf),
                    "offset": str(offset),
                    "integrity": compute_integrity(buf),
                }
                offset += len(buf)
                chunks.append(buf)
        return files

    header_files = build_tree(src_dir, "")

    for rel_posix, orig_info in unpacked_info.items():
        parts = [p for p in rel_posix.split("/") if p]
        if not parts:
            continue
        cur = header_files
        for part in parts[:-1]:
            if part not in cur or "files" not in cur[part]:
                cur[part] = {"files": {}}
            cur = cur[part]["files"]
        leaf = parts[-1]
        disk_unpacked = unpacked_root.joinpath(*parts)
        if disk_unpacked.is_file():
            ubuf = disk_unpacked.read_bytes()
            cur[leaf] = {
                "size": len(ubuf),
                "unpacked": True,
                "integrity": compute_integrity(ubuf),
            }
        else:
            cur[leaf] = orig_info

    header_bytes = json.dumps(
        {"files": header_files},
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    json_size = len(header_bytes)
    padding = (4 - (json_size % 4)) % 4
    aligned_size = json_size + padding
    header_buf = (
        struct.pack("<4I", 4, 8 + aligned_size, 4 + aligned_size, json_size)
        + header_bytes
        + (b"\x00" * padding)
    )

    tmp_asar = dest_asar.with_name(dest_asar.name + ".tmp")
    with open(tmp_asar, "wb") as out_f:
        out_f.write(header_buf)
        for chunk in chunks:
            out_f.write(chunk)
    os.replace(tmp_asar, dest_asar)
