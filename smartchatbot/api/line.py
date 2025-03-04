import frappe
import json
from frappe import _
from frappe.utils import get_request_session

@frappe.whitelist(allow_guest=True)
def webhook():
    if frappe.request.method != "POST":
        frappe.throw(_("Method not allowed"), frappe.PermissionError)
    
    try:
        # Get the raw data from the request
        data = json.loads(frappe.request.data)
        
        # Create new JJ Webhook document
        doc = frappe.new_doc("JJ Webhook")
        
        # Set the raw data
        doc.raw_data = data
        
        # Extract group ID and user ID from the first event if available
        events = data.get("events", [])
        if events and "source" in events[0]:
            source = events[0]["source"]
            if "groupId" in source:
                doc.groupid = source["groupId"]
            if "userId" in source:
                doc.userid = source["userId"]
        
        # Save the document
        doc.insert(ignore_permissions=True)
        
        return {"status": "success"}
        
    except Exception as e:
        frappe.log_error(title="LINE Webhook Error", message=f"LINE Webhook Error: {str(e)}")
        return {"status": "error", "message": str(e)} 