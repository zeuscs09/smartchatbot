import frappe
import uuid
@frappe.whitelist(allow_guest=True)
def ai_test(message=None):
    from smartchatbot.utils.aiagent import reply_message
    if not message:
        return "กรุณาใส่ข้อความที่ต้องการ"
    session_id = "9cf855f5-43ac-414d-a323-445852d9d748"
    return reply_message(message, session_id)

@frappe.whitelist()
def qdrant_test():
    from smartchatbot.utils.qdrant import QdrantManager
    qdrant = QdrantManager()
    r = qdrant.sync_content_and_products()
    return r
