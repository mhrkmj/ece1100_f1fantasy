import streamlit as st

st.set_page_config(
    layout="wide",
    initial_sidebar_state="collapsed"
)
st.title(":red[F1 Fantasy]")

st.markdown("Welcome to my F1 Fantasy Bot. Here you can either get a team for an upcoming grandprix in the 2025 season or get your existing team graded. This program runs on the Gemini LLM, and can sometimes get math wrong. So make sure you check how much your total team costs for either mode. I hope you enjoy!")
st.divider()
st.markdown("##### :green-background[Which mode do you want to be in?]")

st.page_link("pages/Create_Mode.py", label=":grey-background[:triangular_ruler: Create Mode]")
st.page_link("pages/Grade_Mode.py", label=":grey-background[:memo: Grade Mode]")
