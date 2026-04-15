# Student AI Helper

`Student AI Helper` is a Streamlit-based prototype that supports students in organizing their study process and interacting with a mocked AI assistant.

The current version focuses on the user interface and state handling of the main features. Some parts of the system are intentionally mocked and do not yet use real AI-generated outputs.

## Current Features

- Upload one or more PDF study materials through the interface
- Set exam date, daily study hours, and a simulated current date
- Generate a mocked study plan
- Export the generated study plan to `.ics` calendar format
- Chat with a mocked AI study assistant
- Open a flashcard-based knowledge check view

## Current Limitations

- The study plan is currently generated from mock data
- The assistant responses are currently mocked
- Uploaded PDFs are not yet processed by the application logic
- The `openai` dependency is listed, but the current app does not yet call the OpenAI API

## Tech Stack

- Python
- Streamlit

## Project Structure

```text
student_ai_helper/
├── app.py
├── README.md
├── requirements.txt
├── .gitignore
└── venv/              # local virtual environment, not for GitHub
```

## Installation

1. Create and activate a virtual environment if needed.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the App

Start the Streamlit application with:

```bash
streamlit run app.py
```

Then open the local Streamlit URL shown in the terminal.

## Notes

This repository currently represents an early prototype / mockup version of the project. The main emphasis is on interface flow, session-state behavior, and demonstrating planned functionality.
