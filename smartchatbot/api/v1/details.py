import frappe

@frappe.whitelist(allow_guest=True)
def get_product(name=None):
    if not name:
        frappe.throw("Product name is required")
    
    try:
        product = frappe.get_doc("JJ Product", name)
        return {
            "message": {
                "name": product.name,
                "title": product.title,
                "price": product.price,
                "image": product.image,
                "product_category": product.product_category,
                "description": product.description,
                "industry": [{"industry": i.industry} for i in product.industry]
            }
        }
    except frappe.DoesNotExistError:
        frappe.throw("Product not found")

@frappe.whitelist(allow_guest=True)
def get_content(name=None):
    if not name:
        frappe.throw("Content name is required")
    
    try:
        content = frappe.get_doc("JJ Content", name)
        return {
            "message": {
                "name": content.name,
                "title": content.title,
                "content_type": content.content_type,
                "image": content.image,
                "description": content.description,
                "content": content.content,
                "product_categories": [{"category": pc.category} for pc in content.product_category],
                "industries": [{"industry": i.industry} for i in content.industry]
            }
        }
    except frappe.DoesNotExistError:
        frappe.throw("Content not found")
