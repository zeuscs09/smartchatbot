import frappe
from frappe import _
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, 
    TextMessage, 
    TextSendMessage
)

@frappe.whitelist(allow_guest=True)
def webhook():
    if frappe.request.method != "POST":
        frappe.throw(_("Method not allowed"), frappe.PermissionError)
    
    # รับค่า signature และ body
    signature = frappe.get_request_header("X-Line-Signature")
    body = frappe.request.get_data(as_text=True)
    
    frappe.log_error(title="LINE Webhook", message=f"LINE Webhook: {body}")
    frappe.log_error(title="LINE Webhook", message=f"LINE Webhook: {signature}")
    
    try:
        # ดึงการตั้งค่าจาก JJ Chatbot Settings
        settings = frappe.get_doc("JJ Chatbot Settings")
        line_secret = settings.line_secret
        line_token = settings.get_password("line_access_token")
        
        # ตั้งค่า LINE API
        line_bot_api = LineBotApi(line_token)
        handler = WebhookHandler(line_secret)
        
        # ตรวจสอบ signature
        handler.handle(body, signature)
        
        # กำหนด handler function
        @handler.add(MessageEvent, message=TextMessage)
        def handle_message(event):
            # บันทึกข้อความลง DocType
            doc = frappe.get_doc({
                "doctype": "JJ Line Webhook Log",
                "message_id": event.message.id,
                "user_id": event.source.user_id,
                "message_type": "text",
                "message_text": event.message.text,
                "timestamp": frappe.utils.now_datetime(),
                "payload": body
            })
            doc.insert(ignore_permissions=True)
            
            # ส่งข้อความตอบกลับ
            reply_text = f"Hello, User ID: {event.source.user_id}"
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply_text)
            )
            
            # บันทึกข้อความตอบกลับพร้อมเวลา
            doc.response_text = reply_text
            doc.response_time = frappe.utils.now_datetime()
            doc.save(ignore_permissions=True)
        
    except InvalidSignatureError:
        frappe.log_error(title="LINE Webhook Error", message=f"Invalid signature")
    except Exception as e:
        frappe.log_error(title="LINE Webhook Error", message=f"LINE Webhook Error: {str(e)}")
        return "Error"
    
    return "OK" 