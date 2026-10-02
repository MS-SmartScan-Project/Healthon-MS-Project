"""
تصدير سجل الفحوصات إلى ملف Excel (.xlsx) منسّق وجاهز للطبيب.
يستخدم مكتبات بايثون القياسية فقط (zipfile + XML) — لا حاجة لأي مكتبة إضافية.
"""
import io
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape

FINDING = {"Infected": "Suspected MS/SVD", "Uncertain": "Low confidence", "Healthy": "Clear"}
NEXT_STEP = {
    "Infected": "Differentiate MS vs SVD: lumbar puncture (CSF OCBs, κ-FLC); contrast-enhanced MRI brain & spinal cord; "
                "vascular risk assessment (BP, HbA1c, lipids)",
    "Uncertain": "Radiologist review first; if lesion confirmed: lumbar puncture, contrast-enhanced MRI, vascular risk assessment",
    "Healthy": "No AI-flagged follow-up",
}
DISCLAIMER = ("AI-assisted screening results. Final diagnosis requires clinical assessment "
              "and appropriate diagnostic criteria.")

# (header, width)
COLUMNS = [
    ("Scan date & time", 19), ("Patient name", 26), ("Medical number", 17), ("AI finding", 18),
    ("AI confidence", 14), ("Regions flagged", 15), ("Recommended next step", 58),
    ("Analysis time (s)", 16), ("Scan ID", 44),
]

# style indexes in styles.xml <cellXfs>
# index 0 is Excel's default for blank cells, so it must stay borderless
S_PLAIN, S_TEXT, S_HEADER, S_TITLE, S_SUB, S_DATE, S_PCT, S_INT, S_SEC, S_RED, S_AMBER, S_GREEN, S_NOTE, S_MONO = range(14)
FINDING_STYLE = {"Infected": S_RED, "Uncertain": S_AMBER, "Healthy": S_GREEN}

STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="3">
<numFmt numFmtId="164" formatCode="dd mmm yyyy, hh:mm"/>
<numFmt numFmtId="165" formatCode="0.0%"/>
<numFmt numFmtId="166" formatCode="0.00"/>
</numFmts>
<fonts count="7">
<font><sz val="11"/><color rgb="FF1E293B"/><name val="Calibri"/><family val="2"/></font>
<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/><family val="2"/></font>
<font><b/><sz val="16"/><color rgb="FF0B1B33"/><name val="Calibri"/><family val="2"/></font>
<font><sz val="10"/><color rgb="FF64748B"/><name val="Calibri"/><family val="2"/></font>
<font><b/><sz val="11"/><color rgb="FFB4232C"/><name val="Calibri"/><family val="2"/></font>
<font><b/><sz val="11"/><color rgb="FF93540A"/><name val="Calibri"/><family val="2"/></font>
<font><b/><sz val="11"/><color rgb="FF0C6E3B"/><name val="Calibri"/><family val="2"/></font>
</fonts>
<fills count="6">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF0E2250"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFDEFF0"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFFF6E5"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFEAFAF1"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="2">
<border><left/><right/><top/><bottom/><diagonal/></border>
<border><left/><right/><top/><bottom style="thin"><color rgb="FFE2E8F0"/></bottom><diagonal/></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="14">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" applyBorder="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="1" fillId="2" borderId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="2" fillId="0" borderId="0" applyFont="1"/>
<xf numFmtId="0" fontId="3" fillId="0" borderId="0" applyFont="1"/>
<xf numFmtId="164" fontId="0" fillId="0" borderId="1" applyNumberFormat="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>
<xf numFmtId="165" fontId="0" fillId="0" borderId="1" applyNumberFormat="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="1" fontId="0" fillId="0" borderId="1" applyNumberFormat="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="166" fontId="0" fillId="0" borderId="1" applyNumberFormat="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="4" fillId="3" borderId="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="5" fillId="4" borderId="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="6" fillId="5" borderId="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="3" fillId="0" borderId="0" applyFont="1" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
<xf numFmtId="0" fontId="3" fillId="0" borderId="1" applyFont="1" applyBorder="1" applyAlignment="1"><alignment vertical="center"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
</Relationships>"""

WORKBOOK = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Scan registry" sheetId="1" r:id="rId1"/></sheets>
<definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">'Scan registry'!$A$4:$I${last}</definedName>
<definedName name="_xlnm.Print_Titles" localSheetId="0">'Scan registry'!$4:$4</definedName></definedNames>
</workbook>"""

WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

CORE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>MS SmartScan scan registry</dc:title><dc:creator>MS SmartScan</dc:creator>
<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
</cp:coreProperties>"""


def _col(i):
    return "ABCDEFGHIJ"[i]


def _excel_date(value):
    """ISO timestamp → Excel serial date number."""
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    delta = dt - datetime(1899, 12, 30)
    return delta.days + delta.seconds / 86400


def _text(ref, value, style=S_TEXT):
    return f'<c r="{ref}" t="inlineStr" s="{style}"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>'


def _num(ref, value, style):
    if value is None:
        return _text(ref, "—", style)
    return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'


def build(rows, filter_label="All results", query=""):
    """rows: dicts from the scans table, newest first. Returns .xlsx bytes."""
    now = datetime.now()
    out = []
    subtitle = f"Exported {now.strftime('%d %b %Y, %H:%M')}  ·  {len(rows)} scan{'s' if len(rows) != 1 else ''}  ·  Filter: {filter_label}"
    if query:
        subtitle += f'  ·  Search: "{query}"'
    out.append(f'<row r="1" ht="26" customHeight="1">{_text("A1", "MS SmartScan — Scan Registry", S_TITLE)}</row>')
    out.append(f'<row r="2">{_text("A2", subtitle, S_SUB)}</row>')
    out.append('<row r="4" ht="22" customHeight="1">'
               + "".join(_text(f"{_col(i)}4", h, S_HEADER) for i, (h, _) in enumerate(COLUMNS)) + "</row>")

    r = 4
    for s in rows:
        r += 1
        result = s.get("result")
        conf = s.get("confidence")
        conf = round(conf / 100, 4) if (conf is not None and result != "Healthy") else None   # "Clear" has no model confidence
        cells = [
            _num(f"A{r}", _excel_date(s.get("created_at")), S_DATE),
            _text(f"B{r}", s.get("patient") or "Unnamed (legacy record)"),
            _text(f"C{r}", s.get("patient_id") or "—"),
            _text(f"D{r}", FINDING.get(result, result or "—"), FINDING_STYLE.get(result, S_TEXT)),
            _num(f"E{r}", conf, S_PCT),
            _num(f"F{r}", s.get("lesions"), S_INT),
            _text(f"G{r}", NEXT_STEP.get(result, "—")),
            _num(f"H{r}", s.get("seconds"), S_SEC),
            _text(f"I{r}", s.get("id", ""), S_MONO),
        ]
        out.append(f'<row r="{r}" ht="20" customHeight="1">{"".join(cells)}</row>')
    last = max(r, 5)
    note_row = r + 2
    out.append(f'<row r="{note_row}" ht="30" customHeight="1">{_text(f"A{note_row}", DISCLAIMER, S_NOTE)}</row>')

    cols = "".join(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>' for i, (_, w) in enumerate(COLUMNS))
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheetPr><pageSetUpPr fitToPage="1"/></sheetPr>'
        f'<dimension ref="A1:I{note_row}"/>'
        '<sheetViews><sheetView workbookViewId="0" showGridLines="0">'
        '<pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        f"<cols>{cols}</cols>"
        f'<sheetData>{"".join(out)}</sheetData>'
        f'<autoFilter ref="A4:I{last}"/>'
        f'<mergeCells count="3"><mergeCell ref="A1:I1"/><mergeCell ref="A2:I2"/><mergeCell ref="A{note_row}:I{note_row}"/></mergeCells>'
        '<pageMargins left="0.4" right="0.4" top="0.5" bottom="0.5" header="0.3" footer="0.3"/>'
        '<pageSetup orientation="landscape" fitToWidth="1" fitToHeight="0"/>'
        "</worksheet>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("docProps/core.xml", CORE.format(now=now.strftime("%Y-%m-%dT%H:%M:%SZ")))
        z.writestr("xl/workbook.xml", WORKBOOK.replace("{last}", str(last)))
        z.writestr("xl/_rels/workbook.xml.rels", WORKBOOK_RELS)
        z.writestr("xl/styles.xml", STYLES)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return buf.getvalue()
