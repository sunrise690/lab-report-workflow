"""提取Word段落、原表文字与嵌入图片出处，不转换数值或读取图片像素。"""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def text_of(element):
    parts = []
    for node in element.iter():
        if node.tag == "{" + NS["w"] + "}t":
            parts.append(node.text or "")
        elif node.tag in {"{" + NS["w"] + "}br", "{" + NS["w"] + "}cr"}:
            parts.append("\n")
        elif node.tag == "{" + NS["w"] + "}tab":
            parts.append("\t")
    return "".join(parts)


def extract_table(element, block_index, tables, table_number, parent_table=None, parent_cell=None):
    """保留平面rows接口，同时用cell_content和父单元格定位表达嵌套结构。"""
    record = {
        "table": table_number,
        "block_index": block_index,
        "rows": [],
        "cell_spans": [],
        "cell_content": [],
        "parent_table": parent_table,
        # 行、单元格均从1起计，指XML中的物理单元格，不扩展合并单元格。
        "parent_cell": parent_cell,
    }
    tables[table_number - 1] = record
    for row_index, tr in enumerate(element.findall("w:tr", NS), 1):
        cells, cell_spans, row_content = [], [], []
        for cell_index, tc in enumerate(tr.findall("w:tc", NS), 1):
            parts, content = [], []
            for child in tc:
                if child.tag == "{" + NS["w"] + "}p":
                    text = text_of(child)
                    parts.append(text)
                    content.append({"kind": "paragraph", "text": text})
                elif child.tag == "{" + NS["w"] + "}tbl":
                    nested_number = len(tables) + 1
                    tables.append(None)
                    nested = extract_table(
                        child, block_index, tables, nested_number,
                        parent_table=table_number,
                        parent_cell={"row": row_index, "cell": cell_index},
                    )
                    parts.append("\n".join("\t".join(row) for row in nested["rows"]))
                    content.append({"kind": "table", "table": nested_number})
            cells.append("\n".join(parts))
            row_content.append(content)
            gs = tc.find("w:tcPr/w:gridSpan", NS)
            vm = tc.find("w:tcPr/w:vMerge", NS)
            cell_spans.append({
                "grid_span": int(gs.get("{" + NS["w"] + "}val", "1")) if gs is not None else 1,
                "vertical_merge": vm.get("{" + NS["w"] + "}val", "continue") if vm is not None else None,
            })
        record["rows"].append(cells)
        record["cell_spans"].append(cell_spans)
        record["cell_content"].append(row_content)
    return record


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--media-dir", type=Path)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    if args.source.resolve() == args.out.resolve():
        ap.error("输出不能覆盖源Word")
    if args.out.exists() and not args.overwrite:
        ap.error("输出已存在；换新路径或显式使用--overwrite")
    blocks, tables, images = [], [], []
    with ZipFile(args.source) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
        rels = {}
        rels_name = "word/_rels/document.xml.rels"
        if rels_name in archive.namelist():
            rels = {
                x.attrib["Id"]: x.attrib.get("Target", "")
                for x in ET.fromstring(archive.read(rels_name))
                if x.attrib.get("TargetMode") != "External"
            }
        body = document.find("w:body", NS)
        if body is None:
            ap.error("Word正文中没有w:body")
        # 先为顶层表预留编号，新增嵌套表不会改变既有顶层表的编号。
        tables = [None] * len(body.findall("w:tbl", NS))
        top_table_number = 0
        for element in body:
            kind = element.tag.rsplit("}", 1)[-1]
            if kind not in {"p", "tbl"}:
                continue
            index = len(blocks)
            block = {"index": index, "kind": "paragraph" if kind == "p" else "table"}
            if kind == "p":
                block["text"] = text_of(element)
            else:
                top_table_number += 1
                block["table"] = top_table_number
                extract_table(element, index, tables, top_table_number)
            blocks.append(block)
            for blip in element.findall(".//a:blip", NS):
                rid = blip.get("{" + NS["r"] + "}embed")
                member = "word/" + rels.get(rid, "")
                if not member.startswith("word/media/") or ".." in Path(member).parts:
                    continue
                data = archive.read(member)
                image = {
                    "inline_index": len(images) + 1,
                    "block_index": index,
                    "relationship_id": rid,
                    "member": member,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                }
                if args.media_dir:
                    target = args.media_dir / Path(member).name
                    if target.exists() and target.read_bytes() != data and not args.overwrite:
                        raise FileExistsError(f"不覆盖已有不同媒体：{target}")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    image["extracted_path"] = str(target)
                images.append(image)
        for image in images:
            pos = image["block_index"]
            before = [b["text"] for b in blocks[:pos] if b["kind"] == "paragraph" and b.get("text", "").strip()]
            after = [b["text"] for b in blocks[pos + 1:] if b["kind"] == "paragraph" and b.get("text", "").strip()]
            image["context_before"] = before[-1] if before else ""
            image["context_after"] = after[0] if after else ""
    result = {
        "source": str(args.source.resolve()),
        "method": "原表文字和原始嵌入字节；未计算像素、未猜测图像对应关系。",
        "blocks": blocks, "tables": tables, "images": images,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已提取{len(tables)}张表、{len(images)}处图片引用：{args.out}")


if __name__ == "__main__":
    main()
