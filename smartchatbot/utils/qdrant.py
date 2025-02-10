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
        """สร้าง collections สำหรับ content และ product"""
        collections = ["jj_content", "jj_product"]
        for collection in collections:
            try:
                # ตรวจสอบว่ามี collection อยู่แล้วหรือไม่
                try:
                    self.client.get_collection(collection)
                    frappe.logger().debug(f"Collection {collection} exists")
                except UnexpectedResponse as e:
                    if "not found" in str(e).lower():
                        # สร้าง collection ใหม่
                        self.client.create_collection(
                            collection_name=collection,
                            vectors_config=models.VectorParams(
                                size=1536,
                                distance=models.Distance.COSINE
                            )
                        )
                        frappe.logger().info(f"Created collection {collection}")
                    else:
                        raise e
                        
            except Exception as e:
                frappe.log_error(
                    message=f"Error initializing collection {collection}: {str(e)}",
                    title="Qdrant Collection Error"
                )
                raise Exception(f"ไม่สามารถสร้าง collection {collection}: {str(e)}")

    def get_embedding(self, text):
        """สร้าง embedding vector โดยใช้ OpenAI API"""
        return self.ai_client.get_embedding(text)

    def sync_content_and_products(self):
        """Sync JJ Content และ JJ Product ที่มี hash ไม่ตรงกับ hash_ai"""
        try:
            # ดึงข้อมูล JJ Content ที่ต้อง sync
            content_to_sync = frappe.db.sql("""
                SELECT * FROM `tabJJ Content`
                WHERE active = 1 
                AND hash != ''
                AND (hash_ai IS NULL OR hash_ai != hash)
            """, as_dict=1)

            # ดึงข้อมูล JJ Product ที่ต้อง sync
            products_to_sync = frappe.db.sql("""
                SELECT * FROM `tabJJ Product`
                WHERE active = 1 
                AND hash != ''
                AND (hash_ai IS NULL OR hash_ai != hash)
            """, as_dict=1)

            # Sync JJ Content
            for content in content_to_sync:
                try:
                    doc = frappe.get_doc("JJ Content", content.name)
                    
                    # สร้าง text สำหรับ embedding
                    content_text =doc.content
                    
                    # สร้าง vector
                    vector = self.get_embedding(content_text)
                    
                    # สร้าง payload
                    product_categories = [row.category for row in doc.product_category]
                    industries = [row.industry for row in doc.industry]
                    
                    # แปลง image path เป็น full URL
                    image_url = get_url(doc.image) if doc.image else None
                    
                    payload = {
                        "id": doc.name,
                        "title": doc.title,
                        "description": doc.description,
                        "content": doc.content,
                        "content_type": doc.content_type,
                        "product_categories": product_categories,
                        "industries": industries,
                        "image_url": image_url,
                        "doctype": "JJ Content",
                        "text_for_search": content_text
                    }

                    # อัพเดทหรือเพิ่มข้อมูลใน Qdrant ด้วย UUID
                    self.client.upsert(
                        collection_name="jj_content",
                        points=[models.PointStruct(
                            id=doc.uuid,  # สร้าง UUID ใหม่
                            vector=vector,
                            payload=payload
                        )]
                    )

                    # อัพเดท hash_ai
                    doc.hash_ai = doc.hash
                    doc.save(ignore_permissions=True)
                    frappe.db.commit()
                    
                except Exception as e:
                    error_msg = str(e)[:500]
                    frappe.log_error(
                        message=f"Error syncing content {content.name}: {error_msg}",
                        title="Qdrant Content Sync Error"
                    )

            # Sync JJ Product
            for product in products_to_sync:
                try:
                    doc = frappe.get_doc("JJ Product", product.name)
                    
                    # สร้าง text สำหรับ embedding
                    product_text = doc.content
                    
                    # สร้าง vector
                    vector = self.get_embedding(product_text)
                    
                    # สร้าง payload
                    industries = [row.industry for row in doc.industry]
                    
                    # แปลง image path เป็น full URL
                    image_url = get_url(doc.image) if doc.image else None
                    
                    payload = {
                        "id": doc.name,
                        "title": doc.title,
                        "description": doc.description,
                        "content": doc.content,
                        "product_category": doc.product_category,
                        "industries": industries,
                        "price": doc.price,
                        "image_url": image_url,
                        "doctype": "JJ Product",
                        "text_for_search": product_text
                    }

                    # อัพเดทหรือเพิ่มข้อมูลใน Qdrant ด้วย UUID
                    self.client.upsert(
                        collection_name="jj_product",
                        points=[models.PointStruct(
                            id=doc.uuid,  # สร้าง UUID ใหม่
                            vector=vector,
                            payload=payload
                        )]
                    )

                    # อัพเดท hash_ai
                    doc.hash_ai = doc.hash
                    doc.save(ignore_permissions=True)
                    frappe.db.commit()
                    
                except Exception as e:
                    error_msg = str(e)[:500]
                    frappe.log_error(
                        message=f"Error syncing product {product.name}: {error_msg}",
                        title="Qdrant Product Sync Error"
                    )

            return {
                "content_synced": len(content_to_sync),
                "products_synced": len(products_to_sync)
            }
            
        except Exception as e:
            frappe.log_error(str(e), "Qdrant Sync Error")
            raise e

