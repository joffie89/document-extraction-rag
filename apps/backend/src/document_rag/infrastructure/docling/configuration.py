"""Build Docling with English-only RapidOCR settings."""

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    OcrMode,
    PdfPipelineOptions,
    RapidOcrOptions,
)
from docling.document_converter import (
    DocumentConverter,
    ImageFormatOption,
    PdfFormatOption,
)


def build_document_converter(
    timeout_seconds: float,
    ocr_language: str = "en",
) -> DocumentConverter:
    """Configure Docling for every registered format and English OCR."""

    if ocr_language != "en":
        raise ValueError("Only English OCR is supported")

    pdf_options = PdfPipelineOptions(
        document_timeout=timeout_seconds,
        do_ocr=True,
        ocr_options=RapidOcrOptions(
            lang=[ocr_language],
            backend="onnxruntime",
            mode=OcrMode.DEFAULT,
        ),
    )
    image_options = PdfPipelineOptions(
        document_timeout=timeout_seconds,
        do_ocr=True,
        ocr_options=RapidOcrOptions(
            lang=[ocr_language],
            backend="onnxruntime",
            mode=OcrMode.FULL_PAGE,
        ),
    )

    return DocumentConverter(
        allowed_formats=list(InputFormat),
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
            InputFormat.IMAGE: ImageFormatOption(pipeline_options=image_options),
        },
    )
