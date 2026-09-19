"""Local sentence-transformers adapter for the embedder port."""
import logging
from typing import Any, List, Sequence

from app.providers.ports import ModelError

logger = logging.getLogger(__name__)

# Small batches keep memory use down on CPU-only hosts.
ENCODE_BATCH_SIZE = 8


class LocalEmbedder:
    """Embedder running a sentence-transformers model in-process. The model loads on first use."""

    def __init__(self, model: str, dimension: int) -> None:
        self.model = model
        self._dimension = dimension
        self._transformer: Any = None

    def __repr__(self) -> str:
        return f"LocalEmbedder(model={self.model!r})"

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self.model

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Return one vector per text. Raises ModelError on any provider failure."""
        if not texts:
            return []
        try:
            vectors = self._get_transformer().encode(
                list(texts),
                convert_to_numpy=True,
                show_progress_bar=False,
                batch_size=ENCODE_BATCH_SIZE,
            )
            return vectors.tolist()
        except ModelError:
            raise
        except Exception as e:
            # The provider boundary: anything the library raises is a model failure.
            raise ModelError(f"Local embedding failed ({self!r}): {type(e).__name__}: {e}") from e

    def _get_transformer(self) -> Any:
        if self._transformer is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise ModelError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                ) from e
            logger.info(f"Loading local embedding model: {self.model}")
            self._transformer = SentenceTransformer(self.model)
        return self._transformer
