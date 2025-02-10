import frappe
import openai
from functools import lru_cache

class AIClient:
    _instance = None
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            settings = frappe.get_single("JJ Chatbot Settings")
            self.client = openai.OpenAI(
                api_key=settings.get_password("ai_api_token"),
                base_url=settings.ai_api_endpoint if settings.ai_api_endpoint else "https://api.openai.com/v1"
            )
            self.chat_model = settings.ai_model or "gpt-3.5-turbo"
            self.embedding_model = settings.ai_embedding_model or "text-embedding-ada-002"
            
            # ใช้ system instruction จาก settings ถ้ามี
            self.default_system_prompt = settings.ai_system_instruction or """คุณเป็นผู้ช่วย AI ที่เป็นมิตรและมีความรู้เกี่ยวกับสินค้าและบริการ

คำแนะนำในการตอบ:
1. ตอบด้วยความสุภาพและเป็นมิตร
2. ถ้าเป็นคำทักทายหรือคำขอบคุณ ให้ตอบรับอย่างเหมาะสม
3. ถ้าไม่มีข้อมูลเฉพาะเจาะจง ให้ตอบแบบทั่วไปและเสนอให้ถามคำถามเพิ่มเติม
4. พยายามเข้าใจความต้องการของผู้ใช้แม้คำถามจะไม่ชัดเจน"""
            
            self.initialized = True
            
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def get_embedding(self, text: str) -> list:
        """สร้าง embedding vector"""
        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=text,
            encoding_format="float"
        )
        return response.data[0].embedding
    
    def get_conversation_history(self, session_id: str, limit: int = None) -> list:
        """ดึงประวัติการสนทนาตาม session_id"""
       
        history = frappe.get_all(
            "JJ Chat History",
            filters={
                "session_id": session_id,
                "ai_response": ["is", "set"]
            },
            fields=["user_message", "ai_response", "creation"],
            order_by="creation desc"
        )
        
        history.reverse()
        messages = []
        for h in history:
            messages.append({"role": "user", "content": h.user_message})
            messages.append({"role": "assistant", "content": h.ai_response})
        return messages
    
    def chat_completion(self, messages: list, session_id: str = None, **kwargs) -> tuple:
        """สร้าง chat completion และส่งคืนทั้งข้อความและ token usage"""
        conversation_messages = []
        conversation_messages.append({
            "role": "system",
            "content": self.default_system_prompt
        })
        
        if session_id:
            history_messages = self.get_conversation_history(session_id)
            conversation_messages.extend(history_messages)
        
        conversation_messages.extend(messages)
        
        # ตั้งค่า default parameters ถ้าไม่ได้ระบุ
        if 'temperature' not in kwargs:
            kwargs['temperature'] = 0.7  # เพิ่มความยืดหยุ่นในการตอบ
        
        if 'max_tokens' not in kwargs:
            kwargs['max_tokens'] = 300  # จำกัดความยาวคำตอบ
        
        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=conversation_messages,
            **kwargs
        )
        
        # ส่งคืนทั้งข้อความและ token usage
        return {
            "content": response.choices[0].message.content,
            "usage": {
                "total_tokens": response.usage.total_tokens,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens
            }
        } 