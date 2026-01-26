# OCR Implementation - Ollama Vision

> **Note**: This document describes the current OCR implementation using Ollama vision models.
> The previous strategy pattern with PaddleOCR/EasyOCR has been removed in favor of LLM-based OCR.

## Overview

Cartulary uses Ollama's vision-capable models for OCR (Optical Character Recognition). This approach provides:

- **Better accuracy**: LLMs understand context and can handle complex layouts
- **Simpler architecture**: No need for multiple OCR engine implementations
- **Markdown output**: Extracted text is formatted as clean markdown
- **Flexibility**: Easy to switch between different vision models

## Current Implementation

### Architecture

```
Document Upload → PDF/Image → Ollama Vision API → Extracted Text (Markdown)
```

### Key Files

- `apps/backend/app/services/ocr_service.py` - Main OCR service
- `apps/backend/app/config.py` - Configuration settings
- `apps/backend/app/tasks/document_tasks.py` - Celery task integration

### Configuration

```bash
# Enable OCR processing
OCR_ENABLED=true

# Ollama vision model for text extraction
VISION_OCR_MODEL=minicpm-v  # or llava, gemma3:4b-it-q4_K_M

# Ollama server URL (also used for embeddings)
LLM_BASE_URL=http://localhost:11434
```

### Supported Vision Models

| Model | Size | Speed | Accuracy | Notes |
|-------|------|-------|----------|-------|
| `minicpm-v` | ~3GB | Fast | Good | Recommended for most use cases |
| `llava` | ~4GB | Medium | Good | Good general-purpose model |
| `llava:13b` | ~8GB | Slow | Better | Higher accuracy, more resources |
| `gemma3:4b-it-q4_K_M` | ~3GB | Fast | Good | Good for structured documents |

### How It Works

1. **PDF Processing**:
   - PDF pages are converted to images using PyMuPDF
   - Each page is rendered at 300 DPI for quality
   - Images are saved as temporary PNG files

2. **Image Processing**:
   - Images are base64-encoded
   - Sent to Ollama vision API with extraction prompt
   - Response is clean markdown text

3. **Text Extraction Prompt**:
   ```
   Perform Optical Character Recognition (OCR) on the following image data.
   Process all the text on the entire image, exactly as it's written.
   The output should be the extracted text formatted in Markdown,
   preserving structure where possible.
   Do not add any commentary or explanation of the text, just the text itself.
   ```

## Code Structure

### OCRService Class

```python
class OCRService:
    def __init__(self):
        self.enabled = settings.OCR_ENABLED
        self.model = settings.VISION_OCR_MODEL
        self._ollama_client = None

    def _extract_text_from_image(self, image_path: str) -> Optional[str]:
        """Extract text from image using Ollama vision API."""
        # Base64 encode image
        # Send to Ollama chat API with vision model
        # Return extracted text

    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF, using vision OCR for scanned pages."""
        # Convert each page to image
        # Extract text from each page
        # Combine results

    def extract_text(self, file_path: str) -> str:
        """Main entry point for text extraction."""
        # Determine file type
        # Route to appropriate extraction method
```

## Migration from Previous Implementation

The previous implementation used a strategy pattern with PaddleOCR and EasyOCR:

### Removed Files
- `apps/backend/app/services/ocr/` directory (entire strategy pattern)
- `apps/backend/Dockerfile.paddleocr`

### Removed Dependencies
- `paddlepaddle`
- `paddleocr`
- `easyocr`

### Removed Configuration
- `OCR_PROVIDER` (was: `auto`, `paddleocr`, `easyocr`)
- `OCR_LANGUAGES` (was: `["en"]`)
- `OCR_USE_GPU` (was: `true`/`false`)

### New Configuration
- `VISION_OCR_MODEL` - Ollama vision model name
- Uses existing `LLM_BASE_URL` for Ollama connection

## Benefits of Ollama Vision OCR

1. **Simplified Dependencies**: No need for large OCR libraries
2. **Better Context Understanding**: LLMs understand document structure
3. **Markdown Output**: Clean, structured output format
4. **Easy Model Switching**: Just change the model name
5. **Unified Infrastructure**: Same Ollama instance for OCR, embeddings, and LLM

## Limitations

1. **Requires Ollama**: External dependency that must be running
2. **Network Latency**: API calls vs local processing
3. **Resource Usage**: Vision models need significant RAM/VRAM
4. **Rate Limiting**: May need to throttle for large batch processing

## Troubleshooting

### OCR Returns Empty Text

1. Check Ollama is running: `curl http://localhost:11434/api/tags`
2. Verify vision model is pulled: `ollama pull minicpm-v`
3. Check Celery worker logs for errors
4. Verify `LLM_BASE_URL` is accessible from Docker containers

### OCR is Slow

1. Use a faster model (minicpm-v vs llava:13b)
2. Ensure Ollama has adequate resources
3. Consider GPU acceleration for Ollama
4. Increase Celery worker concurrency

### Incomplete Text Extraction

1. Check image quality (increase DPI if needed)
2. Try a different vision model
3. Check for truncation in Ollama response
4. Review the extraction prompt

## Future Improvements

Potential enhancements:

1. **Multi-provider Support**: Add OpenAI GPT-4V, Google Gemini Vision
2. **Batch Processing**: Process multiple pages in parallel
3. **Caching**: Cache OCR results for identical images
4. **Quality Detection**: Auto-detect if page needs OCR vs embedded text
5. **Language Detection**: Auto-detect document language

---

Last Updated: 2026-01-26
