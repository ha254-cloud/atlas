from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.documents.schemas import (
    DocumentClassificationReview,
    DocumentRead,
    DocumentUpdate,
)
from app.documents.service import (
    DocumentAIUnavailable,
    DocumentNotFound,
    DocumentService,
    DuplicateDocument,
)
from app.documents.storage import FileTooLarge, UnsupportedFileType, read_file
from app.models.document import DocumentType
from app.models.user import User
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(tags=["Documents"])


def _svc(db: Session, org: int) -> DocumentService:
    return DocumentService(db, org)


@router.post("/claims/{claim_id}/documents", response_model=DocumentRead)
async def upload_document(
    claim_id: int,
    file: UploadFile = File(...),
    document_type: DocumentType = Form(DocumentType.OTHER),
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.EDIT_CLAIMS)),
):
    """Upload a supporting document (operative report, imaging, referral,
    lab results, authorization) for a claim's Evidence Library."""
    try:
        return _svc(db, organization_id).upload(claim_id, file, document_type, current_user.id)
    except DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except DuplicateDocument as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except UnsupportedFileType as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc))


@router.get("/claims/{claim_id}/documents", response_model=list[DocumentRead])
def list_documents(
    claim_id: int,
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    try:
        return _svc(db, organization_id).list_for_claim(claim_id, search)
    except DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/documents/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    try:
        return _svc(db, organization_id).get(document_id)
    except DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/documents/{document_id}/download")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    try:
        document = _svc(db, organization_id).get(document_id)
    except DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    content = read_file(document.storage_path)
    return Response(
        content=content,
        media_type=document.content_type,
        headers={"Content-Disposition": f'inline; filename="{document.filename}"'},
    )


@router.patch("/documents/{document_id}", response_model=DocumentRead)
def update_document(
    document_id: int,
    payload: DocumentUpdate,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.EDIT_CLAIMS)),
):
    try:
        return _svc(db, organization_id).update(
            document_id,
            payload.document_type,
            payload.tags,
            current_user.id,
        )
    except DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.EDIT_CLAIMS)),
):
    try:
        _svc(db, organization_id).delete(document_id, current_user.id)
    except DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/documents/{document_id}/summarize", response_model=DocumentRead)
async def summarize_document(
    document_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    try:
        return await _svc(db, organization_id).summarize(document_id, current_user.id)
    except DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/documents/{document_id}/classify", response_model=DocumentRead)
async def classify_document(
    document_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.EDIT_CLAIMS)),
):
    try:
        return await _svc(db, organization_id).classify(document_id, current_user.id)
    except DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except DocumentAIUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post(
    "/documents/{document_id}/classification-review",
    response_model=DocumentRead,
)
def review_document_classification(
    document_id: int,
    payload: DocumentClassificationReview,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.EDIT_CLAIMS)),
):
    try:
        return _svc(db, organization_id).review_classification(
            document_id,
            payload.document_type,
            payload.reason,
            current_user.id,
        )
    except DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
