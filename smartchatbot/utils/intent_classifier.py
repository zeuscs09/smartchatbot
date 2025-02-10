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
        instruction = """คุณเป็นผู้เชี่ยวชาญในการวิเคราะห์คำถาม กรุณาแยกประเภทคำถามหรือข้อความ

ประเภทข้อความมีดังนี้:
1. product: คำถามเกี่ยวกับสินค้า
2. content: คำถามเกี่ยวกับเนื้อหาและบทความ
3. greeting: คำทักทาย สวัสดี หรือข้อความทั่วไป
4. general: คำถามทั่วไปที่ไม่เฉพาะเจาะจง

กรุณาตอบในรูปแบบ JSON object ที่มี key "questions" เป็น array โดยแต่ละ object ประกอบด้วย:
- question: ข้อความหรือคำถาม
- type: ประเภทของข้อความ (product, content, greeting, general)
- intents: array ของ intent ที่เกี่ยวข้อง เช่น ["ask_image", "ask_price"]
- industry: array ของอุตสาหกรรมที่เกี่ยวข้อง (ถ้ามี)"""

        # สร้าง context จากประวัติการสนทนา
        context = ""
        if session_id:
            history = self.ai_client.get_conversation_history(session_id)
            if history:
                context = "ประวัติการสนทนาก่อนหน้า:\n"
                for msg in history[-3:]:  # ดึงแค่ 3 messages ล่าสุด
                    role = "ผู้ใช้" if msg["role"] == "user" else "ผู้ช่วย"
                    context += f"{role}: {msg['content']}\n"
                context += "\nข้อความปัจจุบัน:\n"

        response = self.ai_client.chat_completion(
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": f"{context}{text}"}
            ],
            temperature=0,
            response_format={ "type": "json_object" }
        )

        try:
            result = frappe.parse_json(response["content"])
            return {
                "questions": result.get("questions", [{
                    "question": text,
                    "type": "general",
                    "intents": [],
                    "industry": []
                }]),
                "usage": response.get("usage", {})
            }
        except Exception as e:
            frappe.log_error(f"Error parsing intent: {str(e)}\nResponse: {response}")
            # ส่งค่า default ในรูปแบบเดียวกัน
            return {
                "questions": [{
                    "question": text,
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