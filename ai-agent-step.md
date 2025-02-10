# AI Agent Flow

## 1. Intent Classification
แยกประเภทคำถามเป็น 3 กลุ่ม:
- Product Intent: คำถามเกี่ยวกับสินค้า ราคา สต็อก โปรโมชั่น
- Content Intent: คำถามเกี่ยวกับบทความ ข้อมูลความรู้ เนื้อหาทั่วไป  
- General Intent: การทักทาย สอบถามบริการทั่วไป

## 2. Vector Database (Qdrant)
แยก collection ตาม intent:
- `smartchat_product`: เก็บ vectors ของข้อมูลสินค้า
- `smartchat_content`: เก็บ vectors ของ content

## 3. Flow การทำงาน
1. รับคำถามจากผู้ใช้
2. ส่งคำถามไป classify intent ด้วย OpenAI
3. ตามประเภท intent:
   - Product: ค้นหาใน product collection
   - Content: ค้นหาใน content collection  
   - General: ตอบกลับด้วย template ที่เตรียมไว้
4. จัดรูปแบบคำตอบตามประเภทข้อมูล
5. ส่งผลลัพธ์กลับให้ผู้ใช้

## 4. ระบบที่ต้องเตรียม
- OpenAI API สำหรับ:
  - Intent classification
  - Text embedding
- Qdrant server สำหรับ vector search
- ระบบ sync ข้อมูลเข้า Qdrant เมื่อข้อมูลมีการเปลี่ยนแปลง

## 5. ข้อควรระวัง
- ต้องอัพเดท vectors เมื่อข้อมูลมีการเปลี่ยนแปลง
- ควรมีการจัดการ error cases
- อาจต้องปรับแต่งการแยก Intent ให้เหมาะกับธุรกิจ
