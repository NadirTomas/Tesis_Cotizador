from fastapi import APIRouter


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", response_model=dict)
def health_check():
    return {"status": "ok"}
