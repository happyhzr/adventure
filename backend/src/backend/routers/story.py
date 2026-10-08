import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Cookie, Response, BackgroundTasks
from sqlalchemy.orm import Session

from backend.db.database import get_db, SessionLocal
from backend.models.story import Story, StoryNode
from backend.models.job import StoryJob
from backend.schemas.story import (
    CompleteStoryResponse,
    CompleteStoryNodeResponse,
    CreateStoryRequest,
)
from backend.schemas.job import StoryJobResponse
from backend.core.story_generator import StoryGenerator

router = APIRouter(prefix="/stories", tags=["stories"])


def get_session_id(session_id: str | None = Cookie(None)):
    if not session_id:
        session_id = str(uuid.uuid4())
    return session_id


@router.post("/create", response_model=StoryJobResponse)
def create_story(
    request: CreateStoryRequest,
    background_tasks: BackgroundTasks,
    response: Response,
    session_id: str = Depends(get_session_id),
    db: Session = Depends(get_db),
):
    response.set_cookie(key="session_id", value=session_id, httponly=True)

    job_id = str(uuid.uuid4())

    job = StoryJob(
        job_id=job_id, session_id=session_id, theme=request.theme, status="pending"
    )
    db.add(job)
    db.commit()
    background_tasks.add_task(
        generate_story_task, job_id=job_id, theme=request.theme, session_id=session_id
    )
    return job


def generate_story_task(job_id: str, theme: str, session_id: str):
    db = SessionLocal()

    try:
        job = db.query(StoryJob).filter(StoryJob.job_id == job_id).first()
        if not job:
            return
        try:
            job.status = "processing"
            db.commit()
            story = StoryGenerator.generate_story(db, session_id, theme)
            job.story_id = story.id
            job.status = "completed"
            job.completed_at = datetime.now()
            db.commit()
        except Exception as e:
            db.rollback()
            job.status = "failed"
            job.completed_at = datetime.now()
            job.error = str(e)
            db.commit()
    finally:
        db.close()


@router.get("/{story_id}/complete", response_model=CompleteStoryResponse)
def get_complete_story(story_id: int, db: Session = Depends(get_db)):
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return build_complete_story_tree(db, story)


def build_complete_story_tree(db: Session, story: Story) -> CompleteStoryResponse:
    nodes = db.query(StoryNode).filter(StoryNode.story_id == story.id).all()
    roots = [node for node in nodes if node.is_root]
    if not roots:
        raise HTTPException(status_code=409, detail="Story has no root node")
    if len(roots) > 1:
        raise HTTPException(status_code=409, detail="Story has multiple root nodes")
    all_nodes = {
        node.id: CompleteStoryNodeResponse.model_validate(node) for node in nodes
    }
    return CompleteStoryResponse(
        id=story.id,
        title=story.title,
        session_id=story.session_id,
        created_at=story.created_at,
        root_node=all_nodes[roots[0].id],
        all_nodes=all_nodes,
    )
