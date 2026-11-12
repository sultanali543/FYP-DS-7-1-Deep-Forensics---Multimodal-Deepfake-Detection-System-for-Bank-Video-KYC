import io
import re
import zipfile

import httpx
import pytest

from audio.official_eval import RangeArchive


def test_range_zip_reads_only_requested_bytes_and_checks_member_crc():
    buffer = io.BytesIO()
    payload = b"official audio fixture" * 500
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("folder/utterance.flac", payload)
    content = buffer.getvalue()

    def serve(request):
        match = re.fullmatch(r"bytes=(\d+)-(\d+)", request.headers["Range"])
        start, end = int(match[1]), int(match[2])
        return httpx.Response(206, content=content[start:end + 1],
                              headers={"Content-Range": f"bytes {start}-{end}/{len(content)}", "ETag": '"fixture"'})

    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        remote = RangeArchive(client, "https://example.test/archive.zip")
        with zipfile.ZipFile(remote) as archive:
            info = archive.infolist()[0]
        assert remote.member(info) == payload
        info.CRC ^= 1
        with pytest.raises(ValueError, match="CRC"):
            remote.member(info)


@pytest.mark.parametrize("status,headers", [(200, {}), (206, {"Content-Range": "bytes 1-1/20"})])
def test_range_download_rejects_full_file_and_wrong_range(status, headers):
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status, content=b"x", headers=headers))) as client:
        with pytest.raises(ValueError):
            RangeArchive(client, "https://example.test/archive.zip")


def test_range_download_rejects_oversized_response():
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(206, content=b"extra", headers={"Content-Range": "bytes 0-0/20"}))) as client:
        with pytest.raises(ValueError, match="exceeded"):
            RangeArchive(client, "https://example.test/archive.zip")
