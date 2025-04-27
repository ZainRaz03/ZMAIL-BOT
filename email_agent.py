from phi.agent import Agent
from phi.tools import Toolkit
from phi.model.google import Gemini
import os
from typing import Optional, List

class EmailToolsWithAttachments(Toolkit):
    def __init__(
        self,
        receiver_email: Optional[str] = None,
        sender_name: Optional[str] = None,
        sender_email: Optional[str] = None,
        sender_passkey: Optional[str] = None,
    ):
        super().__init__(name="email_tools")
        self.receiver_email: Optional[str] = receiver_email
        self.sender_name: Optional[str] = sender_name
        self.sender_email: Optional[str] = sender_email
        self.sender_passkey: Optional[str] = sender_passkey
        
        self.register(self.email_user_with_attachments)
    
    def email_user_with_attachments(self, subject: str, body: str, attachments: Optional[List[str]] = None) -> str:
        """Emails the user with the given subject, body, and optional attachments.

        :param subject: The subject of the email.
        :param body: The body of the email.
        :param attachments: List of file paths to attach to the email.
        :return: "success" if the email was sent successfully, "error: [error message]" otherwise.
        """
        try:
            import smtplib
            from email.message import EmailMessage
            import mimetypes
        except ImportError:
            print("Required libraries not installed")
            return "error: Required libraries not installed"

        if not self.receiver_email:
            return "error: No receiver email provided"
        if not self.sender_name:
            return "error: No sender name provided"
        if not self.sender_email:
            return "error: No sender email provided"
        if not self.sender_passkey:
            return "error: No sender passkey provided"

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{self.sender_name} <{self.sender_email}>"
        msg["To"] = self.receiver_email
        msg.set_content(body)

        if attachments:
            for file_path in attachments:
                try:
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                        file_name = os.path.basename(file_path)
                        
        
                        content_type, encoding = mimetypes.guess_type(file_path)
                        if content_type is None or encoding is not None:
                            content_type = 'application/octet-stream'
                        
                        maintype, subtype = content_type.split('/', 1)
                        msg.add_attachment(file_data, 
                                          maintype=maintype, 
                                          subtype=subtype, 
                                          filename=file_name)
                except Exception as e:
                    print(f"Failed to attach file {file_path}: {e}")
                    return f"error: Failed to attach file {file_path}: {e}"

        print(f"Sending Email to {self.receiver_email} with {len(attachments) if attachments else 0} attachments")
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(self.sender_email, self.sender_passkey)
                smtp.send_message(msg)
        except Exception as e:
            print(f"Error sending email: {e}")
            return f"error: {e}"
        return "email sent successfully"
