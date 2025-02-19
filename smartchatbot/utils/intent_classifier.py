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
        
        instruction = f"""You are an expert in multilingual question analysis. For the given message in any language, analyze and extract price conditions if present.

Message types and intents:
1. type: "product" - Questions about products ONLY
   - Questions about products, prices, or inventory
   - Examples in multiple languages:
     * English: "What products do you have", "Show me products"
     * Japanese: "商品を見せてください", "製品はありますか"
     * Chinese: "有什么产品", "展示产品"
     * Thai: "มีสินค้าอะไรบ้าง", "สินค้าราคาเท่าไร"
   - Keywords in multiple languages:
     * English: "products", "price", "items"
     * Japanese: "商品", "製品", "価格"
     * Chinese: "产品", "价格", "商品"
     * Thai: "สินค้า", "ราคา"
   - intent: ["product"] - Search in products ONLY

2. type: "content" - Questions about content/articles ONLY
   - Questions about articles, guides, information
   - Examples in multiple languages:
     * English: "Any articles?", "Show me information"
     * Japanese: "記事はありますか", "情報を見せてください"
     * Chinese: "有什么文章", "显示信息"
     * Thai: "มีบทความอะไรบ้าง", "ข้อมูลมีอะไรบ้าง"
   - Keywords in multiple languages:
     * English: "articles", "information", "guides"
     * Japanese: "記事", "情報", "ガイド"
     * Chinese: "文章", "信息", "指南"
     * Thai: "บทความ", "ข้อมูล", "คู่มือ"
   - intent: ["content"] - Search in content ONLY

3. type: "all" - Questions about both products and content
   - General questions that could relate to both
   - Examples in multiple languages:
     * English: "Tell me about soap"
     * Japanese: "石鹸について教えてください"
     * Chinese: "告诉我关于肥皂的信息"
     * Thai: "เกี่ยวกับสบู่มีอะไรบ้าง"
   - intent: ["all"] - Search in BOTH products and content

4. type: "general" - General conversation
   - Greetings and small talk only
   - Examples in multiple languages:
     * English: "Hello", "Thank you"
     * Japanese: "こんにちは", "ありがとう"
     * Chinese: "你好", "谢谢"
     * Thai: "สวัสดี", "ขอบคุณ"
   - intent: ["general"] - No search needed

Important classification rules:
1. Detect the language and analyze the intent based on that language's context
2. For product-related questions -> Always type "product"
3. For information/article questions -> Always type "content"
4. For questions that could refer to both -> Always type "all"
5. For greetings/small talk -> Always type "general"

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
   - Price related: "price", "baht", "ราคา", "บาท", "cost", "not more than"
   - Generic terms: "product", "item", "สินค้า", "want", "show", "find", "about"
   - Price numbers and units

2. KEEP these words:
   - Product categories: {", ".join(product_categories)}
   - Content types: {", ".join(content_types)}
   - Specific product attributes and descriptions
   - Industry or usage context
   - Brand names if mentioned

Please respond in JSON format with:
{{
    "questions": [
        {{
            "original_question": "Original text",
            "search_text": "Clean search text without price and generic terms",
            "type": "product/content/general",
            "intents": ["product"/"content"/"general"],
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
                response_format={"type": "json_object"},
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
            frappe.log_error(title="Error in intent analysis", message=f"Error in intent analysis: {str(e)}\nResponse: {response}")
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