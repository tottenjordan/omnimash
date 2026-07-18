from fastapi import FastAPI
from pydantic import BaseModel
from omnimash.agent.orchestrator import OmniMashAgent


class GenerateRequest(BaseModel):
    user_id: str
    project_id: str
    prompt: str
    clip_index: int = 0
    parent_turn_id: str | None = None


def create_app(mock_mode: bool = True) -> FastAPI:
    app = FastAPI(title="OmniMash API", version="0.1.0")
    agent = OmniMashAgent(mock_mode=mock_mode)

    @app.post("/api/generate")
    def generate_video(req: GenerateRequest):
        res = agent.process_user_turn(
            user_id=req.user_id,
            project_id=req.project_id,
            prompt=req.prompt,
            clip_index=req.clip_index,
            parent_turn_id=req.parent_turn_id,
        )
        return {
            "success": res.success,
            "status": res.status_event,
            "video_url": res.video_url,
            "turn_id": res.turn_id,
            "error": res.error_message,
        }

    return app
