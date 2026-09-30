"""Document classification, versioning and completeness rules (BRD §33–§36, §40). Pure functions."""
import re
from dataclasses import dataclass

MODEL_ID_RE = re.compile(r"(?<![A-Za-z0-9])M-?(\d{4,})(?![0-9])", re.IGNORECASE)
VERSION_RE = re.compile(r"(?:^|[\s_\-.(])v(?:ersion)?[\s_\-.]?(\d+(?:[._]\d+)?)(?=$|[\s_\-.)])", re.IGNORECASE)

# Confidence by evidence (BRD §34: folder name, file name, manifest, content, AI).
CONFIDENCE = {"manifest": 1.0, "user": 1.0, "filename": 0.85, "folder": 0.7, "none": 0.2}


@dataclass(frozen=True)
class TypeGuess:
    document_type: str
    confidence: float
    source: str  # manifest | filename | folder | none | user
    reason: str


def parse_keywords(items: list[str]) -> list[tuple[str, list[str]]]:
    """'Type=kw1|kw2' policy items, in priority order."""
    out = []
    for item in items:
        name, _, kws = item.partition("=")
        out.append((name.strip(), [k.strip().lower() for k in kws.split("|") if k.strip()]))
    return out


def _words(text: str) -> str:
    """Lower-case, separators to spaces, CamelCase split: 'Validation_Report-2026' → 'validation report 2026'."""
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return " " + re.sub(r"[^a-z0-9]+", " ", text.lower()).strip() + " "


def _match(text: str, keywords: list[tuple[str, list[str]]]) -> tuple[str, str] | None:
    words = _words(text)
    for doc_type, kws in keywords:
        for kw in kws:
            if f" {kw} " in words:
                return doc_type, kw
    return None


def classify_type(file_name: str, folders: list[str], keywords: list[tuple[str, list[str]]],
                  fallback: str = "Other") -> TypeGuess:
    """File name first (most specific), then the nearest folder upwards."""
    stem = file_name.rsplit(".", 1)[0]
    hit = _match(stem, keywords)
    if hit:
        return TypeGuess(hit[0], CONFIDENCE["filename"], "filename", f"File name contains '{hit[1]}'.")
    for folder in reversed(folders):
        hit = _match(folder, keywords)
        if hit:
            return TypeGuess(hit[0], CONFIDENCE["folder"], "folder", f"Folder '{folder}' contains '{hit[1]}'.")
    return TypeGuess(fallback, CONFIDENCE["none"], "none", "No keyword matched; please choose the document type.")


def detect_model_id(folders: list[str], file_name: str) -> tuple[str | None, str | None]:
    """Method A (BRD §33): a model ID in the nearest folder name, else in the file name."""
    for folder in reversed(folders):
        m = MODEL_ID_RE.search(folder)
        if m:
            return f"M-{m.group(1)}", "folder"
    m = MODEL_ID_RE.search(file_name)
    if m:
        return f"M-{m.group(1)}", "filename"
    return None, None


def parse_version(file_name: str) -> str | None:
    m = VERSION_RE.search(file_name.rsplit(".", 1)[0])
    if not m:
        return None
    v = m.group(1).replace("_", ".")
    return v if "." in v else f"{v}.0"


def title_from_file(file_name: str) -> str:
    """Human title without extension and version tokens: 'Validation_Report_v1.2.pdf' → 'Validation Report'."""
    stem = file_name.rsplit(".", 1)[0]
    stem = VERSION_RE.sub(" ", stem)
    return re.sub(r"[_\-]+", " ", stem).strip() or file_name


def normalised_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def _version_key(v: str) -> tuple:
    return tuple(int(p) if p.isdigit() else 0 for p in re.split(r"[.]", v))


def next_version(existing: list[str]) -> str:
    """1.0 → 1.1 → 1.2 … (a user or manifest may give 2.0 explicitly)."""
    if not existing:
        return "1.0"
    latest = max(existing, key=_version_key)
    parts = [int(p) if p.isdigit() else 0 for p in latest.split(".")]
    major, minor = (parts + [0])[:2]
    return f"{major}.{minor + 1}"


def is_newer(candidate: str, existing: list[str]) -> bool:
    return not existing or _version_key(candidate) > max(_version_key(v) for v in existing)


def required_types(phase: str, phases: list[str], development: list[str], validation: list[str],
                   production: list[str]) -> list[str]:
    """Required document policy by lifecycle phase (BRD §40): Development, Validation, then the
    production set from Implementation onwards. Earlier phases (Initiation) require nothing."""
    if phase not in phases:
        return []
    if "Implementation" in phases and phases.index(phase) >= phases.index("Implementation"):
        return production
    return {"Validation": validation, "Development": development}.get(phase, [])


@dataclass(frozen=True)
class Completeness:
    required: list[str]
    present: list[str]
    missing: list[str]
    score: float | None  # None when nothing is required


def completeness(required: list[str], present_types: set[str]) -> Completeness:
    present = [t for t in required if t in present_types]
    missing = [t for t in required if t not in present_types]
    score = None if not required else round(100 * len(present) / len(required), 1)
    return Completeness(required, present, missing, score)
