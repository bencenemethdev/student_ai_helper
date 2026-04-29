import time
from datetime import date

import streamlit as st

from studentHelper import (
    build_chunks_from_pdfs,
    build_vector_index,
    generate_flashcards,
    generate_study_plan,
    rag_chat,
)
import os

st.set_page_config(page_title="Student Helper AI", layout="wide")

if "GROQ_API_KEY" in st.secrets and str(st.secrets["GROQ_API_KEY"]).strip():
    os.environ["GROQ_API_KEY"] = str(st.secrets["GROQ_API_KEY"]).strip()

# --- Session State Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! I'm your AI Study Assistant. How can I help you today?"}
    ]
if "show_flashcard" not in st.session_state:
    st.session_state.show_flashcard = False
if "flashcard_answer_revealed" not in st.session_state:
    st.session_state.flashcard_answer_revealed = False
if "flashcard_index" not in st.session_state:
    st.session_state.flashcard_index = 0
if "flashcard_flipped" not in st.session_state:
    st.session_state.flashcard_flipped = False
if "pending_navigation" not in st.session_state:
    st.session_state.pending_navigation = None
if "study_plan" not in st.session_state:
    st.session_state.study_plan = []


if "flashcards" not in st.session_state:
    st.session_state.flashcards = []
if "chunks" not in st.session_state:
    st.session_state.chunks = []
if "chunk_stats" not in st.session_state:
    st.session_state.chunk_stats = None
if "vdb" not in st.session_state:
    st.session_state.vdb = None
if "chunk_id_to_date" not in st.session_state:
    st.session_state.chunk_id_to_date = {}

def generate_mock_ics(plan_items):
    events = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Student Helper AI//EN",
    ]

    for item in plan_items:
        event_date = item["date"].replace("-", "")
        events.extend(
            [
                "BEGIN:VEVENT",
                f"DTSTART;VALUE=DATE:{event_date}",
                f"DTEND;VALUE=DATE:{event_date}",
                f"SUMMARY:{item['task']} ({item['hours']}h)",
                "END:VEVENT",
            ]
        )

    events.append("END:VCALENDAR")
    return "\n".join(events)


def _has_groq_key() -> bool:
    if "GROQ_API_KEY" in st.secrets and str(st.secrets["GROQ_API_KEY"]).strip():
        return True
    return bool(os.environ.get("GROQ_API_KEY", "").strip())


col1, col2 = st.columns([1, 2])

with col1:
    st.header("Planner & Settings")
    st.divider()
    uploaded_files = st.file_uploader(
        "Upload your study materials (PDF)",
        type=["pdf"],
        accept_multiple_files=True,
        help="You can upload multiple PDF files.",
    )

    st.divider()
    exam_date = st.date_input("Exam Date", value=date.today(), help="Select the date of your exam.")
    daily_hours = st.slider(
        "Daily Study Hours",
        min_value=1,
        max_value=8,
        value=2,
        help="How many hours do you plan to study each day?",
    )
    simulated_date = st.date_input(
        "Simulated Current Date",
        value=date.today(),
        help="For testing the AI's time-awareness.",
    )
    st.divider()

    generate_plan = st.button("Generate Study Plan", use_container_width=True)
    if generate_plan:
        if not uploaded_files:
            st.warning("Please upload at least one PDF.")
        elif not _has_groq_key():
            st.error("Missing Groq API key. Set `GROQ_API_KEY` (env var) or add it to Streamlit secrets.")
        else:
            with st.spinner("Processing PDFs and generating study plan..."):
                chunks, stats = build_chunks_from_pdfs(uploaded_files)
                vdb = build_vector_index(chunks)
                plan, chunk_id_to_date = generate_study_plan(
                    chunks=chunks,
                    current_date=simulated_date,
                    exam_date=exam_date,
                    daily_hours=int(daily_hours),
                )

                st.session_state.chunks = chunks
                st.session_state.chunk_stats = stats
                st.session_state.vdb = vdb
                st.session_state.chunk_id_to_date = chunk_id_to_date
                st.session_state.study_plan = plan

                st.session_state.flashcards = []
                st.session_state.flashcard_index = 0
                st.session_state.flashcard_flipped = False

    if st.session_state.study_plan:
        st.subheader("Study Schedule")
        if st.session_state.chunk_stats:
            s = st.session_state.chunk_stats
            st.caption(
                f"Processed {s['files']} file(s), {s['pages']} page(s), {s['chunks']} chunk(s)."
            )
        for item in st.session_state.study_plan:
            st.markdown(f"- **{item['date']}:** {item['task']} ({item['hours']}h)")

    st.divider()
    st.download_button(
        "Export to Calendar (.ics)",
        data=generate_mock_ics(st.session_state.study_plan),
        file_name="study_plan.ics",
        mime="text/calendar",
        use_container_width=True,
        disabled=not st.session_state.study_plan,
    )

with col2:
    st.header("AI Study Assistant")
    st.divider()

    if not st.session_state.show_flashcard:
        flashcard_btn = st.button("Test My Knowledge (Flashcards)", use_container_width=True)
        if flashcard_btn:
            if not st.session_state.vdb:
                st.warning("Generate a study plan first so I can build flashcards from your PDFs.")
            elif not _has_groq_key():
                st.error("Missing Groq API key. Set `GROQ_API_KEY` (env var) or add it to Streamlit secrets.")
            else:
                with st.spinner("Generating flashcards from your study material..."):
                    st.session_state.flashcards = generate_flashcards(
                        vdb=st.session_state.vdb,
                        chunk_id_to_date=st.session_state.chunk_id_to_date,
                        current_date=simulated_date,
                        n_cards=5,
                    )
            st.session_state.show_flashcard = True
            st.session_state.flashcard_answer_revealed = False
            st.session_state.flashcard_index = 0
            st.session_state.flashcard_flipped = False
            st.rerun()

    if st.session_state.show_flashcard:
        with st.container():
            st.markdown(
                """
                <style>
                .flashcard-flip {
                    width: 400px;
                    height: 250px;
                    position: relative;
                    transform-style: preserve-3d;
                    transition: transform 0.6s ease-in-out;
                }
                .flashcard-flip.flipped {
                    transform: rotateY(180deg);
                }
                .flashcard-face {
                    position: absolute;
                    width: 100%;
                    height: 100%;
                    backface-visibility: hidden;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    border-radius: 18px;
                    box-shadow: 0 8px 16px rgba(0,0,0,0.2);
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    font-size: 1.2em;
                    padding: 2em;
                    color: white;
                    user-select: none;
                }
                .flashcard-face.back {
                    transform: rotateY(180deg);
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            close_col1, close_col2 = st.columns([8, 1])
            with close_col2:
                close = st.button(
                    "✖",
                    key="close_flashcard_full",
                    help="Close flashcard overlay",
                    use_container_width=True,
                    type="secondary",
                )
                if close:
                    st.session_state.show_flashcard = False
                    st.session_state.flashcard_flipped = False
                    st.rerun()

            cards = st.session_state.flashcards or [
                {"question": "No flashcards available yet", "answer": "Generate a study plan and try again."}
            ]
            st.session_state.flashcard_index = st.session_state.flashcard_index % len(cards)
            current_card = cards[st.session_state.flashcard_index]
            flip_class = "flipped" if st.session_state.flashcard_flipped else ""
            col_prev, col_card, col_next = st.columns([0.5, 3, 0.5], vertical_alignment="center")

            with col_prev:
                if st.button("◀", key="prev_card", use_container_width=True):
                    if st.session_state.flashcard_flipped:
                        st.session_state.flashcard_flipped = False
                        st.session_state.pending_navigation = "prev"
                        st.rerun()
                    else:
                        st.session_state.flashcard_index = (st.session_state.flashcard_index - 1) % len(cards)
                        st.rerun()

            with col_card:
                flashcard_container = st.empty()
                flashcard_container.markdown(
                    f"""
                    <div style="perspective: 1200px; display: flex; justify-content: center; align-items: center; min-height: 350px; position: relative;">
                        <div class="flashcard-flip {flip_class}">
                            <div class="flashcard-face" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                                <div style="font-size: 0.9em; opacity: 0.9;">Question {st.session_state.flashcard_index + 1} / {len(cards)}</div>
                                <div style="font-size: 1.3em; text-align: center; margin: 1em 0;"><b>{current_card['question']}</b></div>
                            </div>
                            <div class="flashcard-face back" style="background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);">
                                <div style="font-size: 0.9em; opacity: 0.9;">Answer</div>
                                <div style="font-size: 1.3em; text-align: center; margin: 1em 0;"><b>{current_card['answer']}</b></div>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                flip = st.button("Flip", key=f"flip_card_{st.session_state.flashcard_index}", use_container_width=True)
                if flip:
                    st.session_state.flashcard_flipped = not st.session_state.flashcard_flipped
                    st.rerun()

            with col_next:
                if st.button("▶", key="next_card", use_container_width=True):
                    if st.session_state.flashcard_flipped:
                        st.session_state.flashcard_flipped = False
                        st.session_state.pending_navigation = "next"
                        st.rerun()
                    else:
                        st.session_state.flashcard_index = (st.session_state.flashcard_index + 1) % len(cards)
                        st.rerun()

            if st.session_state.pending_navigation:
                time.sleep(0.225)
                st.session_state.flashcard_index = (
                    (st.session_state.flashcard_index - 1) % len(cards)
                    if st.session_state.pending_navigation == "prev"
                    else (st.session_state.flashcard_index + 1) % len(cards)
                )
                st.session_state.pending_navigation = None
                st.rerun()

    else:
        st.subheader("Chat with your AI Assistant")
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        user_input = st.chat_input("Ask about your study material...")
        if user_input:
            with st.chat_message("user"):
                st.markdown(user_input)
            st.session_state.messages.append({"role": "user", "content": user_input})

            if not st.session_state.vdb:
                ai_response = "Please upload PDFs and click **Generate Study Plan** first so I can answer from your material."
            elif not _has_groq_key():
                ai_response = "Missing Groq API key. Set `GROQ_API_KEY` (env var) or add it to Streamlit secrets."
            else:
                with st.spinner("Searching your materials..."):
                    ai_response = rag_chat(
                        vdb=st.session_state.vdb,
                        chunk_id_to_date=st.session_state.chunk_id_to_date,
                        question=user_input,
                        current_date=simulated_date,
                        model="llama-3.3-70b-versatile",
                    )

            with st.chat_message("assistant"):
                st.markdown(ai_response)
            st.session_state.messages.append({"role": "assistant", "content": ai_response})
            st.rerun()
