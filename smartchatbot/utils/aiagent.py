import openai
import frappe

def reply_message(message):
    try:
        settings = frappe.get_doc("JJ Chatbot Settings")
        
        # สร้าง OpenAI client
        client = openai.OpenAI(
            api_key=settings.get_password("ai_api_token"),
            base_url=settings.ai_api_endpoint if settings.ai_api_endpoint else "https://api.openai.com/v1"
        )
        
        # ใช้ค่าจากการตั้งค่า
        model = settings.ai_model or "gpt-3.5-turbo"
        system_instruction = settings.ai_system_instruction or "คุณคือผู้ช่วยที่เป็นมิตรและมีประโยชน์"
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": message}
            ],
            max_tokens=1000
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        frappe.log_error(title="ChatGPT Error", message=str(e))
        return "ขออภัย ระบบมีปัญหา กรุณาลองใหม่อีกครั้ง"
    

    