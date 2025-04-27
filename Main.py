from fastapi import FastAPI, Request, Response, Form
from twilio.rest import Client
from twilio.request_validator import RequestValidator
from dotenv import load_dotenv
import os
import logging
from typing import Optional, List
import json
import requests
import tempfile
import re
from Agentic_System import sql_agent, chat_agent, intro_agent, mediator_agent, pdf_agent, summary_agent
from db import execute_query, init_db
from email_agent import EmailToolsWithAttachments, Agent, Gemini
from datetime import datetime

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
TWILIO_WHATSAPP_NUMBER = "whatsapp:+14155238886"

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
validator = RequestValidator(TWILIO_AUTH_TOKEN)

MOCK_MODE = False

async def verify_twilio_request(request: Request) -> bool:
    try:
        url = str(request.url)
        form_data = await request.form()
        signature = request.headers.get("X-Twilio-Signature", "")
        
        logger.debug(f"Validating request - URL: {url}")
        logger.debug(f"Form data: {form_data}")
        logger.debug(f"Twilio signature: {signature}")
        
        is_valid = validator.validate(url, form_data, signature)
        logger.debug(f"Request validation result: {is_valid}")
        return is_valid
    except Exception as e:
        logger.error(f"Error validating request: {e}", exc_info=True)
        return False

@app.get("/")
async def root():
    logger.info("Root endpoint hit")
    return {"message": "Email Assistant System is running"}

init_db()

def send_whatsapp_message(body, to_number):
    """Send WhatsApp message with mock mode support"""
    try:
        if MOCK_MODE:
            logger.info(f"MOCK MODE: Would send message to {to_number}: {body}")
            return {"sid": "MOCK_SID_" + str(hash(body))[:8]}
        else:
            response = twilio_client.messages.create(
                from_=TWILIO_WHATSAPP_NUMBER,
                body=body,
                to=to_number
            )
            return response
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return {"sid": "ERROR_SID", "error": str(e)}

def download_file(url, local_path):
    """Download a file from a URL to a local path with Twilio authentication"""
    try:

        auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        logger.info(f"Attempting to download file from: {url}")
        response = requests.get(url, auth=auth)
        response.raise_for_status()
        
        with open(local_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"File downloaded successfully to {local_path}")
        return True
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return False

def send_email(recipient_email, subject, body, attachment_path=None):
    """Send an email using the EmailToolsWithAttachments"""
    try:
        
        sender_email = os.getenv("SENDER_EMAIL", "zainxaidi2003@gmail.com")
        sender_name = os.getenv("SENDER_NAME", "Zain Raza")
        sender_passkey = os.getenv("SENDER_PASSKEY", "fvft xjpw pdoz onlk")
        
    
        agent = Agent(
            tools=[
                EmailToolsWithAttachments(
                    receiver_email=recipient_email,
                    sender_email=sender_email,
                    sender_name=sender_name,
                    sender_passkey=sender_passkey,
                )
            ],
            model=Gemini(model="gemini-1.5-flash")
        )
        
        if attachment_path:
            command = f"send an email with a subject '{subject}' and body '{body}' with attachments ['{attachment_path}']"
        else:
            command = f"send an email with a subject '{subject}' and body '{body}'"
        
        response = agent.run(command, markdown=True)
        logger.info(f"Email sending response: {response.content}")
        
        return "email sent successfully" in response.content
    except Exception as e:
        logger.error(f"Error sending email: {e}", exc_info=True)
        return False

def generate_email_body(subject, attachment_path=None, recipient_email=None):
    """Generate an email body based on the resume and subject"""
    try:
        # If no attachment path is provided, return the default template
        if not attachment_path:
            logger.warning("No attachment path provided, using default email template")
            return get_default_email_template(subject)
        
        # Process the PDF
        processing_result = pdf_agent.process_pdf(attachment_path)
        logger.info(f"PDF processing result: {processing_result}")
        
        # Handle different processing results
        if processing_result.get("status") == "success":
            # Query for relevant chunks
            query_text = f"job application for {subject}"
            results = pdf_agent.query_collection(query_text)
            
            if results and results.get("documents") and results["documents"][0]:
                # Generate email content using the summary agent
                email_content = summary_agent.generate_email_content(
                    resume_chunks=results["documents"][0],
                    job_subject=subject,
                    recipient_email=recipient_email
                )
                return email_content
        elif processing_result.get("status") == "partial_success" and processing_result.get("text"):
            # Use the extracted text directly with the summary agent
            logger.info("Using extracted text directly with summary agent")
            email_content = summary_agent.generate_email_content(
                resume_chunks=[processing_result.get("text")],
                job_subject=subject,
                recipient_email=recipient_email
            )
            return email_content
        
        # Fallback to default template if processing fails
        logger.warning("Using default email template as PDF processing failed")
        return get_default_email_template(subject)
    except Exception as e:
        logger.error(f"Error generating email body: {e}", exc_info=True)
        # Return default template if there's an error
        return get_default_email_template(subject)

def get_default_email_template(subject):
    """Return a default email template"""
    return """Dear Hiring Manager,

I am excited to apply for the position mentioned in the subject line. Please find my resume attached for your consideration.

Best regards,
Zain Raza
Lahore, Pakistan
📧 zainxaidi2003@gmail.com | 📞 0306-5187343"""

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Webhook endpoint for WhatsApp messages - Email Assistant System
    """
    print('Webhook hit')
    try:
        form_data = await request.form()
        form_dict = dict(form_data)
        logger.debug(f"Received WhatsApp webhook data: {form_dict}")

        from_number = form_dict.get("From", "")
        body = form_dict.get("Body", "")
        wa_id = form_dict.get("WaId", "")
        
        num_media = int(form_dict.get("NumMedia", "0"))
        media_content_types = []
        media_urls = []
        
        for i in range(num_media):
            media_content_type = form_dict.get(f"MediaContentType{i}")
            media_url = form_dict.get(f"MediaUrl{i}")
            
            if media_content_type and media_url:

                if media_content_type.lower() == 'application/pdf':
                    media_content_types.append(media_content_type)
                    media_urls.append(media_url)
                    logger.info(f"Received PDF: {media_url}")
                else:
                    logger.warning(f"Received non-PDF media: {media_content_type}")
        
        logger.info(f"WhatsApp message received - From: {from_number}, Body: {body}, WaId: {wa_id}")
        
        if wa_id:
            try:
                clean_number = from_number.replace("whatsapp:", "")
                
                sql_query = sql_agent.generate_query(clean_number)
                logger.info(f"Generated SQL query for user check: {sql_query}")
                
                user_result = execute_query(sql_query)
                logger.debug(f"User query result: {user_result}")
                
                if not user_result or not user_result[0].get("is_member", 0):
                    logger.info(f"User not found or not a member: {clean_number}")
                    response = twilio_client.messages.create(
                        from_=TWILIO_WHATSAPP_NUMBER,
                        body="You are not subscribed to our membership. Please contact zainxaidi2003@gmail.com for membership details.",
                        to=from_number
                    )
                    logger.info(f"Non-member message sent with SID: {response.sid}")
                    return Response(
                        content="<?xml version='1.0' encoding='UTF-8'?><Response></Response>",
                        media_type="application/xml"
                    )
            
                user_data = user_result[0]
                user_id = user_data["id"]
                
                active_chat_query = chat_agent.check_active_chat(user_id)
                logger.info(f"Generated SQL query for active chat: {active_chat_query}")
                
                active_chat_result = execute_query(active_chat_query)
                
                chat_id = None
                chat_history = []
                
                if not active_chat_result:
                    new_chat_query = chat_agent.create_new_chat(user_id)
                    logger.info(f"Generated SQL query for new chat: {new_chat_query}")
                    
                    new_chat_result = execute_query(new_chat_query)
                    if new_chat_result and "id" in new_chat_result:
                        chat_id = new_chat_result["id"]
                        logger.info(f"Created new chat with ID: {chat_id}")
                        

                        intro_message = intro_agent.generate_intro_message(user_data, body)
                        logger.info(f"Generated intro message: {intro_message}")
                        
                        
                        save_message = chat_agent.save_message(chat_id, user_id, body, intro_message)
                        execute_query(save_message["query"], save_message["params"])
                        
                        response = twilio_client.messages.create(
                            from_=TWILIO_WHATSAPP_NUMBER,
                            body=intro_message,
                            to=from_number
                        )
                        logger.info(f"Intro message sent with SID: {response.sid}")
                    else:
                        logger.error(f"Failed to create new chat: {new_chat_result}")
                        response = twilio_client.messages.create(
                            from_=TWILIO_WHATSAPP_NUMBER,
                            body="Sorry, I encountered an error setting up your chat session. Please try again later.",
                            to=from_number
                        )
                else:
                    chat_id = active_chat_result[0]["id"]
                    chat_history_query = chat_agent.get_chat_messages(chat_id)
                    logger.info(f"Generated SQL query for chat history: {chat_history_query}")
                    
                    chat_history = execute_query(chat_history_query)
                    logger.info(f"Retrieved chat history with {len(chat_history)} messages")
                    
                    logger.debug("=== Conversation Analysis Debug ===")
                    logger.debug(f"User Data: {user_data}")
                    logger.debug(f"Chat History: {chat_history}")
                    logger.debug(f"Current Message: {body}")
                    logger.debug(f"Media URLs: {media_urls}")
                    
        
                    mediator_response = mediator_agent.analyze_conversation(
                        user_data, chat_history, body, media_urls
                    )
                    logger.debug(f"Mediator Response: {mediator_response}")
                    
                    if mediator_response.startswith("TRUE"):
                        parts = mediator_response.split(",")
                        recipient_email = parts[1].strip()
                        subject = parts[2].strip()
                        
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        temp_file = f"/tmp/resume_{timestamp}.pdf"
                        
                        logger.info(f"Attempting to download attachment to {temp_file}")
                        
                        if media_urls and download_file(media_urls[0], temp_file):

                            email_body = generate_email_body(subject, temp_file, recipient_email)
                            
                            
                            email_sent = send_email(recipient_email, subject, email_body, temp_file)
                            
                            
                            try:
                                os.unlink(temp_file)
                                logger.info(f"Cleaned up temporary file: {temp_file}")
                            except Exception as e:
                                logger.error(f"Error cleaning up file: {e}")
                            
                        
                            print('Email sent: ', email_sent)
                            if email_sent == False:
                            
                                end_chat_query = chat_agent.end_chat(chat_id)
                                execute_query(end_chat_query)
                                
                        
                                confirmation_message = f"✅ Email sent successfully to {recipient_email}!"
                                
                            
                                save_message = chat_agent.save_message(chat_id, user_id, body, confirmation_message)
                                execute_query(save_message["query"], save_message["params"])
                                
        
                                response = twilio_client.messages.create(
                                    from_=TWILIO_WHATSAPP_NUMBER,
                                    body=confirmation_message,
                                    to=from_number
                                )
                                logger.info(f"Confirmation message sent with SID: {response.sid}")
                            else:
                                error_message = "❌ Sorry, I encountered an error sending the email. Please try again later."
                                
                
                                save_message = chat_agent.save_message(chat_id, user_id, body, error_message)
                                execute_query(save_message["query"], save_message["params"])
                                
                                response = twilio_client.messages.create(
                                    from_=TWILIO_WHATSAPP_NUMBER,
                                    body=error_message,
                                    to=from_number
                                )
                        else:
                            error_message = "❌ Sorry, I encountered an error downloading your attachment. Please try again."
                            
                    
                            save_message = chat_agent.save_message(chat_id, user_id, body, error_message)
                            execute_query(save_message["query"], save_message["params"])
                            

                            response = twilio_client.messages.create(
                                from_=TWILIO_WHATSAPP_NUMBER,
                                body=error_message,
                                to=from_number
                            )
                    elif mediator_response == "FALSE_1":
                        logger.info("Attachment missing, sending reminder")
                        missing_attachment_message = "📎 Please attach your resume/CV/transcript/experience letter to continue. I need this to send your job application."
                    
                        save_message = chat_agent.save_message(chat_id, user_id, body, missing_attachment_message)
                        execute_query(save_message["query"], save_message["params"])
                        
                        response = twilio_client.messages.create(
                            from_=TWILIO_WHATSAPP_NUMBER,
                            body=missing_attachment_message,
                            to=from_number
                        )
                        logger.info(f"Reminder sent with SID: {response.sid}")
                    elif mediator_response == "FALSE_2":
                
                        missing_info_message = "📝 I need a bit more information to send your email:\n\n" + \
                                              "1️⃣ The recipient's email address (e.g., recruiter@company.com)\n" + \
                                              "2️⃣ The email subject (e.g., 'Application for Python Developer Position')\n" + \
                                              "3️⃣ Your resume/CV/transcript/experience letter as an attachment\n\n" + \
                                              "Please provide any missing information."
                        
                        
                        save_message = chat_agent.save_message(chat_id, user_id, body, missing_info_message)
                        execute_query(save_message["query"], save_message["params"])
                        
        
                        response = twilio_client.messages.create(
                            from_=TWILIO_WHATSAPP_NUMBER,
                            body=missing_info_message,
                            to=from_number
                        )
                    else:
                    
                        unknown_response_message = "I'm having trouble understanding your request. Please provide:\n\n" + \
                                                 "1. The recipient's email address\n" + \
                                                 "2. The email subject\n" + \
                                                 "3. Your resume/CV/transcript/experience letter as an attachment"
                        

                        save_message = chat_agent.save_message(chat_id, user_id, body, unknown_response_message)
                        execute_query(save_message["query"], save_message["params"])
                        
                
                        response = twilio_client.messages.create(
                            from_=TWILIO_WHATSAPP_NUMBER,
                            body=unknown_response_message,
                            to=from_number
                        )
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                response = twilio_client.messages.create(
                    from_=TWILIO_WHATSAPP_NUMBER,
                    body="Sorry, I encountered an error processing your request. Please try again later.",
                    to=from_number
                )
        else:
            logger.warning(f"Received message without WaId: {from_number}")
            response = twilio_client.messages.create(
                from_=TWILIO_WHATSAPP_NUMBER,
                body="Sorry, I couldn't identify your phone number.",
                to=from_number
            )

        return Response(
            content="<?xml version='1.0' encoding='UTF-8'?><Response></Response>",
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"Error in WhatsApp webhook: {e}", exc_info=True)
        return Response(
            content="<?xml version='1.0' encoding='UTF-8'?><Response></Response>",
            media_type="application/xml"
        )

if __name__ == "__main__":
    import uvicorn
    print("Starting Email Assistant System server...")
    logger.info("Starting server with WhatsApp number: %s", TWILIO_WHATSAPP_NUMBER)
    uvicorn.run(app, host="0.0.0.0", port=8001) 