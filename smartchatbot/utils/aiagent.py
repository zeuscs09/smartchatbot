import frappe
from typing import List, Dict
from .intent_classifier import IntentClassifier
from .ai_client import AIClient
from .qdrant import QdrantManager
from qdrant_client import QdrantClient
from qdrant_client.http import models

class AIAgent:
    def __init__(self):
        self.ai_client = AIClient.get_instance()
        self.classifier = IntentClassifier()
        self.qdrant = QdrantManager()

    def answer_product(self, questions: List[Dict]) -> str:
        """ตอบคำถามเกี่ยวกับสินค้า"""
        product_questions = [q for q in questions if q['type'] == 'product']
        if not product_questions:
            return ""
        
        # ตรวจสอบ intent จากคำถาม
        has_image_intent = any('ask_image' in q.get('intents', []) for q in product_questions)
        
        # ค้นหาข้อมูลที่เกี่ยวข้องจาก Qdrant
        questions_text = " ".join(q['question'] for q in product_questions)
        vector = self.qdrant.get_embedding(questions_text)
        
        results = self.qdrant.client.search(
            collection_name="jj_product",
            query_vector=vector,
            limit=5,
            score_threshold=0.5
        )
        
        if not results:
            return "ขออภัย ไม่พบข้อมูลสินค้าที่เกี่ยวข้องกับคำถามของคุณ"
        
        # สร้าง context จากผลการค้นหา
        context = "ข้อมูลสินค้าที่เกี่ยวข้อง:\n"
        for result in results:
            payload = result.payload
            context += f"\nชื่อสินค้า: {payload['title']}\n"
            context += f"รายละเอียด: {payload['description']}\n"
            if payload.get('price'):
                context += f"ราคา: {payload['price']}\n"
            if payload.get('content'):
                context += f"รายละเอียดเพิ่มเติม: {payload['content']}\n"
            # แสดงรูปภาพเฉพาะเมื่อมี intent ask_image
            if has_image_intent and payload.get('image_url'):
                context += f"รูปภาพ: {payload['image_url']}\n"
        
        instruction = """คุณเป็นผู้เชี่ยวชาญเกี่ยวกับสินค้า กรุณาตอบคำถามต่อไปนี้โดยใช้ข้อมูลที่ให้มา"""
        if has_image_intent:
            instruction += " หากมีรูปภาพสินค้าให้แสดงลิงก์รูปภาพด้วย"
        instruction += ":"
        
        questions_text = "\n".join(f"- {q['question']}" for q in product_questions)
        
        return self.ai_client.chat_completion(
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": f"{context}\n\nคำถาม:\n{questions_text}"}
            ],
            max_tokens=800
        )

    def answer_content(self, questions: List[Dict]) -> str:
        """ตอบคำถามเกี่ยวกับเนื้อหา"""
        content_questions = [q['question'] for q in questions if q['type'] == 'content']
        if not content_questions:
            return ""
            
        # ค้นหาข้อมูลที่เกี่ยวข้องจาก Qdrant
        questions_text = " ".join(content_questions)
        vector = self.qdrant.get_embedding(questions_text)
        
        results = self.qdrant.client.search(
            collection_name="jj_content",
            query_vector=vector,
            limit=3
        )
        
        # สร้าง context จากผลการค้นหา
        context = "เนื้อหาที่เกี่ยวข้อง:\n"
        for result in results:
            payload = result.payload
            context += f"\nหัวข้อ: {payload['title']}\n"
            context += f"คำอธิบาย: {payload['description']}\n"
            context += f"เนื้อหา: {payload['content']}\n"
        
        instruction = """คุณเป็นผู้เชี่ยวชาญเกี่ยวกับเนื้อหาและบทความ กรุณาตอบคำถามต่อไปนี้โดยใช้ข้อมูลที่ให้มา:"""
        questions_text = "\n".join(f"- {q}" for q in content_questions)
        
        return self.ai_client.chat_completion(
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": f"{context}\n\nคำถาม:\n{questions_text}"}
            ],
            max_tokens=500
        )

    def combine_answers(self, product_answer: str, content_answer: str, original_questions: List[Dict]) -> str:
        """รวมคำตอบทั้งหมดให้เป็นข้อความที่สอดคล้องกัน"""
        if not product_answer and not content_answer:
            return "ขออภัย ฉันไม่สามารถตอบคำถามของคุณได้ในขณะนี้"
            
        # สร้าง prompt สำหรับรวมคำตอบ
        instruction = """กรุณารวมคำตอบต่อไปนี้ให้เป็นข้อความที่ต่อเนื่องและเป็นธรรมชาติ:"""
        
        context = f"""คำถามที่ได้รับ:
{chr(10).join(f'- {q["question"]}' for q in original_questions)}

คำตอบเกี่ยวกับสินค้า:
{product_answer}

คำตอบเกี่ยวกับเนื้อหา:
{content_answer}"""
        
        return self.ai_client.chat_completion(
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": context}
            ],
            max_tokens=1000
        )

def reply_message(message: str) -> str:
    chat_history = None
    try:
        agent = AIAgent()
        
        # สร้างบันทึกประวัติการสนทนา
        chat_history = frappe.get_doc({
            "doctype": "JJ Chat History",
            "user_message": message,
            "timestamp": frappe.utils.now_datetime(),
            "intent_analysis": "{}",
            "search_results": "{}",
            "ai_response": ""
        })
        
        # วิเคราะห์ intent
        questions = agent.classifier.extract_questions(message)
        if not questions:
            intent_analysis = {
                "success": False,
                "error": "ไม่สามารถวิเคราะห์คำถามได้",
                "questions": []
            }
            chat_history.intent_analysis = frappe.as_json(intent_analysis, indent=2, ensure_ascii=False)
            chat_history.ai_response = "ขออภัย ฉันไม่เข้าใจคำถามของคุณ กรุณาถามใหม่อีกครั้ง"
            chat_history.insert(ignore_permissions=True)
            return chat_history.ai_response
        
        # บันทึกผลการวิเคราะห์ intent
        intent_analysis = {
            "success": True,
            "questions": questions,
            "timestamp": str(frappe.utils.now_datetime())
        }
        chat_history.intent_analysis = frappe.as_json(intent_analysis, indent=2, ensure_ascii=False)
        
        # รวมคำถามทั้งหมด
        questions_text = " ".join(q['question'] for q in questions)
        vector = agent.qdrant.get_embedding(questions_text)
        
        # ค้นหาจากทั้ง content และ product
        search_results = {
            "combined_search": {
                "query": questions_text,
                "product_results": [],
                "content_results": [],
                "timestamp": str(frappe.utils.now_datetime())
            }
        }
        
        # ค้นหาจาก product และ content collection
        product_results = agent.qdrant.client.search(
            collection_name="jj_product",
            query_vector=vector,
            limit=5,
            score_threshold=0.5
        )
        
        content_results = agent.qdrant.client.search(
            collection_name="jj_content",
            query_vector=vector,
            limit=3,
            score_threshold=0.5
        )
        
        # ถ้าไม่พบผลการค้นหา ลองหาวิธีอื่นๆ
        if not product_results and not content_results:
            alternative_results = []
            
            # 1. ลองค้นหาจาก industry ถ้ามี
            industries = []
            for q in questions:
                if q.get('industry'):  # ใช้ .get() เพื่อป้องกัน KeyError
                    industries.extend(q['industry'])
            
            if industries:
                industry_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="industries",
                            match={
                                "any": industries
                            }
                        )
                    ]
                )
                
                industry_results = agent.qdrant.client.search(
                    collection_name="jj_product",
                    query_vector=vector,
                    limit=3,
                    query_filter=industry_filter
                )
                alternative_results.extend(industry_results)
            
            # 2. ถ้ายังไม่พบ ลองค้นหาสินค้าทั่วไปที่เกี่ยวข้อง
            if not alternative_results:
                general_results = agent.qdrant.client.search(
                    collection_name="jj_product",
                    query_vector=vector,
                    limit=3,
                    score_threshold=0.3  # ลด threshold ลงเพื่อหาสินค้าที่เกี่ยวข้องมากขึ้น
                )
                alternative_results.extend(general_results)
            
            # ถ้าพบผลลัพธ์ทางเลือก
            if alternative_results:
                search_results["combined_search"]["product_results"] = [
                    {
                        "id": r.id,
                        "score": r.score,
                        "title": r.payload.get('title', ''),
                        "description": r.payload.get('description', ''),
                        "price": r.payload.get('price', ''),
                        "image_url": r.payload.get('image_url', ''),
                        "type": "product",
                        "industries": r.payload.get('industries', [])
                    } for r in alternative_results
                ]
                
                # สร้าง context สำหรับสินค้าที่แนะนำ
                context = "ขออภัย ไม่พบสินค้าที่ตรงกับคำถามของคุณ\n\nแต่เรามีสินค้าที่อาจเกี่ยวข้องดังนี้:\n"
                for result in alternative_results:
                    payload = result.payload
                    context += f"\nชื่อ: {payload.get('title', '')}\n"
                    context += f"รายละเอียด: {payload.get('description', '')}\n"
                    if payload.get('price'):
                        context += f"ราคา: {payload['price']}\n"
                    if payload.get('image_url') and any('ask_image' in q.get('intents', []) for q in questions):
                        context += f"รูปภาพ: {payload['image_url']}\n"
                
                # บันทึกผลการค้นหา
                chat_history.search_results = frappe.as_json(search_results, indent=2, ensure_ascii=False)
                
                # สร้างคำตอบ
                instruction = """คุณเป็นผู้เชี่ยวชาญด้านการแนะนำสินค้า กรุณา:
                1. ถ้าพบสินค้าที่เกี่ยวข้อง ให้แนะนำสินค้าโดยตรง ไม่ต้องบอกว่า "ไม่พบสินค้า"
                2. อธิบายคุณสมบัติเด่นของสินค้าที่แนะนำ
                3. เน้นประโยชน์และความเหมาะสมกับการใช้งาน
                4. ถ้าผู้ใช้ถามหาสินค้านอกเหนือจากสินค้าใด ให้เน้นนำเสนอสินค้าประเภทอื่นๆ ที่พบ"""
                
                final_answer = agent.ai_client.chat_completion(
                    messages=[
                        {"role": "system", "content": instruction},
                        {"role": "user", "content": f"{context}\n\nคำถาม:\n{questions_text}"}
                    ],
                    max_tokens=1000
                )
                
                chat_history.ai_response = final_answer
                chat_history.insert(ignore_permissions=True)
                return final_answer
            
            # ถ้าไม่พบผลลัพธ์ใดๆ เลย
            chat_history.search_results = frappe.as_json({
                "combined_search": {
                    "query": questions_text,
                    "error": "ไม่พบข้อมูลที่เกี่ยวข้อง",
                    "timestamp": str(frappe.utils.now_datetime())
                }
            }, indent=2, ensure_ascii=False)
            
            chat_history.ai_response = "ขออภัย ขณะนี้เราไม่มีสินค้าหรือข้อมูลที่ตรงกับความต้องการของคุณ กรุณาติดต่อเจ้าหน้าที่เพื่อสอบถามข้อมูลเพิ่มเติม"
            chat_history.insert(ignore_permissions=True)
            return chat_history.ai_response
            
        # สร้าง context จากผลการค้นหาทั้งหมด
        context = "ข้อมูลที่เกี่ยวข้อง:\n"
        
        # เรียงผลการค้นหาตาม score
        all_results = (
            [(r, 'product') for r in product_results] +
            [(r, 'type') for r in content_results]
        )
        all_results.sort(key=lambda x: x[0].score, reverse=True)
        
        for result, result_type in all_results:
            payload = result.payload
            context += f"\nประเภท: {result_type}\n"
            context += f"ชื่อ: {payload.get('title', '')}\n"
            context += f"รายละเอียด: {payload.get('description', '')}\n"
            if payload.get('price'):
                context += f"ราคา: {payload['price']}\n"
            if payload.get('content'):
                context += f"เนื้อหา: {payload['content']}\n"
            
            # แสดงรูปภาพเฉพาะเมื่อมี intent ask_image
            has_image_intent = any('ask_image' in q.get('intents', []) for q in questions)
            if has_image_intent and payload.get('image_url'):
                context += f"รูปภาพ: {payload['image_url']}\n"
        
        # สร้างคำตอบ
        instruction = """คุณเป็นผู้เชี่ยวชาญ กรุณาตอบคำถามต่อไปนี้โดยใช้ข้อมูลที่ให้มา
        - ถ้าเป็นคำถามเกี่ยวกับสินค้า ให้เน้นตอบข้อมูลจากส่วนที่เป็น product
        - ถ้าเป็นคำถามเกี่ยวกับเนื้อหาหรือบทความ ให้เน้นตอบข้อมูลจากส่วนที่เป็น content
        - ถ้ามีการถามถึงรูปภาพ ให้แสดงลิงก์รูปภาพด้วย"""
        
        questions_text = "\n".join(f"- {q['question']}" for q in questions)
        
        final_answer = agent.ai_client.chat_completion(
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": f"{context}\n\nคำถาม:\n{questions_text}"}
            ],
            max_tokens=1000
        )
        
        # บันทึกคำตอบ
        chat_history.ai_response = final_answer
        chat_history.insert(ignore_permissions=True)
        
        return final_answer
        
    except Exception as e:
        error_message = f"Error: {str(e)}"
        frappe.log_error(message=error_message, title="ChatGPT Error")
        
        if chat_history:
            error_data = {
                "success": False,
                "error": error_message,
                "questions": []
            }
            chat_history.intent_analysis = frappe.as_json(error_data, indent=2, ensure_ascii=False)
            chat_history.search_results = frappe.as_json({
                "error": error_message,
                "timestamp": str(frappe.utils.now_datetime())
            }, indent=2, ensure_ascii=False)
            chat_history.ai_response = "ขออภัย ระบบมีปัญหา กรุณาลองใหม่อีกครั้ง"
            chat_history.insert(ignore_permissions=True)
        
        return "ขออภัย ระบบมีปัญหา กรุณาลองใหม่อีกครั้ง"
    

    