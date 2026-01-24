# 03-03 Summary: Document Classifier & Confidence Scoring

**Completed:** 2026-01-24
**Duration:** ~10 minutes
**Status:** ✅ Complete

## Objective

Create document classifier and confidence scoring for extraction reliability.

## Deliverables

### 1. Document Classifier (`src/documents/classifier.py`)

- **ClassificationResult** model with `document_type`, `confidence` (0.0-1.0), and `reasoning`
- **classify_document()** async function using Claude Vision API via instructor
- Model: `claude-sonnet-4-5-20250514` (fast for classification)
- Supports image types: JPEG, PNG, GIF, WebP
- Classification prompt describes distinguishing features of W-2, 1099-INT, 1099-DIV, 1099-NEC
- **Mock mode** via `MOCK_LLM=true` environment variable for testing without API key

### 2. Confidence Scoring (`src/documents/confidence.py`)

- **ConfidenceResult** dataclass with `level`, `score`, `factors`, `notes`
- **calculate_confidence()** function with weighted factor scoring:
  - LLM self-reported confidence: 30%
  - Field validation pass rate: 40%
  - Critical field presence: 30%
- **Thresholds:**
  - HIGH: score >= 0.85 AND all critical fields present
  - MEDIUM: score >= 0.60
  - LOW: score < 0.60
- **CRITICAL_FIELDS** constant per document type
- **get_critical_fields()** helper function

### 3. Test Coverage

| Test File | Tests | Coverage |
|-----------|-------|----------|
| test_classifier.py | 26 | ClassificationResult, mock mode, prompt content |
| test_confidence.py | 39 | ConfidenceResult, factor weights, level thresholds |
| **Total** | **65** | All passing |

## Commits

1. `feat(03-03): create document classifier with Claude Vision`
2. `feat(03-03): create confidence scoring module`
3. `test(03-03): add classifier and confidence unit tests`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Mock mode via MOCK_LLM env var | Enable testing without Anthropic API key |
| Weights 0.3/0.4/0.3 | Field validation is most objective measure |
| HIGH requires all critical fields | Missing critical data should never be auto-approved |
| Deterministic mock based on byte length | Consistent test results |

## Dependencies Added

None (uses existing anthropic, instructor from 03-01)

## API Exports

```python
from src.documents import (
    # Classifier
    ClassificationResult,
    classify_document,
    # Confidence
    CRITICAL_FIELDS,
    ConfidenceResult,
    calculate_confidence,
    get_critical_fields,
)
```

## Verification

```bash
# Classifier works in mock mode
MOCK_LLM=true uv run python -c "
import asyncio
from src.documents import classify_document
asyncio.run(classify_document(b'test', 'image/jpeg'))
print('Classifier OK')
"

# Confidence scoring works
uv run python -c "from src.documents import calculate_confidence, ConfidenceLevel; print('Confidence OK')"

# All tests pass
uv run pytest tests/documents/test_classifier.py tests/documents/test_confidence.py -v
# 65 passed
```

## Next Plan

03-04: Worksheet Generator - Create Excel worksheets for Drake data entry.
