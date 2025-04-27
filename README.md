# 🚀 ZMAIL BOT: AI-Powered WhatsApp Email Assistant

ZMAIL BOT is an **AI-powered WhatsApp-based email assistant** that automates the entire flow of sending personalized job application emails directly through WhatsApp.  
It uses **Google Gemini models**, **ChromaDB for vector search**, **FastAPI backend**, **Twilio WhatsApp API**, and **multi-agent AI system** built on **PHI framework**.

---

## 🌟 Key Features

- 📄 **PDF Resume Processing**: Extracts and intelligently chunks resume data.
- 🤖 **Multi-Agent AI System**:
  - PDF Processing Agent
  - Summary Generation Agent
  - SQL Query Agent
  - Chat Management Agent
  - Intro Conversation Agent
  - Mediator Agent for flow control
- 💬 **WhatsApp Integration**: Receive user inputs, attachments, and send confirmations directly on WhatsApp using Twilio.
- 🧠 **Smart Conversation Understanding**: Auto-detects missing details like email, subject, or attachment.
- 🛢️ **Database-Backed**: SQLite database for storing users, chats, and messages.
- 📧 **Email Sending with Attachments**: Sends personalized professional emails with the user's resume attached.
- ⚡ **Highly Modular**: Clean separation of agents, backend APIs, and database operations.
- 🔒 **Secure**: Environment variables (.env) are used for API keys and sensitive configs.

---

## 🛠️ Tech Stack

| Category            | Tech Used                   |
|:---------------------|:-----------------------------|
| **Backend**           | FastAPI |
| **AI Model**          | Google Gemini (via PHI) |
| **Vector Database**   | ChromaDB |
| **Database**          | SQLite |
| **Communication**     | Twilio WhatsApp API |
| **File Processing**   | PyPDF2 |
| **Deployment**        | Uvicorn |

---

## 🏗️ Architecture Overview


User (WhatsApp) 
    ↓
FastAPI Server (ZMAIL BOT)
    ↓
Agents (IntroAgent, MediatorAgent, SummaryAgent, etc.)
    ↓
Database (SQLite) + Vector Search (ChromaDB)
    ↓
Twilio API + Email Sending Tools
    ↓
Response back to WhatsApp



## ⚙️ Setup Instructions

1. **Clone the Repository**
   
   git clone https://github.com/ZainRaz03/ZMAIL-BOT.git
   
   cd zmail-bot
  

3. **Create a Virtual Environment**

   python3 -m venv venv
   
   source venv/bin/activate
   

5. **Install Dependencies**
   
   pip install -r requirements.txt
   

6. **Setup Environment Variables**

   Create a `.env` file in the root directory and add:
   
   GOOGLE_API_KEY=your_google_gemini_api_key
   
   TWILIO_ACCOUNT_SID=your_twilio_sid
   
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   
   TWILIO_PHONE_NUMBER=your_twilio_phone_number
   
   SENDER_EMAIL=your_email@example.com
   
   SENDER_NAME=Your Name
   
   SENDER_PASSKEY=your_email_app_password
  

8. **Run the Server**
   
   uvicorn main:app --host 0.0.0.0 --port 8001 --reload




## 📑 Example Flow

- ✅ User sends "Hi" on WhatsApp
- ✅ Bot replies asking for email address, subject, and resume
- ✅ User shares email, subject, and PDF attachment
- ✅ Bot processes the resume and generates a highly personalized email
- ✅ Bot sends the email on user's behalf
- ✅ Bot confirms email sent successfully



## 🧩 Agents and Responsibilities

| Agent Name           | Role |
|----------------------|-----|
| `PDFProcessingAgent`  | Process PDF resumes into vector database |
| `SummaryAgent`        | Generate personalized job application email |
| `SQLAgent`            | Validate users in database |
| `ChatAgent`           | Manage chat sessions and messages |
| `IntroAgent`          | Start conversation with user |
| `MediatorAgent`       | Analyze conversation flow and decide next step |



