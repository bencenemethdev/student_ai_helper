# Student AI Helper

`Student AI Helper` is a Streamlit-based AI study assistant that helps students organize their study process, interact with their study materials using RAG (Retrieval-Augmented Generation), and test their knowledge with flashcards.

## Features

- **PDF Upload**: Upload one or more PDF study materials through the interface
- **Study Plan Generation**: Generate a personalized study plan based on exam date, daily study hours, and uploaded materials
- **AI Chat**: Ask questions about your study materials — the AI answers using RAG with Groq LLM
- **Flashcards**: Auto-generate flashcards from your study materials to test your knowledge
- **Calendar Export**: Export the generated study plan to `.ics` calendar format

## Tech Stack

- **Python** — Core language
- **Streamlit** — Web UI framework
- **Groq** — LLM API for chat and flashcard generation
- **FAISS** — Vector database for semantic search
- **Sentence Transformers** — Text embeddings
- **LangChain** — Text splitting utilities

## Project Structure

```
student_ai_helper/
├── app.py              # Main Streamlit application
├── studentHelper.py     # Core logic (RAG, embeddings, study plan)
├── requirements.txt    # Python dependencies
├── README.md          # This file
├── .gitignore         # Git ignore rules
├── .streamlit/
│   └── secrets.toml   # API keys (not committed)
└── venv/              # Virtual environment (not committed)
```

## Installation

1. Create and activate a virtual environment:

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure API key (choose one method):

   **Option A**: Create `.streamlit/secrets.toml`:
   ```toml
   GROQ_API_KEY = "gsk_..."
   ```

   **Option B**: Set environment variable:
   ```bash
   export GROQ_API_KEY="gsk_..."
   ```

## Running the App

```bash
streamlit run app.py
```

Then open the local Streamlit URL shown in the terminal (typically `http://localhost:8501`).

## How It Works

1. **Upload PDFs**: Upload your study materials (PDF files)
2. **Configure**: Set exam date, daily study hours, and current date
3. **Generate Plan**: Click "Generate Study Plan" to process PDFs and create a schedule
4. **Chat**: Ask questions about your materials in the chat interface
5. **Flashcards**: Click "Test My Knowledge" to generate and review flashcards
6. **Export**: Download your study plan as an ICS calendar file

## API Keys

This project uses [Groq](https://console.groq.com/) for LLM inference. Sign up for free and create an API key.

> **Note**: The `.streamlit/secrets.toml` file contains sensitive API keys and is excluded from version control (already in `.gitignore`).
