#!/usr/bin/env python3

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


def parse_markdown(source: Path) -> tuple[str, list[str], list[str], list[dict[str, object]]]:
    lines = source.read_text(encoding="utf-8").splitlines()

    title = source.stem
    test_data: list[str] = []
    environment_inputs: list[str] = []
    sections: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    mode: str | None = None

    for raw_line in lines:
        line = raw_line.rstrip("\n")

        if line.startswith("# "):
            title = line[2:].strip()
            continue

        if line == "### Test Data Requirements":
            mode = "test_data"
            continue

        if line == "### Environment Inputs":
            mode = "environment"
            continue

        if line.startswith("## "):
            mode = "cases"
            if current:
                sections.append(current)
            current = {
                "title": line[3:].strip(),
                "role": "",
                "route": "",
                "mode": "",
                "destructive": "",
                "note": "",
                "expected": "",
                "steps": [],
            }
            continue

        if mode == "test_data" and line.startswith("- "):
            test_data.append(line[2:].strip())
            continue

        if mode == "environment" and line.startswith("- "):
            environment_inputs.append(line[2:].strip())
            continue

        if mode != "cases" or current is None:
            continue

        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("Role: "):
            current["role"] = stripped[len("Role: ") :].strip()
        elif stripped.startswith("Route: "):
            current["route"] = stripped[len("Route: ") :].strip()
        elif stripped.startswith("Mode: "):
            current["mode"] = stripped[len("Mode: ") :].strip()
        elif stripped.startswith("destructive: "):
            current["destructive"] = stripped[len("destructive: ") :].strip()
        elif stripped.startswith("Note: "):
            current["note"] = stripped[len("Note: ") :].strip()
        elif stripped.startswith("Expected: "):
            current["expected"] = stripped[len("Expected: ") :].strip()
        elif stripped.startswith("- "):
            steps = current.setdefault("steps", [])
            if isinstance(steps, list):
                steps.append(stripped[2:].strip())

    if current:
        sections.append(current)

    return title, test_data, environment_inputs, sections


def col_letter(index: int) -> str:
    result = ""
    value = index
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def multiline_bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def build_sheet(rows: list[list[str]]) -> str:
    max_cols = max((len(row) for row in rows), default=1)
    widths = []

    for col_index in range(max_cols):
        max_len = 10
        for row in rows:
            value = row[col_index] if col_index < len(row) else ""
            longest_line = max((len(part) for part in str(value).split("\n")), default=0)
            max_len = max(max_len, longest_line)
        widths.append(min(max_len + 2, 60))

    cols_xml = "".join(
        f'<col min="{index}" max="{index}" width="{widths[index - 1]:.2f}" customWidth="1"/>'
        for index in range(1, max_cols + 1)
    )

    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cell_xml = []
        for col_index in range(1, max_cols + 1):
            value = row[col_index - 1] if col_index - 1 < len(row) else ""
            text = escape(str(value))
            ref = f"{col_letter(col_index)}{row_index}"
            cell_xml.append(
                f'<c r="{ref}" s="0" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'
            )
        row_xml.append(f'<row r="{row_index}">{"".join(cell_xml)}</row>')

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<cols>{cols_xml}</cols>"
        f"<sheetData>{''.join(row_xml)}</sheetData>"
        "</worksheet>"
    )


def build_workbook(source: Path, output: Path) -> None:
    title, test_data, environment_inputs, sections = parse_markdown(source)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    overview_rows = [
        ["Document", title],
        ["Source", str(source)],
        ["Generated", generated_at],
        ["Total test cases", str(len(sections))],
        ["", ""],
        ["Test Data Requirements", multiline_bullets(test_data)],
        ["", ""],
        ["Environment Inputs", multiline_bullets(environment_inputs)],
    ]

    case_rows = [["ID", "Title", "Role", "Route", "Mode", "Destructive", "Note", "Expected", "Steps"]]
    step_rows = [["Case ID", "Case Title", "Step #", "Step"]]

    for index, section in enumerate(sections, start=1):
        case_id = f"TC-{index:03d}"
        steps = section.get("steps", [])
        if not isinstance(steps, list):
            steps = []

        case_rows.append(
            [
                case_id,
                str(section.get("title", "")),
                str(section.get("role", "")),
                str(section.get("route", "")),
                str(section.get("mode", "")),
                str(section.get("destructive", "") or ("true" if section.get("mode") == "destructive" else "false")),
                str(section.get("note", "")),
                str(section.get("expected", "")),
                "\n".join(f"{step_index}. {step}" for step_index, step in enumerate(steps, start=1)),
            ]
        )

        for step_index, step in enumerate(steps, start=1):
            step_rows.append([case_id, str(section.get("title", "")), str(step_index), str(step)])

    sheets = [
        ("Overview", overview_rows),
        ("Test Cases", case_rows),
        ("Test Steps", step_rows),
    ]

    content_types = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">
  <Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>
  <Default Extension=\"xml\" ContentType=\"application/xml\"/>
  <Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/>
  <Override PartName=\"/docProps/core.xml\" ContentType=\"application/vnd.openxmlformats-package.core-properties+xml\"/>
  <Override PartName=\"/docProps/app.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.extended-properties+xml\"/>
  <Override PartName=\"/xl/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml\"/>
  <Override PartName=\"/xl/theme/theme1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.theme+xml\"/>
  <Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>
  <Override PartName=\"/xl/worksheets/sheet2.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>
  <Override PartName=\"/xl/worksheets/sheet3.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>
</Types>"""

    package_rels = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/>
  <Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties\" Target=\"docProps/core.xml\"/>
  <Relationship Id=\"rId3\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties\" Target=\"docProps/app.xml\"/>
</Relationships>"""

    workbook_xml = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">
  <sheets>
    <sheet name=\"Overview\" sheetId=\"1\" r:id=\"rId1\"/>
    <sheet name=\"Test Cases\" sheetId=\"2\" r:id=\"rId2\"/>
    <sheet name=\"Test Steps\" sheetId=\"3\" r:id=\"rId3\"/>
  </sheets>
</workbook>"""

    workbook_rels = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/>
  <Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet2.xml\"/>
  <Relationship Id=\"rId3\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet3.xml\"/>
  <Relationship Id=\"rId4\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" Target=\"styles.xml\"/>
  <Relationship Id=\"rId5\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme\" Target=\"theme/theme1.xml\"/>
</Relationships>"""

    styles_xml = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<styleSheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">
  <fonts count=\"1\"><font><sz val=\"11\"/><name val=\"Aptos\"/></font></fonts>
  <fills count=\"2\"><fill><patternFill patternType=\"none\"/></fill><fill><patternFill patternType=\"gray125\"/></fill></fills>
  <borders count=\"1\"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\"/></cellStyleXfs>
  <cellXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\" xfId=\"0\" applyAlignment=\"1\"><alignment vertical=\"top\" wrapText=\"1\"/></xf></cellXfs>
  <cellStyles count=\"1\"><cellStyle name=\"Normal\" xfId=\"0\" builtinId=\"0\"/></cellStyles>
</styleSheet>"""

    theme_xml = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<a:theme xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" name=\"Office Theme\">
  <a:themeElements>
    <a:clrScheme name=\"Office\">
      <a:dk1><a:sysClr val=\"windowText\" lastClr=\"000000\"/></a:dk1>
      <a:lt1><a:sysClr val=\"window\" lastClr=\"FFFFFF\"/></a:lt1>
      <a:dk2><a:srgbClr val=\"1F497D\"/></a:dk2>
      <a:lt2><a:srgbClr val=\"EEECE1\"/></a:lt2>
      <a:accent1><a:srgbClr val=\"4F81BD\"/></a:accent1>
      <a:accent2><a:srgbClr val=\"C0504D\"/></a:accent2>
      <a:accent3><a:srgbClr val=\"9BBB59\"/></a:accent3>
      <a:accent4><a:srgbClr val=\"8064A2\"/></a:accent4>
      <a:accent5><a:srgbClr val=\"4BACC6\"/></a:accent5>
      <a:accent6><a:srgbClr val=\"F79646\"/></a:accent6>
      <a:hlink><a:srgbClr val=\"0000FF\"/></a:hlink>
      <a:folHlink><a:srgbClr val=\"800080\"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name=\"Office\">
      <a:majorFont><a:latin typeface=\"Aptos\"/></a:majorFont>
      <a:minorFont><a:latin typeface=\"Aptos\"/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name=\"Office\"><a:fillStyleLst/><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst/></a:fmtScheme>
  </a:themeElements>
</a:theme>"""

    iso_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    core_xml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<cp:coreProperties xmlns:cp=\"http://schemas.openxmlformats.org/package/2006/metadata/core-properties\" xmlns:dc=\"http://purl.org/dc/elements/1.1/\" xmlns:dcterms=\"http://purl.org/dc/terms/\" xmlns:dcmitype=\"http://purl.org/dc/dcmitype/\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">
  <dc:title>{escape(title)}</dc:title>
  <dc:creator>OpenCode QA</dc:creator>
  <cp:lastModifiedBy>OpenCode QA</cp:lastModifiedBy>
  <dcterms:created xsi:type=\"dcterms:W3CDTF\">{iso_now}</dcterms:created>
  <dcterms:modified xsi:type=\"dcterms:W3CDTF\">{iso_now}</dcterms:modified>
</cp:coreProperties>"""

    app_xml = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Properties xmlns=\"http://schemas.openxmlformats.org/officeDocument/2006/extended-properties\" xmlns:vt=\"http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes\">
  <Application>OpenCode QA</Application>
</Properties>"""

    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", content_types)
        workbook.writestr("_rels/.rels", package_rels)
        workbook.writestr("docProps/core.xml", core_xml)
        workbook.writestr("docProps/app.xml", app_xml)
        workbook.writestr("xl/workbook.xml", workbook_xml)
        workbook.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        workbook.writestr("xl/styles.xml", styles_xml)
        workbook.writestr("xl/theme/theme1.xml", theme_xml)
        for sheet_index, (_sheet_name, rows) in enumerate(sheets, start=1):
            workbook.writestr(f"xl/worksheets/sheet{sheet_index}.xml", build_sheet(rows))


def main() -> int:
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: export-user-test-script.py <markdown-path> [xlsx-path]", file=sys.stderr)
        return 1

    source = Path(sys.argv[1]).expanduser().resolve()
    if not source.exists():
        print(f"Markdown file not found: {source}", file=sys.stderr)
        return 1

    output = Path(sys.argv[2]).expanduser().resolve() if len(sys.argv) == 3 else source.with_suffix(".xlsx")
    build_workbook(source, output)
    print(f"Created {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
