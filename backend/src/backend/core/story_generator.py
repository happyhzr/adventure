from sqlalchemy.orm import Session
from langchain_deepseek import ChatDeepSeek
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from dotenv import load_dotenv

from backend.core.config import settings
from backend.core.prompts import STORY_PROMPT
from backend.models.story import Story, StoryNode
from backend.core.models import StoryLLMResponse, StoryNodeLLM

load_dotenv()


class StoryGenerator:
    @classmethod
    def _get_llm(cls):
        return ChatDeepSeek(
            model=settings.DEEPSEEK_MODEL, api_key=settings.DEEPSEEK_API_KEY
        )

    @classmethod
    def generate_story(
        cls, db: Session, session_id: str, theme: str = "fantasy"
    ) -> Story:
        llm = cls._get_llm()
        story_parser = PydanticOutputParser(pydantic_object=StoryLLMResponse)
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", STORY_PROMPT),
                ("human", f"Create the story with this theme: {theme}"),
            ]
        ).partial(format_instructions=story_parser.get_format_instructions())
        raw_response = llm.invoke(prompt.invoke({}))
        response_text = raw_response
        if hasattr(raw_response, "content"):
            response_text = raw_response.content
        story_structure = story_parser.parse(str(response_text))
        story_db = Story(title=story_structure.title, session_id=session_id)
        db.add(story_db)
        db.flush()
        root_node_data = story_structure.rootNode
        if isinstance(root_node_data, dict):
            root_node_data = StoryNodeLLM.model_validate(root_node_data)
        cls._process_story_node(db, story_db.id, root_node_data, is_root=True)
        db.commit()
        return story_db

    @classmethod
    def _process_story_node(
        cls, db: Session, story_id: int, node_data: StoryNodeLLM, is_root: bool = False
    ) -> StoryNode:
        node = StoryNode(
            story_id=story_id,
            content=(
                node_data.content
                if hasattr(node_data, "content")
                else dict(node_data)["content"]
            ),
            is_root=is_root,
            is_ending=(
                node_data.isEnding
                if hasattr(node_data, "isEnding")
                else dict(node_data)["isEnding"]
            ),
            is_winning_ending=(
                node_data.isWinningEnding
                if hasattr(node_data, "isWinningEnding")
                else dict(node_data)["isWinningEnding"]
            ),
            options=[],
        )
        db.add(node)
        db.flush()
        if not bool(node.is_ending) and (
            hasattr(node_data, "options") and node_data.options
        ):
            options_list = []
            for option_data in node_data.options:
                next_node = option_data.nextNode
                if isinstance(next_node, dict):
                    next_node = StoryNodeLLM.model_validate(next_node)
                child_node = cls._process_story_node(db, story_id, next_node, False)
                options_list.append(
                    {"text": option_data.text, "node_id": child_node.id}
                )
            node.options = options_list
        db.flush()
        return node
