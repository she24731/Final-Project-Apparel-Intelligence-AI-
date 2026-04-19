from app.schemas.media import (
    GenerateScriptRequest,
    GenerateScriptResponse,
    GenerateVideoRequest,
    GenerateVideoResponse,
)
from app.schemas.purchase import AnalyzePurchaseRequest, PurchaseAnalysisResponse
from app.schemas.recommend import RecommendOutfitRequest, RecommendOutfitResponse
from app.schemas.wardrobe import GarmentRecord, IngestGarmentResponse

__all__ = [
    "GarmentRecord",
    "IngestGarmentResponse",
    "RecommendOutfitRequest",
    "RecommendOutfitResponse",
    "AnalyzePurchaseRequest",
    "PurchaseAnalysisResponse",
    "GenerateScriptRequest",
    "GenerateScriptResponse",
    "GenerateVideoRequest",
    "GenerateVideoResponse",
]
