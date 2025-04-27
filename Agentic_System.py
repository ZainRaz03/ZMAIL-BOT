from phi.agent import Agent
from phi.tools.sql import SQLTools
from phi.model.google import Gemini
from dotenv import load_dotenv
import os
import PyPDF2
import tempfile
from typing import Optional, List, Dict, Any
from chromadb import Client, Settings
from chromadb.utils import embedding_functions
import logging

load_dotenv()

os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")

logger = logging.getLogger(__name__)

# Base agent class
class BaseAgent(Agent):
    def __init__(self, name, model, tools=None, description=None, instructions=None, show_tool_calls=False, debug_mode=False):
        super().__init__(
            name=name, 
            model=model,
            tools=tools,
            description=description,
            instructions=instructions,
            show_tool_calls=show_tool_calls,
            debug_mode=debug_mode
        )

    def print_response(self, message):
        return super().print_response(message)

# PDF Processing Agent
class PDFProcessingAgent(BaseAgent):
    def __init__(self, name="pdf_processor", model=None):
        model = model or Gemini(model="gemini-1.5-flash")
        super().__init__(name, model)
        
        # Initialize ChromaDB client with timeout settings
        self.client = Client(Settings(
            persist_directory="./chroma_db",
            anonymized_telemetry=False  # Disable telemetry to improve performance
        ))
        
        # Create or get collection
        try:
            self.collection = self.client.get_or_create_collection(
                name="resume_collection",
                embedding_function=embedding_functions.DefaultEmbeddingFunction()
            )
        except Exception as e:
            logger.error(f"Error initializing ChromaDB collection: {e}")
            # Create a fallback collection with minimal settings
            self.collection = self.client.get_or_create_collection(
                name="resume_collection_fallback"
            )

    def process_pdf(self, file_path):
        """Process a single PDF file and store its chunks in the vector database"""
        try:
            with open(file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                filename = os.path.basename(file_path)
                
                all_text = ""
                for page_num, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    all_text += text
                
                # Create fewer, larger chunks to reduce processing time
                chunk_size = 2000  # Increase chunk size
                chunks = [all_text[i:i+chunk_size] for i in range(0, len(all_text), chunk_size)]
                
                # Limit number of chunks to process
                max_chunks = 5
                if len(chunks) > max_chunks:
                    logger.warning(f"Limiting processing to {max_chunks} chunks out of {len(chunks)}")
                    chunks = chunks[:max_chunks]
                
                # Clear previous entries for this file if they exist
                try:
                    self.collection.delete(where={"filename": filename})
                except Exception as e:
                    logger.warning(f"Error clearing previous entries: {e}")
                
                # Add chunks to collection with timeout handling
                added_chunks = 0
                for chunk_id, chunk_text in enumerate(chunks):
                    try:
                        # Set a timeout for this operation
                        self.collection.add(
                            documents=[chunk_text],
                            ids=[f"{filename}_{chunk_id}"],
                            metadatas=[{"filename": filename, "page": 0, "chunk": chunk_id}]
                        )
                        added_chunks += 1
                    except Exception as e:
                        logger.error(f"Error adding chunk {chunk_id}: {e}")
                        # Continue with next chunk
                        continue
                
                if added_chunks > 0:
                    return {
                        "status": "success",
                        "message": f"Processed {filename} with {added_chunks} chunks",
                        "chunks": added_chunks
                    }
                else:
                    # If no chunks were added, return the extracted text directly
                    return {
                        "status": "partial_success",
                        "message": f"Failed to add chunks to database, but extracted text",
                        "text": all_text[:10000]  # Return first 10K chars of text
                    }
                
        except Exception as e:
            logger.error(f"Error processing PDF: {e}")
            return {
                "status": "error",
                "message": f"Error processing PDF: {e}"
            }

    def query_collection(self, query_text, n_results=3):
        """Query the collection for relevant chunks based on the query text"""
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            return results
        except Exception as e:
            logger.error(f"Error querying collection: {e}")
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

# Summary Agent
class SummaryAgent(BaseAgent):
    def __init__(self, name="summary_agent", model=None):
        model = model or Gemini(model="gemini-1.5-flash")
        super().__init__(
            name=name, 
            model=model,
            description="This agent generates personalized email content based on resume data",
            instructions=[
                """
                You are an expert at creating personalized job application emails.
                
                Your task is to:
                1. Analyze the provided resume content
                2. Extract key skills, experiences, and qualifications
                3. Generate a professional and personalized email that highlights the candidate's strengths
                4. Ensure the email is tailored to the job position mentioned in the subject
                5. Keep the tone professional but personable
                
                Important guidelines:
                - Focus on the most relevant experiences for the position
                - Highlight technical skills and achievements
                - Keep the email concise (250-350 words)
                - Include a polite closing and call to action
                - Maintain a professional tone throughout
                - DO NOT include placeholders like [Company Name] in the final output
                - DO NOT include the subject line in the email body
                - DO NOT include instructions or notes in the final output
                """
            ]
        )

    def generate_email_content(self, resume_chunks, job_subject, recipient_email=None):
        """Generate personalized email content based on resume chunks and job subject"""
        try:
            # Extract job position from subject if possible
            job_position = job_subject
            if "position" in job_subject.lower() or "application" in job_subject.lower():
                # Try to extract the actual position
                position_parts = job_subject.split("for ")
                if len(position_parts) > 1:
                    job_position = position_parts[1].strip()
            
            # Limit the amount of text to avoid token limits
            resume_text = ' '.join(resume_chunks)
            if len(resume_text) > 10000:
                resume_text = resume_text[:10000] + "..."
            
            # Create prompt with resume chunks and job position
            prompt = f"""
            Based on the following resume content, create a personalized job application email for a {job_position} position.
            
            RESUME CONTENT:
            {resume_text}
            
            JOB POSITION: {job_position}
            
            RECIPIENT: {recipient_email if recipient_email else 'Hiring Manager'}
            
            Create a professional email with this structure:
            1. Start with a polite greeting (e.g., Dear Hiring Manager)
            2. Open with excitement about applying for the position and eagerness to contribute technical skills
            3. Mention current education status and any relevant work experience
            4. Highlight key skills and expertise, using emojis for section headers:
               - ALWAYS use emojis (not bold text) for section headers: 💻, 🔧, 🛠️
               - For "Programming Languages" section, use 💻 emoji
               - For "Frameworks" section, use 🔧 emoji
               - For "Tools & Technologies" section, use 🛠️ emoji
               - List skills horizontally with commas (not as bullet points)
            5. Briefly mention 3-4 project highlights with a one-line description each, using bullet points (*)
            6. Express motivation to apply skills to the company and align with their goals
            7. Politely invite the recruiter to review the attached resume
            8. End with a professional closing and signature (including name, email, phone)
            9. If a LinkedIn profile is mentioned in the resume, include it ONCE in the signature
            
            IMPORTANT RULES:
            - DO NOT include placeholders like [Company Name] in the final output
            - DO NOT include the subject line in the email body
            - DO NOT include instructions or notes in the final output
            - Keep the tone professional, friendly, and slightly enthusiastic
            - Make the email clear and structured
            - Focus on showcasing technical strength and readiness to contribute value
            - ALWAYS use emojis (💻, 🔧, 🛠️) for section headers, never use bold text
            - List skills horizontally separated by commas, not as bullet points
            - Format only the project highlights as bullet points using asterisks (*)
            - Include LinkedIn URL in signature ONLY ONCE if found in resume
            """
            
            response = self.run(prompt, markdown=True)
            return response.content
        except Exception as e:
            logger.error(f"Error generating email content: {e}")
            return """Dear Hiring Manager,

I am excited to apply for the position mentioned in the subject line. Please find my resume attached for your consideration.

Best regards,
Zain Raza
Lahore, Pakistan
📧 zainxaidi2003@gmail.com | 📞 0306-5187343"""

# Existing agents
class SQLAgent:
    def __init__(self):
        """
        Initializes an SQLAgent to generate SQL queries to check if a user exists in the database.
        """
        self.agent = Agent(
            model=Gemini(model="gemini-1.5-flash"),
            description="This agent generates SQL queries to check if a user exists in the database.",
            instructions=[
                """
                Database Schema Details:
                -------------------------
                Table: 'users'
                Columns:
                - id (bigint unsigned, PRIMARY KEY)
                - name (varchar)
                - phone (varchar)
                - email (varchar)
                - is_member (tinyint(1), represents boolean)
                - is_deleted (tinyint(1), represents boolean)
                
                Your task:
                Generate an SQL query using the above schema. Ensure the query is syntactically correct and adheres to the schema constraints. 
                The query should retrieve user details based on the provided phone number, ensuring the account is not marked as deleted.
                """
            ]
        )
    
    def generate_query(self, phone_number: str) -> str:
        """
        Generates an SQL query to check if a user exists in the database.

        Parameters:
        phone_number (str): The phone number to check.

        Returns:
        str: SQL query to check if the user exists.
        """
        query_prompt = f"""
        Generate an SQL query to check if a user with phone number {phone_number} exists in the users table.
        The query should:
        1. Return the user's id, name, phone, and is_member status
        2. Filter where phone = '{phone_number}' and is_deleted = 0
        
        Return only the SQL query without any explanation or markdown formatting.
        """
        
        response = self.agent.run(query_prompt, markdown=True)
        return response.content

class ChatAgent:
    def __init__(self):
        """
        Initializes a ChatAgent to manage chat sessions and generate queries related to chat functionality.
        """
        self.agent = Agent(
            model=Gemini(model="gemini-1.5-flash"),
            description="This agent manages chat sessions and generates queries related to chat functionality.",
            instructions=[
                """
                Database Schema Details:
                -------------------------
                Table: 'chats'
                Columns:
                - id (bigint unsigned, PRIMARY KEY)
                - user_id (bigint unsigned, links to users.id)
                - status (varchar, can be 'active' or 'ended')
                - created_at (timestamp)
                - updated_at (timestamp)
                
                Table: 'messages'
                Columns:
                - id (bigint unsigned, PRIMARY KEY)
                - chat_id (bigint unsigned, links to chats.id)
                - user_id (bigint unsigned, links to users.id)
                - user_message (text)
                - bot_reply (text)
                - created_at (timestamp)
                
                Important: We are using SQLite database, so use CURRENT_TIMESTAMP instead of NOW() for datetime functions.
                
                Your task:
                Generate SQL queries to manage chat sessions and messages.
                """
            ]
        )
    
    def check_active_chat(self, user_id: str) -> str:
        """
        Generates an SQL query to check if a user has an active chat.

        Parameters:
        user_id (str): The user ID to check.

        Returns:
        str: SQL query to check for active chats.
        """
        query_prompt = f"""
        Generate an SQL query to check if user with ID {user_id} has an active chat.
        The query should:
        1. Return the chat id, user_id, and status
        2. Filter where user_id = {user_id} and status = 'active'
        3. Order by created_at DESC
        4. Limit to 1 result (most recent active chat)
        
        Return only the SQL query without any explanation or markdown formatting.
        """
        
        response = self.agent.run(query_prompt, markdown=True)
        return response.content
    
    def create_new_chat(self, user_id: str) -> str:
        """
        Generates an SQL query to create a new active chat for a user.

        Parameters:
        user_id (str): The user ID to create a chat for.

        Returns:
        str: SQL query to create a new chat.
        """
        query_prompt = f"""
        Generate an SQL query to create a new active chat for user with ID {user_id}.
        The query should:
        1. Insert into the chats table
        2. Set user_id = {user_id}, status = 'active', and appropriate timestamps
        
        Return only the SQL query without any explanation or markdown formatting.
        """
        
        response = self.agent.run(query_prompt, markdown=True)
        return response.content
    
    def get_chat_messages(self, chat_id: str) -> str:
        """
        Generates an SQL query to retrieve all messages for a specific chat.
        
        Parameters:
        chat_id (str): The chat ID to retrieve messages for.
        
        Returns:
        str: SQL query to retrieve chat messages.
        """
        query_prompt = f"""
        Generate an SQL query to retrieve all messages for chat with ID {chat_id}.
        The query should:
        1. Return the user_message and bot_reply
        2. Filter where chat_id = {chat_id}
        3. Order by created_at ASC (oldest to newest)
        
        Return only the SQL query without any explanation or markdown formatting.
        """
        
        response = self.agent.run(query_prompt, markdown=True)
        return response.content

    def save_message(self, chat_id: int, user_id: int, user_message: str, bot_reply: str) -> str:
        """
        Generate a query to save a message in the database.
        """
        query = f"""
        INSERT INTO messages (chat_id, user_id, user_message, bot_reply, created_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        return {"query": query, "params": [chat_id, user_id, user_message, bot_reply]}

    def end_chat(self, chat_id: str) -> str:
        """
        Generates an SQL query to end a chat session.
        
        Parameters:
        chat_id (str): The chat ID to end.
        
        Returns:
        str: SQL query to end a chat.
        """
        query_prompt = f"""
        Generate an SQL query to end a chat session.
        The query should:
        1. Update the chats table
        2. Set status = 'ended' and update the updated_at timestamp
        3. Where id = {chat_id}
        
        Return only the SQL query without any explanation or markdown formatting.
        """
        
        response = self.agent.run(query_prompt, markdown=True)
        return response.content

class IntroAgent:
    def __init__(self):
        """
        Initializes an IntroAgent to handle the initial conversation with users.
        """
        self.agent = Agent(
            model=Gemini(model="gemini-1.5-flash"),
            description="This agent handles the initial conversation with users for the email assistant.",
            instructions=[
                """
                You are an email assistant that helps users send job application emails with their resume/CV.
                
                Your responsibilities:
                1. Guide the user through the process of sending an email
                2. Ask for the recipient's email address
                3. Ask for the email subject
                4. Remind the user to attach their resume/CV/transcript/experience letter.
                
                Important instructions:
                - Be polite, professional, and helpful
                - Make your messages engaging and appealing
                - Use emojis appropriately to make the conversation more engaging
                - Keep your responses concise but informative
                """
            ]
        )
    
    def generate_intro_message(self, user_data: Dict[str, Any], user_message: str) -> str:
        """
        Generate an introductory message for the user.
        
        Parameters:
        user_data (Dict[str, Any]): The user's data.
        user_message (str): The user's message.
        
        Returns:
        str: The introductory message.
        """
        prompt = f"""
        User: {user_message}
        
        User Data: {user_data}
        
        Generate an introductory message for the user. The message should:
        1. Greet the user by name
        2. Explain that you're an email assistant that can help them send job application emails
        3. Ask for the recipient's email address
        4. Ask for the email subject
        5. Remind them to attach their resume/CV
        
        Make the message engaging and appealing. Use emojis appropriately.
        """
        
        response = self.agent.run(prompt, markdown=True)
        return response.content

class MediatorAgent:
    def __init__(self):
        """
        Initializes a MediatorAgent to analyze conversation and determine next steps.
        """
        self.agent = Agent(
            model=Gemini(model="gemini-1.5-flash"),
            description="This agent analyzes the conversation and determines the next steps.",
            instructions=[
                """
                You are a mediator agent that analyzes the conversation between a user and an email assistant.
                
                Your task is to:
                1. Check if the user has provided all required information:
                   - Recipient email address (look for email patterns like xxx@xxx.xxx)
                   - Email subject
                   - Resume/CV attachment
                2. Return the appropriate response:
                   - If all information is present AND media_urls is not empty: "TRUE, [email], [subject], [attachment_url]"
                   - If email and subject found but media_urls is empty: "FALSE_1"
                   - If email or subject is missing: "FALSE_2"
                
                Important:
                - First check if media_urls list has any attachments
                - If media_urls is empty, ALWAYS return "FALSE_1" if email and subject are found
                - Never return TRUE if media_urls is empty or None
                - Be thorough in searching for email patterns
                """
            ]
        )
    
    def analyze_conversation(self, user_data: Dict[str, Any], chat_history: List[Dict[str, Any]], user_message: str, media_urls: List[str]) -> str:
        """
        Analyze the conversation and determine the next steps.
        """
        chat_messages = []
        for msg in chat_history:
            chat_messages.append(f"User: {msg['user_message']}")
            chat_messages.append(f"Bot: {msg['bot_reply']}")
        formatted_history = "\n".join(chat_messages)

        prompt = (
            f"Analyze this conversation carefully:\n\n"
            f"User Data: {user_data}\n\n"
            f"Previous Messages:\n{formatted_history}\n\n"
            f"Current Message: {user_message}\n\n"
            f"Attachments: {media_urls}\n\n"
            "Task:\n"
            "1. FIRST check if media_urls list has any items\n"
            "2. Find recipient email address in any message (pattern: xxx@xxx.xxx)\n"
            "3. Find email subject in any message\n\n"
            "Rules:\n"
            "- If media_urls is empty or None: Return 'FALSE_1' if email and subject are found\n"
            "- If media_urls has items AND email+subject found: Return 'TRUE, [email], [subject], [first_url]'\n"
            "- If email or subject missing: Return 'FALSE_2'\n\n"
            "IMPORTANT: Never return TRUE if media_urls is empty or None.\n"
            "Format responses EXACTLY as specified. Do not add extra text."
        )
        
        response = self.agent.run(prompt, markdown=True)
        result = response.content.strip()

    
        if result.startswith("TRUE") and not media_urls:
            # Force FALSE_1 if no attachments
            return "FALSE_1"
            
        return result

# Initialize agents
sql_agent = SQLAgent()
chat_agent = ChatAgent()
intro_agent = IntroAgent()
mediator_agent = MediatorAgent()
pdf_agent = PDFProcessingAgent()
summary_agent = SummaryAgent() 