"""列出实验文件、ZIP时间及图像头部元数据；不计算图像像素统计。"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("directory", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--hashes", action="store_true")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    root = args.directory.resolve()
    if not root.is_dir():
        ap.error("输入必须是目录")
    if args.out and args.out.exists() and not args.overwrite:
        ap.error("输出已存在；换新路径或显式使用--overwrite")
    files = root.rglob("*") if args.recursive else root.iterdir()
    records, groups = [], {}
    image_exts = {".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".apng", ".tif", ".tiff", ".bmp", ".dib", ".webp"}
    for p in sorted(files):
        if not p.is_file() or not p.resolve().is_relative_to(root):
            continue
        if args.out and p.resolve() == args.out.resolve():
            continue
        st = p.stat()
        row = {
            "file": p.relative_to(root).as_posix(),
            "bytes": st.st_size,
            "modified_utc": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
        }
        if args.hashes:
            digest = hashlib.sha256()
            with p.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            row["sha256"] = digest.hexdigest()
            groups.setdefault(row["sha256"], []).append(row["file"])
        if p.suffix.lower() in image_exts:
            try:
                from PIL import Image
                with Image.open(p) as im:
                    row["image_metadata"] = {
                        "format": im.format,
                        "width": im.width,
                        "height": im.height,
                        "dpi": im.info.get("dpi"),
                    }
                    accepted = {
                        extension.lower()
                        for extension, image_format in Image.registered_extensions().items()
                        if image_format == im.format
                    }
                    if not accepted:
                        accepted = {"." + im.format.lower()}
                    row["extension_matches_format"] = p.suffix.lower() in accepted
            except Exception as exc:
                row["metadata_error"] = str(exc)
        if p.suffix.lower() == ".zip":
            try:
                with ZipFile(p) as archive:
                    row["zip_entries"] = [
                        {
                            "member": x.filename,
                            "bytes": x.file_size,
                            "zip_member_time_naive": "%04d-%02d-%02d %02d:%02d:%02d" % x.date_time,
                        }
                        for x in archive.infolist() if not x.is_dir()
                    ]
            except Exception as exc:
                row["archive_error"] = str(exc)
        records.append(row)
    result = {
        "root": str(root),
        "time_note": "文件修改时间为UTC；ZIP条目时间无时区，不能自动当作拍摄时间。",
        "files": records,
        "duplicate_groups": [v for v in groups.values() if len(v) > 1],
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"已记录{len(records)}个文件：{args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
