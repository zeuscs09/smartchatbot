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
    TextMessage,
    FlexMessage,
    FlexContainer
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)
from smartchatbot.utils.aiagent import reply_message

def create_message_handler(doc, handler, configuration):
    @handler.add(MessageEvent, message=TextMessageContent)
    def handle_message(event):
        try:
            frappe.log_error(title="LINE Debug", message=f"Starting handle_message with event: {event}")
            
            # อัพเดทข้อมูลเพิ่มเติม
            doc.message_id = event.message.id
            doc.user_id = event.source.user_id
            doc.message_type = "text"
            doc.message_text = event.message.text
            
            # ใช้ ChatGPT ตอบกลับ
            user_message = event.message.text
            response = reply_message(user_message, doc.user_id)
            
            messages = []
            if isinstance(response, dict) and 'products' in response:
                # สร้าง Flex Message สำหรับแสดงสินค้า
                flex_contents = {
                    "type": "carousel",
                    "contents": []
                }
                
                for product in response['products']:
                    bubble = {
                        "type": "bubble",
                        "hero": {
                            "type": "image",
                            "url": product['image_url'],
                            "size": "full",
                            "aspectRatio": "20:13",
                            "aspectMode": "cover"
                        },
                        "body": {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": product['title'],
                                    "weight": "bold",
                                    "size": "md",
                                    "wrap": True
                                },
                                {
                                    "type": "text",
                                    "text": f"ราคา: {product['price']} บาท",
                                    "size": "sm",
                                    "color": "#555555"
                                },
                                {
                                    "type": "text",
                                    "text": product['description'],
                                    "size": "xs",
                                    "color": "#555555",
                                    "wrap": True,
                                    "maxLines": 5
                                }
                            ]
                        }
                    }
                    flex_contents["contents"].append(bubble)
                
                messages.append(
                    FlexMessage(
                        alt_text="รายการสินค้า",
                        contents=FlexContainer.from_dict(flex_contents)
                    )
                )
                
                # เพิ่มข้อความอธิบายถ้ามี
                if 'text' in response:
                    messages.append(TextMessage(text=response['text']))
                    
                reply_text = response.get('text', 'ดูรายการสินค้าด้านบนค่ะ')
            else:
                messages.append(TextMessage(text=response))
                reply_text = response
            
            # ส่งข้อความตอบกลับ
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                
                frappe.log_error(title="LINE Debug", 
                               message=f"Attempting to reply with messages: {messages}")
                
                response = line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=messages
                    )
                )
            
            # บันทึกข้อความตอบกลับพร้อมเวลา
            doc.response_text = reply_text
            doc.response_time = frappe.utils.now_datetime()
            doc.save(ignore_permissions=True)
            
            frappe.log_error(title="LINE Debug", message="Message handled successfully")
            
        except Exception as e:
            frappe.log_error(title="LINE Message Handler Error", 
                           message=f"Error in handle_message: {str(e)}\nEvent: {event}")
            raise e
            
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