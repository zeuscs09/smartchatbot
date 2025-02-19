import frappe
import openai
from functools import lru_cache

class AIClient:
    _instance = None
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            settings = frappe.get_single("JJ Chatbot Settings")
            
            # แยก client สำหรับ embedding เป็น OpenAI เสมอ
            self.embedding_client = openai.OpenAI(
                api_key=settings.get_password("ai_api_token"),
                base_url="https://api.openai.com/v1"
            )
            self.embedding_model = settings.ai_embedding_model or "text-embedding-ada-002"
            
            # เลือก provider สำหรับ chat
            self.ai_provider = settings.ai_provider or "Open Ai"
            
            # สร้าง chat client ตาม provider
            if self.ai_provider == "Open Ai":
                self.client = openai.OpenAI(
                    api_key=settings.get_password("ai_api_token"),
                    base_url="https://api.openai.com/v1"
                )
                self.chat_model = settings.ai_model or "gpt-3.5-turbo"
                
            elif self.ai_provider == "Typhoon":
                self.client = openai.OpenAI(
                    api_key=settings.get_password("typhoon_token"),
                    base_url="https://api.opentyphoon.ai/v1"
                )
                self.chat_model = settings.typhoon_model or "typhoon-v1.5x-70b-instruct"
                
            elif self.ai_provider == "Gemini":
                import google.generativeai as genai
                genai.configure(api_key=settings.get_password("gemini_token"))
                self.generation_config = {
                    "temperature": 1,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 8192,
                    "response_mime_type": "text/plain",
                }
                self.client = genai
                self.chat_model = settings.gemini_model or "gemini-2.0-flash"
            
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
        response = self.embedding_client.embeddings.create(
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
        conversation_messages = []
        conversation_messages.append({
            "role": "system",
            "content": self.default_system_prompt
        })
        
        if session_id:
            history_messages = self.get_conversation_history(session_id)
            conversation_messages.extend(history_messages)
        
        conversation_messages.extend(messages)
            
        # แยกการเรียก API ตาม provider
        if self.ai_provider == "Gemini":
            try:
                generation_config = self.generation_config.copy()
                if 'temperature' in kwargs:
                    generation_config["temperature"] = kwargs['temperature']
                if 'max_tokens' in kwargs:
                    generation_config["max_output_tokens"] = kwargs['max_tokens']
                    
                model = self.client.GenerativeModel(
                    model_name=self.chat_model,
                    generation_config=generation_config
                )
                
                # แปลง conversation_messages เป็น history สำหรับ Gemini
                history = []
                for msg in conversation_messages[1:-1]:  # ข้าม system message และข้อความล่าสุด
                    if msg["role"] in ["user", "assistant"]:
                        history.append({
                            "role": "user" if msg["role"] == "user" else "model",
                            "parts": [msg["content"]]
                        })
                
                chat = model.start_chat(history=history)
                
                # ส่ง system prompt รวมกับ user message
                last_message = conversation_messages[-1]["content"]
                if conversation_messages[0]["role"] == "system":
                    last_message = f"{conversation_messages[0]['content']}\n\n{last_message}"
                
                response = chat.send_message(last_message)
                
                if not response.text:
                    raise ValueError("Empty response from Gemini")
                
                return {
                    "content": response.text,
                    "usage": {
                        "total_tokens": 0,
                        "prompt_tokens": 0,
                        "completion_tokens": 0
                    }
                }
            except Exception as e:
                error_info = f"""
                Provider: {self.ai_provider}
                Model: {self.chat_model}
                Error: {str(e)}
                """
                frappe.log_error(error_info, "AI Chat Completion Error")
                # Fallback to OpenAI if Gemini fails
                self.ai_provider = "Open Ai"
                return self.chat_completion(messages, session_id, **kwargs)
                
        else:  # OpenAi และ Typhoon
            try:
                response = self.client.chat.completions.create(
                    model=self.chat_model,
                    messages=conversation_messages,
                    **kwargs
                )
                return {
                    "content": response.choices[0].message.content,
                    "usage": {
                        "total_tokens": response.usage.total_tokens,
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens
                    }
                }
            except Exception as e:
                error_info = f"""
                Provider: {self.ai_provider}
                Model: {self.chat_model}
                Error: {str(e)}
                """
                frappe.log_error(error_info, "AI Chat Completion Error")
                raise 