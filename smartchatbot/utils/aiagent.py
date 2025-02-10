import frappe
from typing import List, Dict
from .intent_classifier import IntentClassifier
from .ai_client import AIClient
from .qdrant import QdrantManager
from qdrant_client import QdrantClient
from qdrant_client.http import models
import uuid
from datetime import datetime, timedelta

class AIAgent:
    def __init__(self):
        self.ai_client = AIClient.get_instance()
        self.classifier = IntentClassifier()
        self.qdrant = QdrantManager()
   

    def get_or_create_session(self, session_id: str = None) -> str:
        """สร้างหรือดึง session ที่มีอยู่"""
        # ถ้ามี session_id ให้ตรวจสอบว่ายังใช้งานได้
        if session_id:
            active_session = frappe.get_all(
                "JJ Chat History",
                filters={
                    "session_id": session_id
                  
                },
                limit=1
            )
            if active_session:
                return session_id
        
        # หา session ล่าสุดที่ยังไม่หมดอายุ
        active_session = frappe.get_all(
            "JJ Chat History",
            filters={
                "session_id": session_id
            },
            fields=["session_id"],
            order_by="creation desc",
            limit=1
        )
        
        if active_session:
            return active_session[0].session_id
            
        # สร้าง session ใหม่
        return f"session_{uuid.uuid4().hex[:12]}"



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

def reply_message(message: str, session_id: str) -> Dict:
    """
    ตอบกลับข้อความโดยใช้ session_id ที่ได้รับจากภายนอก
    Returns:
        Dict: {
            "text": str,  # ข้อความตอบกลับแบบละเอียด
            "summary_text": str,  # ข้อความสรุปสั้นๆ
            "products": List[Dict]  # array ของสินค้าที่เกี่ยวข้อง
        }
    """
    try:
        agent = AIAgent()
        
        # วิเคราะห์ intent พร้อม session context
        intent_response = agent.classifier.extract_questions(
            message, 
            session_id=session_id
        )
        
        questions = intent_response["questions"]
        questions_text = "\n".join([q['question'] for q in questions])
        
        # สร้าง chat history
        chat_history = frappe.get_doc({
            "doctype": "JJ Chat History",
            "user_message": message,
            "session_id": session_id,
            "intent_analysis": frappe.as_json({
                "questions": questions,
                "success": True,
                "timestamp": str(frappe.utils.now_datetime())
            }, indent=2),
            "intent_token": intent_response.get("usage", {}).get("total_tokens", 0)
        })
        
        # ถ้าเป็น greeting หรือ general
        if questions and questions[0]['type'] in ['greeting', 'general']:
            ai_response = agent.ai_client.chat_completion(
                messages=[{"role": "user", "content": message}],
                session_id=session_id
            )
            
            chat_history.ai_response = ai_response["content"]
            chat_history.response_token = ai_response.get("usage", {}).get("total_tokens", 0)
            chat_history.insert(ignore_permissions=True)
            return {
                "text": ai_response["content"],
                "summary_text": "",
                "products": []
            }
            
        # ถ้าไม่ใช่ greeting ค่อยทำการค้นหาข้อมูล
        vector = agent.ai_client.get_embedding(questions_text)
        
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
        
        # เก็บ products ก่อนสร้าง context
        products = []
        for result in product_results:
            payload = result.payload
            products.append({
                "name": payload.get("id", ""),
                "title": payload.get("title", ""),
                "price": payload.get("price", ""),
                "description": payload.get("description", ""),
                "image_url": payload.get("image_url", "")
            })
        
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
        
        if products:
            instruction = """You are a product expert. Please answer questions following these guidelines:
1. Be concise and to the point
2. For price-related questions, specify exact prices
3. For multiple products, list them with bullet points
4. Use friendly and polite Thai language
5. Include image links when asked about product images
6. For products under 100 baht, emphasize value for money
7. For products with multiple sizes, recommend based on usage
8. Do not use any markdown formatting
9. Response must be in Thai language"""

            summary_instruction = """Summarize the product information in Thai language:
1. Number of relevant products
2. Price range (if any)
3. Key product features
Note: Keep it within 2 lines, no markdown formatting"""

        else:
            instruction = """You are an information expert. Please follow these guidelines:
1. Be concise and to the point
2. Use friendly and polite Thai language
3. If no exact match found, suggest alternative questions
4. Provide additional useful recommendations
5. Do not use any markdown formatting
6. Response must be in Thai language"""

            summary_instruction = """Summarize the answer in Thai language:
1. Keep it within 1 line
2. No markdown formatting
3. Maintain friendly tone"""

        # สร้างคำตอบละเอียด
        final_response = agent.ai_client.chat_completion(
            messages=[
                {"role": "system", "content": instruction },
                {"role": "user", "content": f"{context}\n\nคำถาม:\n{questions_text}"}
            ],
            session_id=session_id
        )

        # สร้างคำตอบแบบสรุป
        summary_response = agent.ai_client.chat_completion(
            messages=[
                {"role": "system", "content": summary_instruction},
                {"role": "user", "content": f"คำตอบที่ต้องสรุป:\n{final_response['content']}"}
            ],
            session_id=session_id
        )
        
        chat_history.ai_response = final_response["content"]
        chat_history.response_token = final_response.get("usage", {}).get("total_tokens", 0)
        chat_history.search_results = frappe.as_json({
            "products": products,
            "content": content_results,
            "timestamp": str(frappe.utils.now_datetime())
        })
        chat_history.insert(ignore_permissions=True)

        return {
            "text": final_response["content"],
            "summary_text": summary_response["content"],
            "products": products
        }
        
    except Exception as e:
        frappe.log_error(f"Error in reply_message: {str(e)}")
        return {
            "text": "ขออภัย เกิดข้อผิดพลาดในการประมวลผล กรุณาลองใหม่อีกครั้ง",
            "summary_text": "เกิดข้อผิดพลาด",
            "products": []
        }
    

    