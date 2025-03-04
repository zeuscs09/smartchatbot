import frappe
import json
from frappe import _
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    TextMessage
)

@frappe.whitelist(allow_guest=True)
def webhook():
    if frappe.request.method != "POST":
        frappe.throw(_("Method not allowed"), frappe.PermissionError)
    
    try:
        # Get the raw data from the request and format it nicely
        data = json.loads(frappe.request.data)
        formatted_data = json.loads(json.dumps(data, indent=4))
        
        # Create new JJ Webhook document
        doc = frappe.new_doc("JJ Webhook")
        
        # Set the formatted raw data
        doc.raw_data = formatted_data
        
        # Extract group ID, user ID and message text from the first event if available
        events = data.get("events", [])
        if events and "source" in events[0]:
            source = events[0]["source"]
            if "groupId" in source:
                doc.groupid = source["groupId"]
            if "userId" in source:
                doc.userid = source["userId"]
            
            # Extract message text if it's a text message
            if "message" in events[0] and events[0]["message"]["type"] == "text":
                doc.message_text = events[0]["message"]["text"]
        
        # Save the document
        doc.insert(ignore_permissions=True)
        
        return {"status": "success"}
        
    except Exception as e:
        frappe.log_error(title="LINE Webhook Error", message=f"LINE Webhook Error: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def push_message(channel_id, message, source_id):
    """
    Push message to LINE user or group using channel settings and send mapping
    Args:
        channel_id (str): Channel ID from JJ Channel Setting
        message (str): Message to send
        source_id (str): Source ID to lookup in JJ Send Mapping
    """
    try:
        # Log incoming parameters
        frappe.log_error(
            title="LINE Push Message Debug",
            message=f"Incoming parameters - Channel: {channel_id}, Source: {source_id}, Message: {message}"
        )
        
        # Get channel settings
        channel = frappe.get_doc("JJ Channel Setting", channel_id)
        if not channel:
            frappe.throw(_("Channel not found"))
            
        # Get send mapping
        send_mapping = frappe.get_list("JJ Send Mapping",
            filters={
                "channel": channel_id,
                "source_id": source_id
            },
            fields=["send_to_id"]
        )
        
        if not send_mapping:
            frappe.throw(_("Send mapping not found for given source ID"))
            
        send_to_id = send_mapping[0].send_to_id
        
        # Log mapping info
        frappe.log_error(
            title="LINE Push Message Debug",
            message=f"Mapping found - Send to ID: {send_to_id}"
        )
        
        # Verify channel secret key and use it as token
        if not channel.channel_secret_key:
            frappe.throw(_("Channel secret key not configured"))
        
        # Configure LINE API
        configuration = Configuration(
            access_token=channel.channel_secret_key
        )
        
        # Create message object
        messages = [TextMessage(text=message)]
        
        # Log request details
        frappe.log_error(
            title="LINE Push Message Debug",
            message=f"Preparing to send message to: {send_to_id}"
        )
        
        # Send message using LINE Bot SDK
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            response = line_bot_api.push_message(
                PushMessageRequest(
                    to=send_to_id,
                    messages=messages
                )
            )
            
            # Log success
            frappe.log_error(
                title="LINE Push Message Debug",
                message=f"Message sent successfully"
            )
            
            return {
                "status": "success",
                "channel": channel_id,
                "source_id": source_id,
                "send_to_id": send_to_id
            }
            
    except Exception as e:
        error_message = f"""
        Channel: {channel_id}
        Source: {source_id}
        Send To ID: {send_to_id if 'send_to_id' in locals() else 'Not found'}
        Error: {str(e)}
        """
        frappe.log_error(
            title="LINE Push Message Error",
            message=error_message
        )
        return {"status": "error", "message": str(e)} 