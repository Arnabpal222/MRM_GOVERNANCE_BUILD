"""Reading uploaded Excel/CSV files and writing blank or filled templates."""
import csv
import io
from dataclasses import dataclass
from datetime import date, datetime

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from app.ingestion.registry import Template

DATA_SHEET = "data"
INSTRUCTIONS_SHEET = "instructions"
XLSX_MAGIC = b"PK\x03\x04"


class FileFormatError(ValueError):
    pass


@dataclass
class ParsedFile:
    sheet: str | None
    headers: list[str]
    rows: list[dict[str, str]]  # raw text values keyed by header; row numbers are index + 2


def _cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat() if value.time() == datetime.min.time() else value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def parse(file_name: str, data: bytes) -> ParsedFile:
    lower = file_name.lower()
    if lower.endswith(".csv"):
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise FileFormatError("The CSV file is not UTF-8 encoded. Save it as 'CSV UTF-8' and upload again.") from None
        reader = csv.reader(io.StringIO(text))
        table = [row for row in reader]
        sheet = None
    elif lower.endswith(".xlsx"):
        if not data.startswith(XLSX_MAGIC):
            raise FileFormatError("The file has an .xlsx name but is not an Excel workbook.")
        try:
            wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception as exc:  # noqa: BLE001 — any openpyxl failure means an unreadable workbook
            raise FileFormatError(f"The workbook could not be read ({type(exc).__name__}).") from None
        names = [n for n in wb.sheetnames if n.lower() != INSTRUCTIONS_SHEET]
        sheet = DATA_SHEET if DATA_SHEET in wb.sheetnames else (names[0] if names else None)
        if sheet is None:
            raise FileFormatError(f"The workbook has no '{DATA_SHEET}' sheet.")
        table = [[_cell_text(v) for v in row] for row in wb[sheet].iter_rows(values_only=True)]
        wb.close()
    else:
        raise FileFormatError("Only .xlsx and .csv files can be imported.")

    table = [row for row in table if any((c or "").strip() for c in row)] if table else []
    if not table:
        raise FileFormatError("The file is empty: no header row was found.")
    headers = [(h or "").strip() for h in table[0]]
    rows = []
    for raw in table[1:]:
        padded = list(raw) + [""] * (len(headers) - len(raw))
        rows.append({h: (padded[i] or "").strip() for i, h in enumerate(headers) if h})
    return ParsedFile(sheet=sheet, headers=[h for h in headers if h], rows=rows)


def _instructions(ws, template: Template, allowed_values: dict[str, list[str]]) -> None:
    ws.append(["column", "type", "required", "allowed values / rule", "description", "example"])
    for c in template.columns:
        allowed = allowed_values.get(c.name) or []
        rule = "; ".join(filter(None, [", ".join(allowed) if allowed else "", c.condition or "",
                                       f"must exist in {c.fk}" if c.fk else "", f"max {c.max_length} chars" if c.max_length else ""]))
        ws.append([c.name, c.type, "Yes" if c.required else ("Conditional" if c.condition else "No"), rule,
                   c.description, c.example])
    ws.append([])
    ws.append(["Dates as YYYY-MM-DD. Yes/no as Y or N. Lists separated by ';'. Keep the header row as is; "
               "column order does not matter. Re-importing an existing ID updates that record."])
    for cell in ws[1]:
        cell.font = Font(bold=True)


def write_workbook(template: Template, rows: list[dict], allowed_values: dict[str, list[str]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = DATA_SHEET
    headers = [c.name for c in template.columns]
    ws.append(headers)
    fill = PatternFill("solid", fgColor="DDE1EA")
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = fill
    for r in rows:
        ws.append([_cell_text(r.get(h)) if r.get(h) is not None else None for h in headers])
    _instructions(wb.create_sheet(INSTRUCTIONS_SHEET), template, allowed_values)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def write_csv(template: Template, rows: list[dict]) -> bytes:
    buf = io.StringIO()
    headers = [c.name for c in template.columns]
    w = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({h: _cell_text(r.get(h)) for h in headers})
    return buf.getvalue().encode("utf-8")
