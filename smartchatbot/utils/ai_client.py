import frappe
import openai
from functools import lru_cache

class AIClient:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            settings = frappe.get_single("JJ Chatbot Settings")
            self.client = openai.OpenAI(
                api_key=settings.get_password("ai_api_token"),
                base_url=settings.ai_api_endpoint if settings.ai_api_endpoint else "https://api.openai.com/v1"
            )
            self.chat_model = settings.ai_model or "gpt-3.5-turbo"
            self.embedding_model = settings.ai_embedding_model or "text-embedding-ada-002"
            self.initialized = True
    
    @classmethod
    def get_instance(cls):
        return cls()
    
    def get_embedding(self, text: str) -> list:
        """สร้าง embedding vector"""
        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=text,
            encoding_format="float"
        )
        return response.data[0].embedding
    
    def chat_completion(self, messages: list, **kwargs) -> str:
        """สร้าง chat completion"""
        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=messages,
            **kwargs
        )
        return response.choices[0].message.content 