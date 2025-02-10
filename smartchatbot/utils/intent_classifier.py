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
    
    def extract_questions(self, text: str) -> List[Dict[str, str]]:
        """แยกคำถามและประเภทของแต่ละคำถาม"""
        data = self.get_instruction_data()
        
        instruction = f"""คุณเป็นผู้เชี่ยวชาญในการวิเคราะห์คำถาม กรุณาแยกคำถามและระบุประเภทของแต่ละคำถาม

ประเภทคำถามมีดังนี้:
1. product: คำถามเกี่ยวกับสินค้า เช่น
- ถามเกี่ยวกับราคา ขนาด รูปภาพ รายละเอียดสินค้า
- ถามหาสินค้าที่มีคุณสมบัติเฉพาะ
- ถามเกี่ยวกับสินค้าในหมวดหมู่: {', '.join(data['product_categories'])}

2. content: คำถามเกี่ยวกับเนื้อหาและบทความประเภท: {', '.join(data['content_types'])}

กรุณาตอบในรูปแบบ JSON object ที่มี key "questions" เป็น array โดยแต่ละ object ประกอบด้วย:
- question: คำถามที่แยกได้
- type: ประเภทของคำถาม (product หรือ content)
- intents: array ของ intent ที่เกี่ยวข้อง โดยมี intent ดังนี้
  - ask_image: ต้องการดูรูปภาพ
  - ask_price: ต้องการทราบราคา
  - ask_detail: ต้องการรายละเอียดสินค้า/เนื้อหา
- industry: array ของอุตสาหกรรมที่เกี่ยวข้อง โดยมีดังนี้
  - education, school: เกี่ยวกับโรงเรียน การศึกษา
  - healthcare, hospital: เกี่ยวกับโรงพยาบาล การแพทย์
  - hotel, hospitality: เกี่ยวกับโรงแรม ที่พัก
  - restaurant, food: เกี่ยวกับร้านอาหาร อาหาร
  - office, business: เกี่ยวกับสำนักงาน ธุรกิจ

ตัวอย่างคำตอบ:
{{"questions": [
    {{"question": "มีสินค้าอะไรแนะนำสำหรับโรงเรียนบ้าง", 
      "type": "product", 
      "intents": ["ask_detail"],
      "industry": ["education", "school"]
    }},
    {{"question": "ขอดูรูปสินค้าหน่อย", 
      "type": "product", 
      "intents": ["ask_image"],
      "industry": []
    }}
]}}"""

        response_text = self.ai_client.chat_completion(
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": text}
            ],
            temperature=0,
            response_format={ "type": "json_object" }
        )
        
        try:
            result = frappe.parse_json(response_text)
            return result.get("questions", [])
        except Exception as e:
            frappe.log_error(f"Error parsing intent classification response: {str(e)}")
            return []

# ตัวอย่างการใช้งาน
def analyze_user_query(query: str) -> List[Dict[str, str]]:
    classifier = IntentClassifier()
    return classifier.extract_questions(query) 