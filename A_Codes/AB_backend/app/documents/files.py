"""File validation for uploaded documents (BRD §65): extension, signature, MIME, size — and safe ZIP expansion."""
import io
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath

MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "csv": "text/csv",
}
OOXML_PART = {"docx": "word/", "xlsx": "xl/", "pptx": "ppt/"}
SKIP_NAMES = ("__MACOSX/", ".DS_Store", "Thumbs.db", "desktop.ini")


class FileRejected(ValueError):
    pass


def extension(name: str) -> str:
    return PurePosixPath(name).suffix.lstrip(".").lower()


def validate_document(name: str, data: bytes, allowed_ext: list[str], max_bytes: int) -> str:
    """Return the MIME type, or raise FileRejected with a human-readable reason."""
    ext = extension(name)
    if ext not in allowed_ext:
        raise FileRejected(f"'.{ext or '?'}' files are not accepted. Allowed: {', '.join('.' + e for e in allowed_ext)}.")
    if not data:
        raise FileRejected("The file is empty.")
    if len(data) > max_bytes:
        raise FileRejected(f"The file is {len(data) / 1048576:.1f} MB; the limit is {max_bytes // 1048576} MB.")
    if ext == "pdf" and not data.startswith(b"%PDF-"):
        raise FileRejected("The file is named .pdf but is not a PDF document.")
    if ext in OOXML_PART:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = z.namelist()
        except zipfile.BadZipFile:
            raise FileRejected(f"The file is named .{ext} but is not an Office document.") from None
        if "[Content_Types].xml" not in names or not any(n.startswith(OOXML_PART[ext]) for n in names):
            raise FileRejected(f"The file is named .{ext} but its content does not match.")
    if ext == "csv":
        try:
            data[:65536].decode("utf-8-sig")
        except UnicodeDecodeError:
            raise FileRejected("The CSV file is not UTF-8 text.") from None
    return MIME.get(ext, "application/octet-stream")


@dataclass(frozen=True)
class ZipLimits:
    max_files: int
    max_uncompressed_bytes: int
    max_ratio: int


def safe_member_path(name: str) -> str | None:
    """Normalised relative path, None for entries to skip; raises on traversal (BRD §32, §65)."""
    name = name.replace("\\", "/")
    if name.endswith("/") or any(s in name for s in SKIP_NAMES) or PurePosixPath(name).name.startswith("._"):
        return None
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts or (p.parts and ":" in p.parts[0]):
        raise FileRejected(f"The ZIP contains an unsafe path '{name}'. The package was rejected.")
    return "/".join(x for x in p.parts if x not in ("", "."))


def expand_zip(data: bytes, limits: ZipLimits) -> list[tuple[str, bytes]]:
    """Expand a ZIP package into (relative path, bytes), enforcing file count, size and ratio limits."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise FileRejected("The file is not a valid ZIP package.") from None
    with z:
        members = []
        for info in z.infolist():
            path = safe_member_path(info.filename)
            if path is None:
                continue
            if info.flag_bits & 0x1:
                raise FileRejected(f"'{path}' is encrypted; encrypted packages are not accepted.")
            if info.compress_size and info.file_size / info.compress_size > limits.max_ratio:
                raise FileRejected(f"'{path}' is compressed suspiciously (possible zip bomb). The package was rejected.")
            members.append((path, info))
        if len(members) > limits.max_files:
            raise FileRejected(f"The ZIP contains {len(members)} files; the limit is {limits.max_files}.")
        total = sum(i.file_size for _, i in members)
        if total > limits.max_uncompressed_bytes:
            raise FileRejected(f"The ZIP expands to {total / 1048576:.0f} MB; the limit is "
                               f"{limits.max_uncompressed_bytes // 1048576} MB.")
        out, read = [], 0
        for path, info in members:
            content = z.read(info)
            read += len(content)
            if read > limits.max_uncompressed_bytes:  # declared sizes can lie
                raise FileRejected("The ZIP expands beyond the size limit. The package was rejected.")
            out.append((path, content))
        return out
