# Copyright (c) 2025, jingjai soft and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import hashlib
import json
import uuid

class JJContent(Document):
	def validate(self):
		if not self.uuid:  # เพิ่มการตรวจสอบและสร้าง UUID
			self.uuid = str(uuid.uuid4())
		self.build_content_and_hash()
		
	
	def build_content_and_hash(self):
		# แปลงสถานะเป็นข้อความ
		status = "เปิดใช้งาน" if self.active else "ปิดใช้งาน"
		
		# สร้าง content ในรูปแบบ markdown
		content = f"""# {self.title}

## สถานะ
{status}

## รายละเอียด
{self.description or ''}

## ข้อมูลทั่วไป
- ประเภทเนื้อหา: {self.content_type or ''}
"""

		# เพิ่มข้อมูล product categories
		if self.product_category:
			content += "\n## หมวดหมู่สินค้าที่เกี่ยวข้อง\n"
			for cat in self.product_category:
				content += f"- {cat.category}\n"

		# เพิ่มข้อมูล industry
		if self.industry:
			content += "\n## อุตสาหกรรม\n"
			for ind in self.industry:
				content += f"- {ind.industry}\n"

		# สร้าง hash จาก content และข้อมูลสำคัญ
		hash_data = {
			"title": self.title,
			"description": self.description,
			"content_type": self.content_type,
			"product_category": [cat.category for cat in self.product_category] if self.product_category else [],
			"industry": [ind.industry for ind in self.industry] if self.industry else [],
			"active": self.active
		}
		
		# สร้าง hash จากข้อมูลทั้งหมด
		content_hash = hashlib.md5(json.dumps(hash_data, sort_keys=True).encode()).hexdigest()
		
		# เก็บค่าใน document
		self.content = content
		self.hash = content_hash
		


