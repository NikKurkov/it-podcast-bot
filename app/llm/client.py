import httpx
from openai import OpenAI

from app.config.settings import settings


def create_llm_client() -> OpenAI:
    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        http_client=httpx.Client(trust_env=False),
    )
