# OCR Strategy Pattern Implementation Plan

## Overview

Implement a strategy pattern for OCR providers to allow switching between EasyOCR and PaddleOCR depending on the deployment environment. PaddleOCR provides better accuracy but only runs well on AMD processors.

## Current State

- OCR is implemented in `apps/backend/app/services/ocr_service.py`
- Uses EasyOCR with lazy initialization and GPU detection
- Configuration in `apps/backend/app/config.py`

## Changes Required

### 1. Add Configuration Setting

In `apps/backend/app/config.py`, add a new setting:

```python
# OCR (Phase 2)
OCR_ENABLED: bool = False
OCR_PROVIDER: str = "easyocr"  # "easyocr" or "paddleocr"
OCR_LANGUAGES: List[str] = ["en"]
OCR_USE_GPU: bool = False
```

### 2. Create OCR Engine Interface

Create `apps/backend/app/services/ocr/base.py`:

```python
from abc import ABC, abstractmethod
from typing import List, Optional

class OCREngine(ABC):
    """Abstract base class for OCR engines."""

    @abstractmethod
    def initialize(self, languages: List[str], use_gpu: bool) -> None:
        """Initialize the OCR engine."""
        pass

    @abstractmethod
    def extract_text(self, image_path: str) -> Optional[str]:
        """Extract text from an image file."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return engine name for logging."""
        pass
```

### 3. Create Concrete Implementations

#### EasyOCR Engine (`apps/backend/app/services/ocr/easyocr_engine.py`)

Move the current EasyOCR logic from `ocr_service.py` into this class:

```python
import logging
from typing import List, Optional

from .base import OCREngine

logger = logging.getLogger(__name__)


class EasyOCREngine(OCREngine):
    """EasyOCR implementation - works well on ARM64 and general CPU."""

    def __init__(self):
        self._engine = None

    @property
    def name(self) -> str:
        return "EasyOCR"

    def initialize(self, languages: List[str], use_gpu: bool) -> None:
        """Initialize EasyOCR engine."""
        import easyocr

        # Auto-detect GPU availability if use_gpu is True
        actual_use_gpu = use_gpu
        if use_gpu:
            try:
                import torch
                if not torch.cuda.is_available():
                    logger.warning("GPU requested but CUDA not available, falling back to CPU")
                    actual_use_gpu = False
                else:
                    logger.info(f"GPU detected: {torch.cuda.get_device_name(0)}")
            except ImportError:
                logger.warning("PyTorch not available for GPU detection, falling back to CPU")
                actual_use_gpu = False

        # EasyOCR supports multiple languages
        lang_list = list(languages)

        self._engine = easyocr.Reader(
            lang_list=lang_list,
            gpu=actual_use_gpu
        )
        logger.info(f"EasyOCR engine initialized with languages: {lang_list}, GPU: {actual_use_gpu}")

    def extract_text(self, image_path: str) -> Optional[str]:
        """Extract text from image using EasyOCR."""
        if self._engine is None:
            logger.error("EasyOCR engine not initialized")
            return None

        # EasyOCR returns: [([bbox], text, confidence), ...]
        result = self._engine.readtext(image_path)

        if not result:
            return ""

        # Extract text from OCR results
        text_lines = []
        for detection in result:
            if len(detection) >= 3:
                bbox, text, confidence = detection
                if confidence > 0.5:  # Only include confident results
                    text_lines.append(text)

        return "\n".join(text_lines)
```

#### PaddleOCR Engine (`apps/backend/app/services/ocr/paddleocr_engine.py`)

```python
import logging
from typing import List, Optional

from .base import OCREngine

logger = logging.getLogger(__name__)


class PaddleOCREngine(OCREngine):
    """PaddleOCR implementation - better accuracy, works well on AMD processors."""

    def __init__(self):
        self._engine = None

    @property
    def name(self) -> str:
        return "PaddleOCR"

    def initialize(self, languages: List[str], use_gpu: bool) -> None:
        """Initialize PaddleOCR engine."""
        from paddleocr import PaddleOCR

        # PaddleOCR uses single language string, not list
        # Map common language codes
        lang_map = {
            "en": "en",
            "ch": "ch",
            "chinese": "ch",
            "de": "german",
            "german": "german",
            "fr": "french",
            "french": "french",
            "ja": "japan",
            "japanese": "japan",
            "ko": "korean",
            "korean": "korean",
        }

        lang = languages[0] if languages else "en"
        paddle_lang = lang_map.get(lang.lower(), lang)

        self._engine = PaddleOCR(
            use_angle_cls=True,
            lang=paddle_lang,
            use_gpu=use_gpu,
            show_log=False  # Suppress verbose logging
        )
        logger.info(f"PaddleOCR engine initialized with language: {paddle_lang}, GPU: {use_gpu}")

    def extract_text(self, image_path: str) -> Optional[str]:
        """Extract text from image using PaddleOCR."""
        if self._engine is None:
            logger.error("PaddleOCR engine not initialized")
            return None

        # PaddleOCR returns nested structure: [[[box, (text, conf)], ...]]
        result = self._engine.ocr(image_path, cls=True)

        if not result:
            return ""

        text_lines = []
        for page in result:
            if page:
                for line in page:
                    if len(line) >= 2:
                        text, confidence = line[1]
                        if confidence > 0.5:  # Only include confident results
                            text_lines.append(text)

        return "\n".join(text_lines)
```

### 4. Create Factory Function

Create `apps/backend/app/services/ocr/__init__.py`:

```python
"""OCR engine factory and exports."""
import logging
from typing import Optional

from app.config import settings
from .base import OCREngine

logger = logging.getLogger(__name__)


def create_ocr_engine() -> Optional[OCREngine]:
    """
    Factory to create the configured OCR engine.

    Returns:
        OCREngine instance or None if creation fails
    """
    provider = settings.OCR_PROVIDER.lower()

    if provider == "paddleocr":
        try:
            from .paddleocr_engine import PaddleOCREngine
            logger.info("Creating PaddleOCR engine")
            return PaddleOCREngine()
        except ImportError:
            logger.warning(
                "PaddleOCR not installed. Install with: pip install paddlepaddle paddleocr"
            )
            return None
    else:
        # Default to EasyOCR
        try:
            from .easyocr_engine import EasyOCREngine
            logger.info("Creating EasyOCR engine")
            return EasyOCREngine()
        except ImportError:
            logger.warning(
                "EasyOCR not installed. Install with: pip install easyocr"
            )
            return None


__all__ = ["OCREngine", "create_ocr_engine"]
```

### 5. Update OCRService

Modify `apps/backend/app/services/ocr_service.py` to use the factory:

```python
"""OCR service for extracting text from documents."""
import logging
from pathlib import Path
from typing import Optional

from app.config import settings
from app.services.ocr import create_ocr_engine

logger = logging.getLogger(__name__)


class OCRService:
    """Service for OCR text extraction."""

    def __init__(self):
        """Initialize OCR service."""
        self.enabled = settings.OCR_ENABLED
        self.languages = settings.OCR_LANGUAGES
        self.use_gpu = settings.OCR_USE_GPU
        self._ocr_engine = None

    def _initialize_engine(self):
        """Lazy initialize OCR engine."""
        if not self.enabled:
            return

        if self._ocr_engine is None:
            try:
                self._ocr_engine = create_ocr_engine()
                if self._ocr_engine:
                    self._ocr_engine.initialize(self.languages, self.use_gpu)
                    logger.info(f"{self._ocr_engine.name} engine initialized successfully")
                else:
                    logger.error("Failed to create OCR engine")
                    self.enabled = False
            except Exception as e:
                logger.error(f"Failed to initialize OCR engine: {e}")
                self.enabled = False

    # ... rest of the methods remain the same, but replace
    # self._ocr_engine.readtext() calls with self._ocr_engine.extract_text()
```

### 6. Update Dependencies

In `apps/backend/requirements.txt`:

```
# OCR - choose one or both based on deployment
easyocr>=1.7.0

# For PaddleOCR support (better on AMD):
# paddlepaddle>=2.5.0        # CPU version
# paddlepaddle-gpu>=2.5.0    # GPU version (CUDA)
# paddleocr>=2.7.0
```

Or create optional dependency groups in `pyproject.toml`:

```toml
[project.optional-dependencies]
ocr-easyocr = ["easyocr>=1.7.0"]
ocr-paddle = ["paddlepaddle>=2.5.0", "paddleocr>=2.7.0"]
ocr-paddle-gpu = ["paddlepaddle-gpu>=2.5.0", "paddleocr>=2.7.0"]
```

## File Structure After Implementation

```
apps/backend/app/services/
├── ocr/
│   ├── __init__.py          # Factory function and exports
│   ├── base.py              # Abstract OCREngine class
│   ├── easyocr_engine.py    # EasyOCR implementation
│   └── paddleocr_engine.py  # PaddleOCR implementation
└── ocr_service.py           # Main service (uses factory)
```

## Configuration Examples

### For ARM/Apple Silicon (use EasyOCR):
```bash
OCR_ENABLED=true
OCR_PROVIDER=easyocr
OCR_LANGUAGES=["en"]
OCR_USE_GPU=false
```

### For AMD/x86 with better accuracy (use PaddleOCR):
```bash
OCR_ENABLED=true
OCR_PROVIDER=paddleocr
OCR_LANGUAGES=["en"]
OCR_USE_GPU=true  # If AMD GPU with ROCm support
```

## Key Considerations

1. **Language mapping differs**: EasyOCR uses `["en"]` list, PaddleOCR uses `"en"` single string with different codes
2. **Output format differs**: Each engine returns results in different structures - normalized in the engine implementations
3. **GPU detection**: PaddleOCR has different GPU requirements (PaddlePaddle vs PyTorch/CUDA)
4. **Dependencies are large**: Both libraries are substantial - consider making them optional with graceful fallback
5. **Testing**: Need to test both engines produce consistent output format

## Implementation Order

1. Create the `ocr/` directory and `base.py` with the abstract class
2. Create `easyocr_engine.py` by extracting logic from current `ocr_service.py`
3. Create `paddleocr_engine.py` with PaddleOCR implementation
4. Create `__init__.py` with factory function
5. Update `config.py` to add `OCR_PROVIDER` setting
6. Update `ocr_service.py` to use the factory
7. Update requirements/dependencies
8. Test both engines

## Notes

- PaddleOCR generally provides better accuracy for complex documents
- EasyOCR is more portable and works well on ARM64 (Apple Silicon, Raspberry Pi)
- Both support multiple languages but with different language codes
- Consider adding a fallback mechanism if the preferred engine fails to initialize
