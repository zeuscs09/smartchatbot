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
            frappe.log_error(title="LINE Debug", message=f"Response: {response}")
            messages = []
            if isinstance(response, dict):
                # ส่ง summary_text ก่อนเสมอถ้ามี
                if 'summary_text' in response and response['summary_text']:
                    messages.append(TextMessage(text=response['summary_text']))
                    reply_text = response['summary_text']
                # ถ้าไม่มี summary_text จึงใช้ text
                elif 'text' in response and response['text']:
                    messages.append(TextMessage(text=response['text']))
                    reply_text = response['text']
                
                # ถ้ามี products จึงแสดง flex message สำหรับสินค้า
                if 'products' in response and response['products']:
                    flex_contents = {
                        "type": "carousel",
                        "contents": []
                    }
                    
                    for product in response['products']:
                        # ตรวจสอบและแปลง image URL
                        image_url = product.get('image_url', '')
                        if image_url and not image_url.startswith('http'):
                            image_url = frappe.utils.get_url(image_url)
                        
                        bubble = {
                            "type": "bubble",
                            "hero": {
                                "type": "image",
                                "url": image_url,
                                "size": "full",
                                "aspectRatio": "20:13",
                                "aspectMode": "cover"
                            },
                            "body": {
                                "type": "box",
                                "layout": "vertical",
                                "spacing": "sm",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": product.get('title', ''),
                                        "weight": "bold",
                                        "size": "md",
                                        "wrap": True
                                    },
                                    {
                                        "type": "text",
                                        "text": f"฿{product.get('price', 0):,.0f}",
                                        "size": "xl",
                                        "weight": "bold",
                                        "color": "#D53600"
                                    }
                                ]
                            },
                            "footer": {
                                "type": "box",
                                "layout": "vertical",
                                "spacing": "sm",
                                "contents": [
                                    {
                                        "type": "button",
                                        "action": {
                                            "type": "uri",
                                            "label": "ดูรายละเอียด",
                                            "uri": f"{frappe.utils.get_url()}/line/products/{product.get('name', '')}"
                                        },
                                        "style": "primary"
                                    }
                                ]
                            }
                        }
                        flex_contents["contents"].append(bubble)
                    
                    if flex_contents["contents"]:
                        messages.append(
                            FlexMessage(
                                alt_text="รายการสินค้า",
                                contents=FlexContainer.from_dict(flex_contents)
                            )
                        )
                
                # เพิ่ม flex message สำหรับ content
                if 'content' in response and response['content']:
                    content_flex = {
                        "type": "carousel",
                        "contents": []
                    }
                    
                    for content in response['content']:
                        # ตรวจสอบและแปลง image URL
                        image_url = content.get('image_url', '')
                        if image_url and not image_url.startswith('http'):
                            image_url = frappe.utils.get_url(image_url)
                        
                        bubble = {
                            "type": "bubble",
                            "hero": {
                                "type": "image",
                                "url": image_url,
                                "size": "full",
                                "aspectRatio": "20:13",
                                "aspectMode": "cover"
                            },
                            "body": {
                                "type": "box",
                                "layout": "vertical",
                                "spacing": "sm",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": content.get('title', ''),
                                        "weight": "bold",
                                        "size": "md",
                                        "wrap": True
                                    }
                                ]
                            },
                            "footer": {
                                "type": "box",
                                "layout": "vertical",
                                "spacing": "sm",
                                "contents": [
                                    {
                                        "type": "button",
                                        "action": {
                                            "type": "uri",
                                            "label": "ดูรายละเอียด",
                                            "uri": f"{frappe.utils.get_url()}/line/content/{content.get('name', '')}"
                                        },
                                        "style": "primary"
                                    }
                                ]
                            }
                        }
                        content_flex["contents"].append(bubble)
                    
                    if content_flex["contents"]:
                        messages.append(
                            FlexMessage(
                                alt_text="บทความที่เกี่ยวข้อง",
                                contents=FlexContainer.from_dict(content_flex)
                            )
                        )
                elif not messages:  # ถ้าไม่มีทั้ง text และ products
                    messages.append(TextMessage(text="ขออภัยค่ะ ไม่พบข้อมูลที่ต้องการ"))
                    reply_text = "ไม่พบข้อมูล"
            else:
                messages.append(TextMessage(text=str(response)))
                reply_text = str(response)
            
            # ส่งข้อความตอบกลับ
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
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