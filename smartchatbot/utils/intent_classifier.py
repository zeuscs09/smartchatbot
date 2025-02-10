import frappe
from typing import List, Dict
from .ai_client import AIClient

class IntentClassifier:
    def __init__(self):
        self.ai_client = AIClient.get_instance()
        
    def get_instruction_data(self):
        """ดึงข้อมูล content types และ product categories"""
        content_types = frappe.get_all(
            "JJ Content Type",
            fields=["description"],
            pluck="description"
        )
        
        product_categories = frappe.get_all(
            "JJ Product Category",
            fields=["description"],
            pluck="description"
        )
        
        return {
            "content_types": content_types,
            "product_categories": product_categories
        }
    
    def extract_questions(self, text: str, session_id: str = None) -> Dict:
        """วิเคราะห์ intent และส่งคืนทั้ง questions และ token usage"""
        # แปลง unicode เป็นข้อความปกติก่อนวิเคราะห์
        decoded_text = text.encode().decode('unicode-escape') if '\\u' in text else text
        
        instruction = """You are an expert in question analysis. Please analyze and transform the following question or message.

Message types are:
1. product: Questions about products
2. content: Questions about content and articles
3. greeting: Greetings, hello, or general messages
4. general: General questions that are not specific

For product and content types, transform the question into a search-friendly format by:
1. Remove unnecessary words like "มีไหม", "อยากทราบ", etc.
2. Keep only essential keywords
3. Add relevant category terms if implied
4. Standardize units (ml, kg, etc.)

Please respond in JSON object format with a "questions" key as an array where each object contains:
- original_question: The original message
- search_text: The transformed search-friendly text (for product/content types only)
- type: Message type (product, content, greeting, general)
- intents: Array of related intents e.g. ["ask_image", "ask_price"]
- industry: Array of related industries (if any)"""

        # สร้าง context จากประวัติการสนทนา
        context = ""
        if session_id:
            history = self.ai_client.get_conversation_history(session_id)
            if history:
                context = "Previous conversation history:\n"
                for msg in history:  # ดึงแค่ 3 messages ล่าสุด
                    role = "User" if msg["role"] == "user" else "Assistant"
                    context += f"{role}: {msg['content']}\n"
                context += "\nCurrent message:\n"

        response = self.ai_client.chat_completion(
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": f"{context}{decoded_text}"}
            ],
            temperature=0,
            response_format={ "type": "json_object" }
        )

        try:
            result = frappe.parse_json(response["content"])
            return {
                "questions": result.get("questions", [{
                    "original_question": decoded_text,
                    "search_text": decoded_text,  # ถ้าไม่มีการแปลง ใช้ข้อความเดิม
                    "type": "general",
                    "intents": [],
                    "industry": []
                }]),
                "usage": response.get("usage", {})
            }
        except Exception as e:
            frappe.log_error(f"Error parsing intent: {str(e)}\nResponse: {response}")
            return {
                "questions": [{
                    "original_question": decoded_text,
                    "search_text": decoded_text,
                    "type": "general",
                    "intents": [],
                    "industry": []
                }],
                "usage": response.get("usage", {})
            }

# ตัวอย่างการใช้งาน
def analyze_user_query(query: str) -> List[Dict[str, str]]:
    classifier = IntentClassifier()
    return classifier.extract_questions(query) 