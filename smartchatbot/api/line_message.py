import frappe
from frappe import _
from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

def create_message_handler(doc, handler, configuration):
    @handler.add(MessageEvent, message=TextMessageContent)
    def handle_message(event):
        # อัพเดทข้อมูลเพิ่มเติม
        doc.message_id = event.message.id
        doc.user_id = event.source.user_id
        doc.message_type = "text"
        doc.message_text = event.message.text
        
        # ส่งข้อความตอบกลับ
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            reply_text = f"Hello, User ID: {event.source.user_id}"
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
            
            # บันทึกข้อความตอบกลับพร้อมเวลา
            doc.response_text = reply_text
            doc.response_time = frappe.utils.now_datetime()
            doc.save(ignore_permissions=True)
    return handle_message

@frappe.whitelist(allow_guest=True)
def webhook():
    if frappe.request.method != "POST":
        frappe.throw(_("Method not allowed"), frappe.PermissionError)
    
    # รับค่า signature และ body
    signature = frappe.get_request_header("X-Line-Signature")
    if not signature:
        frappe.throw(_("Missing X-Line-Signature header"))
        
    body = frappe.request.get_data(as_text=True)
    if not body:
        frappe.throw(_("Empty request body"))
    
    try:
        # ดึงการตั้งค่าจาก JJ Chatbot Settings
        settings = frappe.get_doc("JJ Chatbot Settings")
        line_secret = settings.line_secret
        line_token = settings.get_password("line_access_token")
        
        # บันทึก payload และ timestamp ก่อน
        doc = frappe.get_doc({
            "doctype": "JJ Line Webhook Log",
            "timestamp": frappe.utils.now_datetime(),
            "payload": body
        })
        doc.insert(ignore_permissions=True)
        
        # ตั้งค่า LINE API
        configuration = Configuration(access_token=line_token)
        handler = WebhookHandler(line_secret)
        
        # สร้าง handler function
        handle_message = create_message_handler(doc, handler, configuration)
        
        # ตรวจสอบ signature
        handler.handle(body, signature)
        
    except InvalidSignatureError:
        frappe.log_error(title="LINE Webhook Error", message=f"Invalid signature")
    except Exception as e:
        frappe.log_error(title="LINE Webhook Error", message=f"LINE Webhook Error: {str(e)}")
        return "Error"
    
    return "OK" 