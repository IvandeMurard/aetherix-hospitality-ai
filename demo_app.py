import streamlit as st
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="F&B Operations Agent", page_icon="🍽️")

st.title("🍽️ F&B Operations Agent")
st.markdown("**Hackathon Pioneers AILab** - Intelligent prediction with Mistral + Qdrant + ElevenLabs")

# Sidebar
st.sidebar.header("📅 Configuration")
date = st.sidebar.date_input(
    "Prediction Date",
    value=datetime.now() + timedelta(days=1)
)

# Input section
st.header("📝 Event Context")
col1, col2 = st.columns(2)

with col1:
    events = st.text_area(
        "Planned Events",
        value="Coldplay concert at Stade de France, sunny evening",
        height=100
    )

with col2:
    weather = st.text_area(
        "Weather Conditions",
        value="Clear sky, 22°C",
        height=100
    )

# Predict button
if st.button("🎯 Generate Prediction", type="primary", use_container_width=True):
    with st.spinner("🤖 Agent analyzing..."):
        try:
            response = requests.post(
                "http://127.0.0.1:8000/predict",
                json={
                    "date": str(date),
                    "events": events,
                    "weather": weather
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Metrics
                st.success("✅ Prediction generated successfully!")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric(
                        label="🍽️ Expected Covers",
                        value=result['expected_covers'],
                        delta=f"+{result['expected_covers'] - 60} vs normal"
                    )
                
                with col2:
                    st.metric(
                        label="👥 Recommended Staff",
                        value=result['recommended_staff'],
                        delta="people"
                    )
                
                with col3:
                    st.metric(
                        label="📊 Confidence",
                        value=f"{result['confidence']}%",
                        delta="high" if result['confidence'] > 80 else "medium"
                    )
                
                st.divider()
                
                # Key factors
                st.subheader("🔑 Key Prediction Factors")
                for i, factor in enumerate(result['key_factors'], 1):
                    st.write(f"**{i}.** {factor}")
                
                # Context recap
                with st.expander("📋 Context Summary"):
                    st.write(f"**📅 Date:** {result['date']}")
                    st.write(f"**🎪 Events:** {result['events']}")
                    st.write(f"**🌤️ Weather:** {result['weather']}")
                
            else:
                st.error(f"❌ API Error: {response.status_code}")
                
        except Exception as e:
            st.error(f"❌ Connection Error: {e}")
            st.info("💡 Make sure the API is running: `uvicorn api:app --reload --port 8000`")

# Sidebar info
st.sidebar.markdown("---")
st.sidebar.markdown("**🛠️ Technologies Used:**")
st.sidebar.markdown("• **Mistral AI** - Embeddings + LLM")
st.sidebar.markdown("• **Qdrant** - Vector Search")
st.sidebar.markdown("• **ElevenLabs** - Voice (integrated)")
st.sidebar.markdown("• **FastAPI** - Backend")
st.sidebar.markdown("• **Streamlit** - Interface")

