"""Fetch a fixed, small official ASVspoof 2019 LA evaluation subset via HTTP ranges.

Only declared protocol IDs are downloaded. No test scores influence sampling.
Contains information from ASVspoof 2019, University of Edinburgh/CSTR,
https://doi.org/10.7488/ds/2555, available under ODC Attribution License.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import threading
import zipfile
import zlib

import httpx

from .evaluate import FIELDS
from .robustness import balanced_ids, write_json

ARCHIVE = "https://datashare.ed.ac.uk/server/api/core/bitstreams/a9f87c35-f055-4015-80e2-2fdff0d46269/content"
LICENSE = "https://datashare.ed.ac.uk/server/api/core/bitstreams/60c7de6d-37d3-45c1-b52e-9f18b0338e47/content"
SOURCE = "https://doi.org/10.7488/ds/2555"
SEED = 20261112


class RangeArchive(io.RawIOBase):
    def __init__(self, client, url=ARCHIVE, budget=700 * 1024 * 1024):
        self.client, self.url, self.budget = client, url, budget
        self.position, self.downloaded = 0, 0
        self.lock = threading.Lock()
        self.cache, self.cache_start = b"", 0
        self.length, self.etag = None, None
        self.fetch(0, 0)

    def fetch(self, start, end):
        if start < 0 or end < start or end - start + 1 > 40 * 1024 * 1024:
            raise ValueError("Invalid or oversized range request.")
        with self.lock:
            if self.downloaded + end - start + 1 > self.budget:
                raise ValueError("Selective download byte budget exceeded.")
            self.downloaded += end - start + 1
        headers = {"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"}
        if self.etag:
            headers["If-Range"] = self.etag
        with self.client.stream("GET", self.url, headers=headers) as response:
            if response.status_code != 206:
                raise ValueError("Server did not honor the range request; refusing a full archive download.")
            match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", ""))
            if not match or (int(match[1]), int(match[2])) != (start, end):
                raise ValueError("Unexpected Content-Range.")
            length = int(match[3])
            if self.length is not None and length != self.length:
                raise ValueError("Archive size changed during download.")
            etag = response.headers.get("ETag")
            if self.etag and etag != self.etag:
                raise ValueError("Archive ETag changed during download.")
            self.length, self.etag = length, etag
            chunks, received = [], 0
            for chunk in response.iter_bytes():
                received += len(chunk)
                if received > end - start + 1:
                    raise ValueError("Range response exceeded its declared size.")
                chunks.append(chunk)
            if received != end - start + 1:
                raise ValueError("Truncated range response.")
            return b"".join(chunks)

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        position = offset if whence == 0 else self.position + offset if whence == 1 else self.length + offset if whence == 2 else -1
        if not 0 <= position <= self.length:
            raise ValueError("Seek outside remote archive.")
        self.position = position
        return position

    def read(self, size=-1):
        if size < 0:
            size = self.length - self.position
        size = min(size, self.length - self.position)
        if size == 0:
            return b""
        if not (self.cache_start <= self.position and self.position + size <= self.cache_start + len(self.cache)):
            self.cache_start = self.position
            end = min(self.length - 1, self.position + max(size, 65536) - 1)
            self.cache = self.fetch(self.position, end)
        start = self.position - self.cache_start
        self.position += size
        return self.cache[start:start + size]

    def member(self, info):
        if not 0 < info.file_size <= 20 * 1024 * 1024 or info.compress_size > 20 * 1024 * 1024:
            raise ValueError("Unexpected member size.")
        end = min(self.length - 1, info.header_offset + 512 + info.compress_size - 1)
        data = self.fetch(info.header_offset, end)
        fields = struct.unpack("<4sHHHHHIIIHH", data[:30])
        if fields[0] != b"PK\x03\x04" or fields[2] & 1:
            raise ValueError("Invalid or encrypted ZIP member.")
        name_length, extra_length = fields[-2:]
        offset = 30 + name_length + extra_length
        if offset + info.compress_size > len(data):
            data = self.fetch(info.header_offset, info.header_offset + offset + info.compress_size - 1)
        name = data[30:30 + name_length].decode("utf-8" if fields[2] & 0x800 else "cp437")
        if name != info.filename or fields[3] != info.compress_type:
            raise ValueError("ZIP header differs from central directory.")
        payload = data[offset:offset + info.compress_size]
        if info.compress_type == zipfile.ZIP_STORED:
            content = payload
        elif info.compress_type == zipfile.ZIP_DEFLATED:
            decoder = zlib.decompressobj(-15)
            content = decoder.decompress(payload, info.file_size + 1)
            if not decoder.eof:
                raise ValueError("Truncated or oversized compressed member.")
        else:
            raise ValueError("Unsupported ZIP compression.")
        if len(content) != info.file_size or zlib.crc32(content) != info.CRC:
            raise ValueError("ZIP member failed length/CRC verification.")
        return content


def download_subset(output, per_class=500, workers=3):
    if not 1 <= per_class <= 2000 or not 1 <= workers <= 4:
        raise ValueError("Use 1–2000 clips per class and 1–4 workers.")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    audio_dir = output / "flac"
    audio_dir.mkdir(exist_ok=True)
    with httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": "DeepForensics-academic-evaluation/1.0"},
                      transport=httpx.HTTPTransport(retries=2)) as client:
        remote = RangeArchive(client)
        with zipfile.ZipFile(remote) as archive:
            infos = archive.infolist()
            protocols = [info for info in infos if info.filename.endswith("ASVspoof2019.LA.cm.eval.trl.txt")]
            if len(protocols) != 1:
                raise ValueError("Official evaluation protocol was not found uniquely.")
            protocol = remote.member(protocols[0])
        rows = []
        for line in protocol.decode().splitlines():
            speaker, name, _, system, label = line.split()
            if not re.fullmatch(r"LA_E_\d+", name) or label not in {"bonafide", "spoof"}:
                raise ValueError("Invalid evaluation protocol.")
            rows.append({"speaker_id": speaker, "audio_file_name": name, "system_id": system, "key": int(label == "spoof")})
        if sum(row["key"] == 0 for row in rows) != 7355 or sum(row["key"] == 1 for row in rows) != 63882:
            raise ValueError("Official evaluation counts differ from the expected protocol.")
        selected_ids = balanced_ids(rows, per_class, SEED)
        selected = [row for row in rows if row["audio_file_name"] in set(selected_ids)]
        members = {Path(info.filename).stem: info for info in infos
                   if "/ASVspoof2019_LA_eval/flac/" in "/" + info.filename and info.filename.endswith(".flac")}
        if not set(selected_ids).issubset(members):
            raise ValueError("Some selected evaluation utterances are absent from the archive.")
        plan = {"source": SOURCE, "archive_url": ARCHIVE, "archive_bytes": remote.length, "archive_etag": remote.etag,
                "license_url": LICENSE, "protocol_sha256": hashlib.sha256(protocol).hexdigest(),
                "seed": SEED, "per_class": per_class, "selection": "round-robin speaker/attack strata; fixed before any model scoring",
                "selected_ids": selected_ids, "expected_audio_bytes": sum(members[name].file_size for name in selected_ids)}
        plan_path = output / "download_plan.json"
        if plan_path.exists() and json.loads(plan_path.read_text()) != plan:
            raise ValueError("Download selection or source changed; choose another output directory.")
        write_json(plan_path, plan)
        (output / "official_eval_protocol.txt").write_bytes(protocol)
        print(f"Fixed selection: {len(selected_ids)} clips, {plan['expected_audio_bytes'] / 1e6:.1f} MB of FLAC", flush=True)

        def download(row):
            name = row["audio_file_name"]
            info, destination = members[name], audio_dir / f"{name}.flac"
            if destination.exists():
                content = destination.read_bytes()
                if len(content) != info.file_size or zlib.crc32(content) != info.CRC:
                    raise ValueError(f"Existing audio failed CRC: {name}")
            else:
                content = remote.member(info)
                temporary = destination.with_suffix(".download")
                temporary.write_bytes(content)
                temporary.replace(destination)
            return {"audio_id": name, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content), "zip_crc32": info.CRC}

        checksums = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for index, record in enumerate(executor.map(download, selected), 1):
                checksums.append(record)
                if index % 50 == 0 or index == len(selected):
                    print(f"Official evaluation download: {index}/{len(selected)}", flush=True)
        license_response = client.get(LICENSE)
        license_response.raise_for_status()
        (output / "LICENSE_text.txt").write_text(license_response.text, encoding="utf-8")
        manifest = output / "manifest.csv"
        with manifest.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=FIELDS)
            writer.writeheader()
            for row in selected:
                writer.writerow(dict(zip(FIELDS, (row["audio_file_name"], f"flac/{row['audio_file_name']}.flac",
                                "FAKE" if row["key"] else "REAL", row["speaker_id"], row["system_id"], "test", SOURCE), strict=True)))
        write_json(output / "download_summary.json", {"clips": len(selected), "network_bytes_this_run": remote.downloaded,
                   "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(), "files": checksums,
                   "integrity": "HTTPS official source, central-directory CRC per member, local SHA256; full archive checksum not computed"})
        return {"manifest": str(manifest.resolve()), "clips": len(selected), "network_bytes_this_run": remote.downloaded}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-class", type=int, default=500)
    parser.add_argument("--workers", type=int, default=3)
    arguments = parser.parse_args()
    print(json.dumps(download_subset(arguments.output, arguments.per_class, arguments.workers), indent=2))
