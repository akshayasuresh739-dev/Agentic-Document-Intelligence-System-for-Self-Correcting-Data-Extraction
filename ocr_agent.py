"""
OCR Agent
---------
Uses OpenAI GPT-4o vision API to extract raw text from
any document (PDF page images or image files).

NOTE: OpenAI does not accept raw PDFs via the API.
      PDFs are converted to images first using PyMuPDF (fitz),
      then each page image is sent to GPT-4o vision.
"""

import base64
import os
from pathlib import Path
from openai import OpenAI


class OCRAgent:

    def __init__(self):
        self.client = OpenAI()          # reads OPENAI_API_KEY from env
        self.model  = "gpt-4o"

    def _encode_image_bytes(self, image_bytes: bytes) -> str:
        return base64.b64encode(image_bytes).decode("utf-8")

    def _pdf_to_images(self, pdf_path: str) -> list:
        """Convert each PDF page to PNG bytes using PyMuPDF."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError(
                "PyMuPDF is required for PDF support.\n"
                "Install it with:  pip install pymupdf"
            )
        doc = fitz.open(pdf_path)
        pages = []
        for page in doc:
            mat = fitz.Matrix(2.0, 2.0)   # 2x resolution for better OCR
            pix = page.get_pixmap(matrix=mat)
            pages.append(pix.tobytes("png"))
        doc.close()
        return pages

    def _ocr_image_bytes(self, image_bytes: bytes, media_type: str = "image/png") -> str:
        """Send one image to GPT-4o vision and return extracted text."""
        b64 = self._encode_image_bytes(image_bytes)
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{b64}",
                            "detail": "high"
                        }
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract and return ALL text from this document exactly "
                            "as it appears. Preserve labels, values, and layout. "
                            "Do not summarise — return the raw text content only."
                        )
                    }
                ]
            }]
        )
        return response.choices[0].message.content.strip()

    def extract_text(self, file_path: str) -> str:
        """
        Extract raw text from a PDF or image file.
        PDFs: converted page-by-page via PyMuPDF, then GPT-4o vision.
        Images (PNG/JPG): sent directly to GPT-4o vision.
        Returns empty string if file not found.
        """
        if not file_path or not os.path.exists(file_path):
            return ""

        ext = Path(file_path).suffix.lower()

        if ext == ".pdf":
            page_images = self._pdf_to_images(file_path)
            texts = [self._ocr_image_bytes(pg, "image/png") for pg in page_images]
            return "\n".join(texts).strip()
        else:
            media_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
            media_type = media_map.get(ext, "image/png")
            with open(file_path, "rb") as f:
                image_bytes = f.read()
            return self._ocr_image_bytes(image_bytes, media_type)
