import httpx
import json
import logging

logger = logging.getLogger(__name__)

class UnifiedCrocoTranslator:
    def __init__(self, model_name: str, endpoint: str):
        self.model_name = model_name
        self.endpoint = endpoint

    def translate(self, video: bytes) -> str:
        files = {"video": ("video.mp4", video, "video/mp4")}
        payload = {
            "name": self.model_name
        }
        response = httpx.Client(timeout=600).post(self.endpoint, files=files, data=payload)

        body = json.loads(response.read())

        if response.status_code != 200:
            raise RuntimeError(f"Translator returned {response.status_code}: {body}")

        return body['text']