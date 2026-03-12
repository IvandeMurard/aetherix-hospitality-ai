from fastapi import APIRouter, Request, BackgroundTasks
from app.services.whatsapp_service import WhatsAppService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
whatsapp = WhatsAppService()

@router.post("/twilio/whatsapp")
async def twilio_whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Inbound webhook for Twilio WhatsApp messages.
    Uses BackgroundTasks for non-blocking processing.
    """
    # Twilio sends data as Form Data (x-www-form-urlencoded)
    form_data = await request.form()
    data = dict(form_data)
    
    # Process in background to respond to Twilio immediately (200 OK)
    background_tasks.add_task(whatsapp.handle_inbound_message, data)
    
    return {"status": "received"}
