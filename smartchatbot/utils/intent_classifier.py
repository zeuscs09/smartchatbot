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
        decoded_text = text.encode().decode('unicode-escape') if '\\u' in text else text
        
        # ดึงข้อมูลจากระบบ
        data = self.get_instruction_data()
        content_types = data.get("content_types", [])
        product_categories = data.get("product_categories", [])
        
        instruction = f"""You are an expert in question analysis. For the given message, analyze and extract price conditions if present.

For price-related questions, you MUST extract specific price conditions in this format:
- operator: Use these symbols only
  * "=" for exact price
  * "<" for less than
  * ">" for more than
  * "<=" for less than or equal
  * ">=" for more than or equal
  * "between" for price range
- value: number or [min, max] for "between" operator

For search_text extraction:
1. REMOVE these words:
   - Price related: "ราคา", "บาท", "ไม่เกิน", "ต่ำกว่า", "สูงกว่า", "ระหว่าง", "ถึง"
   - Generic terms: "สินค้า", "ของ", "อยากได้", "มี", "หา", "ขอ", "ดู", "เกี่ยวกับ"
   - Price numbers and units

2. KEEP these words:
   - Product categories: {", ".join(product_categories)}
   - Content types: {", ".join(content_types)}
   - Specific product attributes and descriptions
   - Industry or usage context
   - Brand names if mentioned

Examples of price extraction:
- "ราคาต่ำกว่า 10 บาท" -> {{"operator": "<", "value": 10}}
- "สินค้าราคาไม่เกิน 100" -> {{"operator": "<=", "value": 100}}
- "ราคา 200-300 บาท" -> {{"operator": "between", "value": [200, 300]}}

Examples of search_text:
- "สบู่เหลวราคาไม่เกิน 10 บาท" -> search_text: "สบู่เหลว"
- "หาสบู่โรงแรมราคา 4-8 บาท" -> search_text: "สบู่ โรงแรม"
- "สินค้าราคา 4-8 บาท" -> search_text: ""

Please respond in JSON format with:
{{
    "questions": [
        {{
            "original_question": "Original text",
            "search_text": "Clean search text without price and generic terms",
            "type": "product/content/greeting/general",
            "intents": ["intent1", "intent2"],
            "price_condition": {{price condition object if any}},
            "industry": ["industry1", "industry2"]
        }}
    ]
}}

Note: Always check for price conditions in Thai language patterns like:
- "ราคา..." "ราคาไม่เกิน..." "ราคาต่ำกว่า..."
- "...บาท" "...บาทขึ้นไป" "...บาทลงมา"
- "ไม่เกิน..." "ต่ำกว่า..." "สูงกว่า..."
- "ระหว่าง... ถึง..."

If no specific product, content, or attribute is mentioned, search_text should be empty string."""

        try:
            response = self.ai_client.chat_completion(
                messages=[
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": decoded_text}
                ]
            )
            
            # เพิ่ม logging เพื่อ debug
            frappe.log_error(
                title="Intent Analysis Debug",
                message=f"""
                Input: {decoded_text}
                Available Categories: {product_categories}
                Available Content Types: {content_types}
                Response: {response.get('content')}
                """
            )
            
            result = frappe.parse_json(response["content"])
            return {
                "questions": result.get("questions", []),
                "usage": response.get("usage", {})
            }
            
        except Exception as e:
            frappe.log_error(f"Error in intent analysis: {str(e)}\nResponse: {response}")
            return {
                "questions": [{
                    "original_question": decoded_text,
                    "search_text": decoded_text,
                    "type": "general",
                    "intents": [],
                    "price_condition": None,
                    "industry": []
                }],
                "usage": response.get("usage", {})
            }

# ตัวอย่างการใช้งาน
def analyze_user_query(query: str) -> List[Dict[str, str]]:
    classifier = IntentClassifier()
    return classifier.extract_questions(query) 