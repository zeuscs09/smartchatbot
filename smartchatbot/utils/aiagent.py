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
        
        # ใช้ search_text แทน original_question
        search_texts = [q['search_text'] for q in questions if q['type'] in ['product', 'content']]
        questions_text = " ".join(search_texts) 

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
                "products": [],
                "content": []
            }
            
        # ถ้าไม่ใช่ greeting ค่อยทำการค้นหาข้อมูล
        vector = agent.qdrant.get_embedding(questions_text)
        
        # สร้าง filter conditions จาก price_condition
        filter_conditions = None
        price_conditions = [q.get('price_condition') for q in questions if q.get('price_condition')]
        
        if price_conditions:
            conditions = []
            for condition in price_conditions:
                operator = condition.get('operator')
                value = condition.get('value')
                
                if operator == '=':
                    conditions.append(
                        models.FieldCondition(
                            key="price",
                            match=models.MatchValue(value=value)
                        )
                    )
                elif operator == '<':
                    conditions.append(
                        models.FieldCondition(
                            key="price",
                            range=models.Range(lt=value)
                        )
                    )
                elif operator == '>':
                    conditions.append(
                        models.FieldCondition(
                            key="price",
                            range=models.Range(gt=value)
                        )
                    )
                elif operator == '<=':
                    conditions.append(
                        models.FieldCondition(
                            key="price",
                            range=models.Range(lte=value)
                        )
                    )
                elif operator == '>=':
                    conditions.append(
                        models.FieldCondition(
                            key="price",
                            range=models.Range(gte=value)
                        )
                    )
                elif operator == 'between':
                    conditions.append(
                        models.FieldCondition(
                            key="price",
                            range=models.Range(
                                gte=value[0],
                                lte=value[1]
                            )
                        )
                    )
            
            # รวม conditions สำหรับ product ที่มีราคา
            filter_conditions = models.Filter(
                must=[
                    models.FieldCondition(
                        key="doctype",
                        match=models.MatchValue(value="JJ Product")
                    ),
                    *conditions
                ]
            )
            
            frappe.log_error(
                title="Price Filter Debug",
                message=f"""
                Price Conditions: {price_conditions}
                Filter Applied: {filter_conditions}
                """
            )
        
        # ค้นหาด้วย vector และ filter (ถ้ามี)
        search_results = agent.qdrant.client.search(
            collection_name="jj_data",
            query_vector=vector,
            limit=20,
            score_threshold=0.2,
            search_params=models.SearchParams(
                hnsw_ef=512
            ),
            query_filter=filter_conditions
        )
        
        # แยกประเภทตาม doctype
        product_results = [r for r in search_results if r.payload.get('doctype') == 'JJ Product']
        content_results = [r for r in search_results if r.payload.get('doctype') == 'JJ Content']
        
        frappe.log_error(
            title="Search Results Debug",
            message=f"""
            Query: {questions_text}
            Has Price Filter: {bool(filter_conditions)}
            Total Results: {len(search_results)}
            Product Results: {len(product_results)}
            Content Results: {len(content_results)}
            First Result Score: {search_results[0].score if search_results else 'No results'}
            """
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
        
        contents=[]
        for result in content_results:
            payload = result.payload
            contents.append({
                "name": payload.get("id", ""),
                "title": payload.get("title", ""),
                "description": payload.get("description", ""),
                "image_url": payload.get("image_url", "")
            })
        # สร้าง context จากผลการค้นหาทั้งหมด
        context = "ข้อมูลที่เกี่ยวข้อง:\n"
        # เรียงผลการค้นหาตาม score
        all_results = (
            [(r, 'product') for r in product_results] +
            [(r, 'content') for r in content_results]
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
        
        temperature=0.2
        if all_results:  # เปลี่ยนจาก products เป็น all_results
            instruction = """You are a knowledgeable assistant. Please answer questions following these guidelines:
1. Be concise and to the point
2. For price-related questions, specify exact prices
3. For multiple items, list them with bullet points
4. Use friendly and polite Thai language
5. Include image links when asked about images
6. For products under 100 baht, emphasize value for money
7. For products with multiple sizes, recommend based on usage
8. For content/articles, highlight key information
9. Do not use any markdown formatting
10. Response must be in Thai language"""

            summary_instruction = """Summarize the information in Thai language:
1. Number of relevant items (both products and content)
2. Price range (if products)
3. Key features or information points
Note: Keep it within 2 lines, no markdown formatting"""

        else:
            instruction = """You are a helpful customer service agent. The user asked about our products/services, 
            but we couldn't find exact matching information. Please:
            1. Politely inform that we don't have the exact information
            2. Suggest how they might rephrase their question
            3. Offer to help find alternative products/information
            4. Keep the tone friendly and professional
            5. Use Thai language
            6. Do not make up any product information"""

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
            session_id=session_id,
            temperature=temperature
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
        chat_history.response_token = final_response.get("usage", {}).get("total_tokens", 0) + summary_response.get("usage", {}).get("total_tokens", 0)
        chat_history.search_results = frappe.as_json({
            "products": products,
            "content": contents,
            "timestamp": str(frappe.utils.now_datetime())
        })
        chat_history.insert(ignore_permissions=True)
        
        return {
            "text": final_response["content"],
            "summary_text": summary_response["content"],
            "products": products,
            "content": contents
        }
        
    except Exception as e:
        frappe.log_error(title="Error in reply_message", message=f"Error in reply_message: {str(e)}")
        return {
            "text": "ขออภัย เกิดข้อผิดพลาดในการประมวลผล กรุณาลองใหม่อีกครั้ง",
            "summary_text": "เกิดข้อผิดพลาด",
            "products": [],
            "content": []
        }
    

    