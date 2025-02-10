import frappe

def get_context(context):
    """ดึงข้อมูลสินค้าจาก Doctype JJ Product"""
    try:
        # เพิ่ม debug log
        frappe.log_error(f"Form dict: {frappe.form_dict}")
        
        # แก้ไขการดึง product_name
        product_name = frappe.form_dict.get('product_name')
        frappe.log_error(f"Product name: {product_name}")
        
        if not product_name:
            context.error = "กรุณาระบุรหัสสินค้า"
            frappe.log_error("No product name provided")
            return context
            
        # เพิ่ม debug log
        frappe.log_error(f"Fetching product: {product_name}")
        product = frappe.get_doc("JJ Product", product_name)
        
        if not product:
            context.error = f"ไม่พบสินค้ารหัส {product_name}"
            frappe.log_error(f"Product not found: {product_name}")
            return context
            
        # แปลง relative URL เป็น absolute URL
        if product.image and not product.image.startswith('http'):
            product.image = frappe.utils.get_url(product.image)
            
        # ดึง LINE ID จาก settings (ถ้ามี)
        line_id = frappe.db.get_single_value('Line Settings', 'line_channel_id') or "YOUR_LINE_ID"
            
        # เพิ่ม debug log
        frappe.log_error(f"Context being set with product: {product.name}")
        
        context.update({
            'product': product,
            'line_id': line_id,
            'no_cache': 1,
            'no_sidebar': 1
        })
        
    except Exception as e:
        frappe.log_error(f"Error in line/index.py: {str(e)}")
        context.error = "เกิดข้อผิดพลาดในการดึงข้อมูลสินค้า"
        
    # เพิ่ม debug log
    frappe.log_error(f"Final context: {context}")
    return context