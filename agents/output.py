from pydantic import BaseModel
from neural.models import CapabilityManifest


class AgentAction(BaseModel):
    type: str
    parameters: dict = {}


class AgentOutput(BaseModel):
    action: AgentAction | None = None
    user_prompt_update: str | None = None

    def is_valid_for_manifest(self, manifest: CapabilityManifest) -> bool:
        if self.action is None:
            return True
        available = manifest.get_available_actions()
        return self.action.type in available

    @classmethod
    def parse_llm_response(cls, text: str) -> "AgentOutput | None":
        """
        Parse raw LLM text into AgentOutput.
        Extracts first JSON object from the response.
        Returns None if parsing fails (entity takes no action).
        """
        import json
        import re
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return cls.model_validate_json(match.group(0))
        except Exception:
            return None
