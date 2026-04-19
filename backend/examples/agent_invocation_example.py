"""
Example invocations for Apparel Intelligence agents (async).

Run from `backend/` with venv activated:

    PYTHONPATH=. python examples/agent_invocation_example.py

Requires GEMINI_API_KEY in `.env` for live runs; otherwise prints a notice.
"""

from __future__ import annotations

import asyncio


async def main() -> None:
    from app.config import get_settings
    from app.agents.orchestrator import (
        analyze_purchase_with_optional_agent,
        generate_script_with_optional_agent,
        ingest_garment_with_optional_agent,
        recommend_outfit_with_optional_agent,
    )
    from app.schemas.wardrobe import GarmentRecord
    from app.services.embeddings import deterministic_embedding
    from app.services.store import get_store

    settings = get_settings()
    print("live_llm:", settings.has_live_llm)

    ingest = await ingest_garment_with_optional_agent(
        filename="navy_wool_coat.jpg",
        image_path="uploads/navy_wool_coat.jpg",
        hints="wool, winter",
    )
    print("ingest:", ingest.garment.id, ingest.garment.category, "used_live_agent=", ingest.used_live_agent)
    get_store().upsert(ingest.garment)

    demo_top = GarmentRecord(
        id="demo-top",
        category="top",
        color="white",
        formality_score=0.4,
        season="all-season",
        tags=["cotton"],
        image_path="uploads/white_shirt.png",
        embedding=deterministic_embedding(("demo-top", "top", "white")),
    )
    demo_bottom = GarmentRecord(
        id="demo-bottom",
        category="bottom",
        color="navy",
        formality_score=0.45,
        season="all-season",
        tags=["denim"],
        image_path="uploads/navy_chinos.png",
        embedding=deterministic_embedding(("demo-bottom", "bottom", "navy")),
    )
    for g in (demo_top, demo_bottom):
        get_store().upsert(g)

    rec = await recommend_outfit_with_optional_agent(
        occasion="work_presentation",
        weather="mild_clear",
        vibe="quiet_luxury",
        wardrobe=[ingest.garment, demo_top, demo_bottom],
        user_preference="no loud logos",
    )
    print("recommend confidence:", rec.confidence, "used_live_agent=", rec.used_live_agent)

    purchase = await analyze_purchase_with_optional_agent(
        candidate=GarmentRecord(
            id="candidate",
            category="shoes",
            color="brown",
            formality_score=0.55,
            season="all-season",
            tags=["leather"],
            image_path="uploads/loafers.png",
            embedding=deterministic_embedding(("candidate", "shoes", "brown")),
        ),
        wardrobe=[ingest.garment, demo_top, demo_bottom],
    )
    print("purchase:", purchase.recommendation, purchase.compatibility_score)

    script = await generate_script_with_optional_agent(
        platform="linkedin",
        outfit_summary="navy coat, white shirt, navy chinos, brown loafers",
        user_voice="warm, precise",
    )
    print("script used_live_agent=", script.used_live_agent)
    print(script.script[:180], "...")


if __name__ == "__main__":
    asyncio.run(main())
