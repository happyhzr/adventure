import json
import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.story_generator import StoryGenerator
from backend.db.database import Base, get_db
from backend.models.job import StoryJob
from backend.models.story import Story, StoryNode
from backend.routers.story import generate_story_task, router


def ending(content, winning):
    return {
        "content": content,
        "isEnding": True,
        "isWinningEnding": winning,
        "options": [],
    }


STORY_RESPONSE = {
    "title": "Forest adventure",
    "rootNode": {
        "content": "Choose a path",
        "isEnding": False,
        "isWinningEnding": False,
        "options": [
            {"text": "Left", "nextNode": ending("Treasure", True)},
            {
                "text": "Right",
                "nextNode": {
                    "content": "A bridge",
                    "isEnding": False,
                    "isWinningEnding": False,
                    "options": [
                        {"text": "Cross", "nextNode": ending("Lost", False)}
                    ],
                },
            },
        ],
    },
}


class StoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.db = self.sessions()
        app = FastAPI()
        app.include_router(router, prefix="/api")

        def database():
            with self.sessions() as db:
                yield db

        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_generated_story_complete_response(self):
        llm = MagicMock()
        llm.invoke.return_value = AIMessage(content=json.dumps(STORY_RESPONSE))
        with patch.object(StoryGenerator, "_get_llm", return_value=llm):
            story = StoryGenerator.generate_story(self.db, "session", "forest")
        response = self.client.get(f"/api/stories/{story.id}/complete")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["title"], "Forest adventure")
        self.assertEqual(data["session_id"], "session")
        self.assertEqual(len(data["all_nodes"]), 4)
        root = data["root_node"]
        self.assertEqual(root["content"], "Choose a path")
        self.assertEqual(root, data["all_nodes"][str(root["id"])])
        left, right = [
            data["all_nodes"][str(option["node_id"])]
            for option in root["options"]
        ]
        self.assertTrue(left["is_ending"])
        self.assertTrue(left["is_winning_ending"])
        self.assertEqual(left["options"], [])
        self.assertFalse(right["is_ending"])
        losing = data["all_nodes"][str(right["options"][0]["node_id"])]
        self.assertTrue(losing["is_ending"])
        self.assertFalse(losing["is_winning_ending"])
        self.assertEqual(self.db.query(StoryNode).filter_by(is_root=True).count(), 1)

    def test_missing_story(self):
        response = self.client.get("/api/stories/999/complete")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Story not found")

    def test_invalid_root_count(self):
        story = Story(title="Old story", session_id="session")
        self.db.add(story)
        self.db.commit()
        response = self.client.get(f"/api/stories/{story.id}/complete")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "Story has no root node")
        for _ in range(2):
            self.db.add(StoryNode(story_id=story.id, content="Root", is_root=True))
        self.db.commit()
        response = self.client.get(f"/api/stories/{story.id}/complete")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "Story has multiple root nodes")

    def run_failed_job(self, content, processor=None):
        self.db.add(StoryJob(job_id="job", session_id="session", theme="forest", status="pending"))
        self.db.commit()
        llm = MagicMock()
        llm.invoke.return_value = AIMessage(content=content)
        with patch("backend.routers.story.SessionLocal", self.sessions), patch.object(
            StoryGenerator, "_get_llm", return_value=llm
        ):
            if processor:
                with patch.object(StoryGenerator, "_process_story_node", side_effect=processor):
                    generate_story_task("job", "forest", "session")
            else:
                generate_story_task("job", "forest", "session")
        self.db.expire_all()
        job = self.db.query(StoryJob).filter_by(job_id="job").one()
        self.assertEqual(job.status, "failed")
        self.assertIsNotNone(job.completed_at)
        self.assertTrue(job.error)
        self.assertIsNone(job.story_id)
        self.assertEqual(self.db.query(Story).count(), 0)
        self.assertEqual(self.db.query(StoryNode).count(), 0)

    def test_malformed_output_marks_job_failed(self):
        self.run_failed_job('{"title": "Bad", "rootNode": "not a node"}')

    def test_persistence_failure_rolls_back_before_marking_job_failed(self):
        def fail(db, story_id, node_data, is_root=False):
            db.add_all([
                StoryNode(id=1, story_id=story_id, content="First"),
                StoryNode(id=1, story_id=story_id, content="Duplicate"),
            ])
            db.flush()

        self.run_failed_job(json.dumps(STORY_RESPONSE), processor=fail)


if __name__ == "__main__":
    unittest.main()
