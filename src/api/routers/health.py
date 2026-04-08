from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz", tags=["infra"])
async def healthz():
    return {"status": "ok"}
