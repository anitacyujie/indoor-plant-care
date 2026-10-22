"""POST /products/draft: read a label photo with Claude and return a draft.

Nothing is saved: the user checks the draft, fixes what the problems list,
and saves it with POST /products. The photo is only held for the request.
"""

from dataclasses import asdict
from typing import Annotated

import anthropic
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.label_reading.drafts import draft_from_extraction
from app.label_reading.reader import (
    MAX_IMAGE_BYTES,
    LabelReaderUnavailable,
    LabelReadFailed,
    LabelRefused,
    get_anthropic_client,
    image_media_type,
    read_label,
)
from app.label_reading.schemas import LabelCallRead, LabelDraftResponse

router = APIRouter(prefix="/products", tags=["products"])

ClientDep = Annotated[anthropic.Anthropic, Depends(get_anthropic_client)]


@router.post("/draft")
def draft_from_photo(photo: UploadFile, client: ClientDep) -> LabelDraftResponse:
    # Read one byte past the limit, so an oversized upload is caught without
    # reading all of it.
    data = photo.file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"The photo is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB",
        )
    # Checked before calling the model, so a wrong file costs nothing.
    media_type = image_media_type(data)
    if media_type is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "The photo must be JPEG, PNG, GIF, or WebP"
        )

    try:
        reading = read_label(client, data, media_type)
    except LabelRefused as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "This photo could not be read; try another") from error
    except LabelReadFailed as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The model did not return a usable reading") from error
    except LabelReaderUnavailable as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Label reading is unavailable; try again later") from error

    draft = draft_from_extraction(reading.extraction)
    return LabelDraftResponse(
        extraction=draft.extraction,
        product=draft.product,
        problems=draft.problems,
        call=LabelCallRead(**asdict(reading.call)),
    )
