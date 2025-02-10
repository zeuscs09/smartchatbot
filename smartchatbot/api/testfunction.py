import frappe

@frappe.whitelist(allow_guest=True)
def ai_test(message=None):
    from smartchatbot.utils.aiagent import reply_message
    if not message:
        return "กรุณาใส่ข้อความที่ต้องการ"
    return reply_message(message)

@frappe.whitelist()
def qdrant_test():
    from smartchatbot.utils.qdrant import QdrantManager
    qdrant = QdrantManager()
    r = qdrant.sync_content_and_products()
    return r
