import frappe
from frappe import _
from frappe.utils import get_url
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse
from urllib.parse import urlparse
from .ai_client import AIClient
import uuid

class QdrantManager:
    def __init__(self):
        try:
            # ดึงการตั้งค่าทั้งหมดจาก JJ Chatbot Settings
            settings = frappe.get_single("JJ Chatbot Settings")
            self.ai_client = AIClient.get_instance()
            
            if not settings.qdrant_endpoint:
                raise Exception("กรุณาตั้งค่า Qdrant Endpoint ใน JJ Chatbot Settings")
            
            if not settings.qdrant_token:
                raise Exception("กรุณาตั้งค่า Qdrant Token สำหรับ Qdrant Cloud")
            
            # สร้าง Qdrant client สำหรับ cloud
            
            self.client = QdrantClient(
                url=settings.qdrant_endpoint,  # ใช้ url แทน host/port
                api_key=settings.get_password("qdrant_token"),
                timeout=10
            )
          
            # เก็บค่า AI model สำหรับใช้งานต่อ
            self.ai_embedding_model = settings.ai_embedding_model or "text-embedding-3-small"
            
            # สร้าง collections ถ้ายังไม่มี
            self._init_collections()
            
        except Exception as e:
            frappe.log_error(
                message=f"Qdrant initialization error: {str(e)}\n"
                f"Endpoint: {settings.qdrant_endpoint}",
                title="Qdrant Connection Error"
            )
            raise Exception(f"ไม่สามารถเชื่อมต่อกับ Qdrant ได้: {str(e)}")

    def _init_collections(self):
        """สร้าง collection เดียวสำหรับทั้ง content และ product"""
        try:
            # ตรวจสอบว่ามี collection อยู่แล้วหรือไม่
            try:
                self.client.get_collection("jj_data")
                frappe.logger().debug("Collection jj_data exists")
            except UnexpectedResponse as e:
                if "not found" in str(e).lower():
                    # สร้าง collection ใหม่
                    self.client.create_collection(
                        collection_name="jj_data",
                        vectors_config=models.VectorParams(
                            size=1536,
                            distance=models.Distance.COSINE
                        )
                    )
                    frappe.logger().info("Created collection jj_data")
                else:
                    raise e
                    
        except Exception as e:
            frappe.log_error(
                message=f"Error initializing collection jj_data: {str(e)}",
                title="Qdrant Collection Error"
            )
            raise Exception(f"ไม่สามารถสร้าง collection: {str(e)}")

    def get_embedding(self, text):
        """สร้าง embedding vector โดยใช้ OpenAI API"""
        return self.ai_client.get_embedding(text)

    def sync_content_and_products(self):
        """Sync JJ Content และ JJ Product เข้า collection เดียวกัน"""
        try:
            # ดึงข้อมูลที่ต้อง sync
            content_to_sync = frappe.db.sql("""
                SELECT * FROM `tabJJ Content`
                WHERE active = 1 
                AND hash != ''
                AND (hash_ai IS NULL OR hash_ai != hash)
            """, as_dict=1)

            products_to_sync = frappe.db.sql("""
                SELECT * FROM `tabJJ Product`
                WHERE active = 1 
                AND hash != ''
                AND (hash_ai IS NULL OR hash_ai != hash)
            """, as_dict=1)

            points = []

            # เตรียมข้อมูล Content
            for content in content_to_sync:
                try:
                    doc = frappe.get_doc("JJ Content", content.name)
                    content_text = doc.content
                    vector = self.get_embedding(content_text)
                    
                    payload = {
                        "id": doc.name,
                        "title": doc.title,
                        "description": doc.description,
                        "content": doc.content,
                        "content_type": doc.content_type,
                        "product_categories": [row.category for row in doc.product_category],
                        "industries": [row.industry for row in doc.industry],
                        "image_url": get_url(doc.image) if doc.image else None,
                        "doctype": "JJ Content",
                        "text_for_search": content_text
                    }
                    
                    points.append(models.PointStruct(
                        id=doc.uuid,
                        vector=vector,
                        payload=payload
                    ))
                    
                    doc.hash_ai = doc.hash
                    doc.save(ignore_permissions=True)
                    
                except Exception as e:
                    frappe.log_error(f"Error syncing content {content.name}: {str(e)}")

            # เตรียมข้อมูล Product
            for product in products_to_sync:
                try:
                    doc = frappe.get_doc("JJ Product", product.name)
                    product_text = doc.content
                    vector = self.get_embedding(product_text)
                    
                    payload = {
                        "id": doc.name,
                        "title": doc.title,
                        "description": doc.description,
                        "content": doc.content,
                        "price": doc.price,
                        "product_category": doc.product_category,
                        "industries": [row.industry for row in doc.industry],
                        "image_url": get_url(doc.image) if doc.image else None,
                        "doctype": "JJ Product",
                        "text_for_search": product_text
                    }
                    
                    points.append(models.PointStruct(
                        id=doc.uuid,
                        vector=vector,
                        payload=payload
                    ))
                    
                    doc.hash_ai = doc.hash
                    doc.save(ignore_permissions=True)
                    
                except Exception as e:
                    frappe.log_error(f"Error syncing product {product.name}: {str(e)}")

            # อัพเดทข้อมูลทั้งหมดใน collection เดียว
            if points:
                self.client.upsert(
                    collection_name="jj_data",
                    points=points
                )

            return {
                "content_synced": len(content_to_sync),
                "products_synced": len(products_to_sync)
            }
            
        except Exception as e:
            frappe.log_error(str(e), "Qdrant Sync Error")
            raise e

