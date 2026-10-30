"""为JPEG建立正确显示尺寸的PDF容器，不改JPEG字节或像素。"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--width-cm", type=float, default=12.0)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    if args.source.resolve() == args.output.resolve():
        ap.error("输出不能覆盖输入")
    if args.output.suffix.lower() != ".pdf":
        ap.error("输出必须为.pdf")
    if args.output.exists() and not args.overwrite:
        ap.error("输出已存在；换新路径或显式使用--overwrite")
    if not math.isfinite(args.width_cm) or args.width_cm <= 0:
        ap.error("显示宽度必须为有限正数")
    from PIL import Image
    import pymupdf
    with Image.open(args.source) as image:
        if image.format != "JPEG":
            ap.error("本工具只处理JPEG，其他格式不要先转码套用")
        orientation = image.getexif().get(274, 1)
        if orientation != 1:
            ap.error(
                f"JPEG的EXIF Orientation为{orientation}；本工具只修复显示尺寸，"
                "不处理方向变换，未生成PDF。请先核对原图显示方向。"
            )
        width, height = image.size
    data = args.source.read_bytes()
    page_width = args.width_cm * 72 / 2.54
    page_height = page_width * height / width
    doc = pymupdf.open()
    page = doc.new_page(width=page_width, height=page_height)
    xref = page.insert_image(page.rect, stream=data, keep_proportion=True)
    if doc.extract_image(xref)["image"] != data:
        raise RuntimeError("嵌入字节不一致，停止保存")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(args.output)
    doc.close()
    print(json.dumps({
        "output": str(args.output),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "jpeg_bytes_preserved": True,
        "display_points": [page_width, page_height],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
