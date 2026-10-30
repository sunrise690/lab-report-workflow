"""用临时自造输入检验原表、图片与文件保护行为；不依赖真实实验资料。"""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from xml.sax.saxutils import escape
from zipfile import ZipFile

from PIL import Image
import pymupdf


SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "lab-report-workflow" / "scripts"
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def paragraph(text=""):
    return f'<w:p><w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'


def table(rows):
    return "<w:tbl>" + "".join(
        "<w:tr>" + "".join("<w:tc>" + paragraph(cell) + "</w:tc>" for cell in row) + "</w:tr>"
        for row in rows
    ) + "</w:tbl>"


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lab-report-helper-test-")
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def run_helper(self, script, *args, success=True):
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(SCRIPTS / script), *map(str, args)],
            capture_output=True, text=True, encoding="utf-8",
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def make_docx(self, body, name="records.docx", image_bytes=None, include_rels=False):
        path = self.root / name
        with ZipFile(path, "w") as archive:
            archive.writestr(
                "[Content_Types].xml",
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="jpg" ContentType="image/jpeg"/>'
                '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                '</Types>',
            )
            archive.writestr(
                "_rels/.rels",
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'<Relationship Id="rId1" Type="{REL_NS}/officeDocument" Target="word/document.xml"/>'
                '</Relationships>',
            )
            archive.writestr(
                "word/document.xml",
                f'<w:document xmlns:w="{WORD_NS}" xmlns:r="{REL_NS}" xmlns:a="{DRAWING_NS}">'
                f'<w:body>{body}</w:body></w:document>',
            )
            if image_bytes is not None or include_rels:
                relationship = (
                    f'<Relationship Id="rImage" Type="{REL_NS}/image" Target="media/image1.jpg"/>'
                    if image_bytes is not None else ""
                )
                archive.writestr(
                    "word/_rels/document.xml.rels",
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    + relationship + '</Relationships>',
                )
            if image_bytes is not None:
                archive.writestr("word/media/image1.jpg", image_bytes)
        return path

    def jpeg_bytes(self, orientation=None):
        image = Image.new("RGB", (40, 20), "blue")
        stream = io.BytesIO()
        options = {}
        if orientation is not None:
            exif = Image.Exif()
            exif[274] = orientation
            options["exif"] = exif
        image.save(stream, format="JPEG", **options)
        return stream.getvalue()

    def extract(self, source, **kwargs):
        output = self.root / (source.stem + ".json")
        self.run_helper("extract_docx_records.py", source, "--out", output, **kwargs)
        return json.loads(output.read_text(encoding="utf-8"))

    def test_blank_zero_and_failed_measurement_remain_distinct(self):
        rows = [["组次", "仪器读数", "状态"], ["1", "", "未记录"], ["2", "0", "已记录"], ["3", "", "未能测得"]]
        source = self.make_docx(table(rows), include_rels=True)
        result = self.extract(source)
        self.assertEqual(result["tables"][0]["rows"], rows)
        self.assertEqual(result["tables"][0]["cell_spans"][1][1]["grid_span"], 1)

    def test_plain_document_without_relationships_is_supported(self):
        source = self.make_docx(paragraph("原始记录 12.50 mV"))
        result = self.extract(source)
        self.assertEqual(result["blocks"][0]["text"], "原始记录 12.50 mV")
        self.assertEqual(result["tables"], [])
        self.assertEqual(result["images"], [])

    def test_nested_tables_keep_text_structure_and_parent_cell(self):
        inner = table([["嵌套读数12.50", "0"]])
        middle = "<w:tbl><w:tr><w:tc>" + paragraph("中间层") + inner + paragraph() + "</w:tc></w:tr></w:tbl>"
        outer = (
            "<w:tbl><w:tr><w:tc>" + paragraph("第一列") + "</w:tc><w:tc>"
            '<w:tcPr><w:gridSpan w:val="2"/></w:tcPr>'
            + paragraph("之前") + middle + paragraph("之后") + "</w:tc></w:tr></w:tbl>"
        )
        source = self.make_docx(outer + table([["第二张顶层表"]]))
        result = self.extract(source)
        records = {record["table"]: record for record in result["tables"]}
        self.assertEqual(result["blocks"][1]["table"], 2)
        self.assertEqual(records[2]["rows"], [["第二张顶层表"]])
        self.assertIn("嵌套读数12.50", records[1]["rows"][0][1])
        self.assertTrue(records[1]["rows"][0][1].startswith("之前\n"))
        self.assertTrue(records[1]["rows"][0][1].endswith("\n之后"))
        self.assertEqual(records[1]["cell_spans"][0][1]["grid_span"], 2)
        nested_id = records[1]["cell_content"][0][1][1]["table"]
        self.assertEqual(records[nested_id]["parent_table"], 1)
        self.assertEqual(records[nested_id]["parent_cell"], {"row": 1, "cell": 2})
        inner_id = records[nested_id]["cell_content"][0][0][1]["table"]
        self.assertEqual(records[inner_id]["rows"], [["嵌套读数12.50", "0"]])
        self.assertEqual(records[inner_id]["parent_table"], nested_id)
        self.assertEqual(records[inner_id]["parent_cell"], {"row": 1, "cell": 1})

    def test_embedded_image_is_extracted_without_changing_bytes(self):
        data = self.jpeg_bytes()
        source = self.make_docx('<w:p><w:r><w:drawing><a:blip r:embed="rImage"/></w:drawing></w:r></w:p>', image_bytes=data)
        output, media = self.root / "image-records.json", self.root / "media"
        self.run_helper("extract_docx_records.py", source, "--out", output, "--media-dir", media)
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual((media / "image1.jpg").read_bytes(), data)
        self.assertEqual(result["images"][0]["sha256"], hashlib.sha256(data).hexdigest())

    def test_jpeg_container_preserves_image_bytes_and_display_dimensions(self):
        source, output = self.root / "input.jpg", self.root / "display.pdf"
        data = self.jpeg_bytes()
        source.write_bytes(data)
        self.run_helper("jpeg_display_pdf.py", source, output, "--width-cm", 10)
        with pymupdf.open(output) as document:
            page = document[0]
            self.assertAlmostEqual(page.rect.width, 10 * 72 / 2.54, places=3)
            self.assertAlmostEqual(page.rect.width / page.rect.height, 2, places=5)
            self.assertEqual(document.extract_image(page.get_images()[0][0])["image"], data)
        self.assertEqual(source.read_bytes(), data)

    def test_exif_orientation_is_rejected_without_producing_pdf(self):
        for orientation in (2, 3, 6, 8):
            with self.subTest(orientation=orientation):
                data = self.jpeg_bytes(orientation)
                source = self.root / f"orientation-{orientation}.jpg"
                output = self.root / f"orientation-{orientation}.pdf"
                source.write_bytes(data)
                result = self.run_helper("jpeg_display_pdf.py", source, output, success=False)
                self.assertIn("EXIF Orientation", result.stderr)
                self.assertFalse(output.exists())
                self.assertEqual(source.read_bytes(), data)

    def test_different_existing_extracted_image_is_not_overwritten(self):
        data = self.jpeg_bytes()
        source = self.make_docx('<w:p><w:r><w:drawing><a:blip r:embed="rImage"/></w:drawing></w:r></w:p>', image_bytes=data)
        media = self.root / "media"
        media.mkdir()
        target = media / "image1.jpg"
        target.write_bytes(b"existing-image-do-not-overwrite")
        output = self.root / "records.json"
        self.run_helper("extract_docx_records.py", source, "--out", output, "--media-dir", media, success=False)
        self.assertEqual(target.read_bytes(), b"existing-image-do-not-overwrite")
        self.assertFalse(output.exists())

    def test_existing_output_files_are_not_overwritten(self):
        document = self.make_docx(paragraph("记录"))
        jpeg = self.root / "input.jpg"
        jpeg.write_bytes(self.jpeg_bytes())
        cases = [
            ("extract_docx_records.py", [document, "--out"], "records.json"),
            ("inventory_lab_sources.py", [self.root, "--out"], "inventory.json"),
            ("jpeg_display_pdf.py", [jpeg], "display.pdf"),
        ]
        for script, arguments, leaf in cases:
            with self.subTest(script=script):
                output = self.root / leaf
                output.write_bytes(b"existing-result-do-not-overwrite")
                self.run_helper(script, *arguments, output, success=False)
                self.assertEqual(output.read_bytes(), b"existing-result-do-not-overwrite")

    def test_source_file_cannot_be_used_as_output_even_with_overwrite(self):
        document = self.make_docx(paragraph("不能覆盖原记录"))
        before = document.read_bytes()
        self.run_helper("extract_docx_records.py", document, "--out", document, "--overwrite", success=False)
        self.assertEqual(document.read_bytes(), before)
        jpeg = self.root / "input.jpg"
        data = self.jpeg_bytes()
        jpeg.write_bytes(data)
        self.run_helper("jpeg_display_pdf.py", jpeg, jpeg, "--overwrite", success=False)
        self.assertEqual(jpeg.read_bytes(), data)

    def test_real_format_aliases_are_accepted_but_misnamed_images_are_flagged(self):
        Image.new("RGB", (2, 3)).save(self.root / "valid.tif", format="TIFF")
        Image.new("RGB", (2, 3)).save(self.root / "valid.tiff", format="TIFF")
        jpeg = self.jpeg_bytes()
        for leaf in ("valid.jpe", "valid.jfif", "misnamed.png"):
            (self.root / leaf).write_bytes(jpeg)
        output = self.root / "inventory.json"
        self.run_helper("inventory_lab_sources.py", self.root, "--hashes", "--out", output)
        result = json.loads(output.read_text(encoding="utf-8"))
        records = {record["file"]: record for record in result["files"]}
        for leaf in ("valid.tif", "valid.tiff", "valid.jpe", "valid.jfif"):
            self.assertTrue(records[leaf]["extension_matches_format"], leaf)
        self.assertFalse(records["misnamed.png"]["extension_matches_format"])
        self.assertTrue(any(set(group) == {"valid.jpe", "valid.jfif", "misnamed.png"} for group in result["duplicate_groups"]))
        self.assertEqual(len(list(self.root.glob("valid.*"))), 4)


if __name__ == "__main__":
    unittest.main()
