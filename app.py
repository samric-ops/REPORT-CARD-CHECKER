import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import re

# Page configuration
st.set_page_config(page_title="Report Card Checker", page_icon="📝", layout="wide")

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1f4e3f;
        text-align: center;
        margin-bottom: 1rem;
    }
    .subheader {
        text-align: center;
        color: #4a6a5c;
        margin-bottom: 2rem;
    }
    .grade-table {
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
    .success-text {
        color: #28a745;
        font-weight: bold;
        font-size: 1.2rem;
    }
    .error-text {
        color: #dc3545;
        font-weight: bold;
        font-size: 1.2rem;
    }
    .warning-text {
        color: #ffc107;
        font-weight: bold;
    }
    footer {
        text-align: center;
        font-size: 0.8rem;
        color: #6c757d;
        margin-top: 3rem;
    }
    </style>
""", unsafe_allow_html=True)

# Title and description
st.markdown('<div class="main-header">📝 Report Card Grade Checker</div>', unsafe_allow_html=True)
st.markdown('<div class="subheader">I-upload ang larawan ng report card para awtomatikong suriin ang mga kalkulasyon.</div>', unsafe_allow_html=True)

# Sidebar for API key and settings
with st.sidebar:
    st.header("🔑 Settings")
    api_key = st.text_input("Google Gemini API Key", type="password", help="Kumuha ng API key mula sa Google AI Studio")
    
    # Model selection to avoid 404 errors
    model_options = {
        "gemini-1.5-flash": "Gemini 1.5 Flash (mabilis, balanse)",
        "gemini-1.5-pro": "Gemini 1.5 Pro (mas malakas, mas tumpak)",
        "gemini-1.0-pro": "Gemini 1.0 Pro (legacy)"
    }
    selected_model = st.selectbox("Pumili ng Gemini model", options=list(model_options.keys()), format_func=lambda x: model_options[x])
    
    st.markdown("---")
    st.markdown("### Paano gamitin")
    st.markdown("""
    1. Ipasok ang iyong Gemini API key.
    2. I-upload ang larawan ng report card (JPG/PNG).
    3. I-click ang **Check Grades**.
    4. Tingnan ang resulta sa ibaba.
    """)

# Main content area
if not api_key:
    st.info("🔐 Mangyaring ilagay ang iyong Gemini API key sa sidebar para makapagsimula.")
else:
    # Configure Gemini
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"⚠️ Error sa pag-configure ng API key: {e}")
        st.stop()

    # File uploader
    uploaded_file = st.file_uploader("Pumili ng larawan (JPG, PNG)", type=['jpg', 'jpeg', 'png'])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        # Show image with fixed width
        st.image(image, caption="Uploaded Report Card", use_container_width=True)

        # Check button
        if st.button("🔍 Check Grades", type="primary"):
            with st.spinner("Binabasa ang report card at kinukuha ang mga grado..."):
                try:
                    # Create model instance
                    model = genai.GenerativeModel(selected_model)
                    
                    # Prompt designed for better JSON extraction
                    prompt = """
                    Analyze this image of a student report card. Extract:
                    - For each subject: the subject name, four quarterly grades (Q1, Q2, Q3, Q4), and the final grade (if visible).
                    - The overall General Average (if present).

                    Return ONLY a valid JSON object with the following structure (do not include any extra text or markdown):
                    {
                        "subjects": [
                            {
                                "subject": "Subject Name",
                                "q1": 90,
                                "q2": 91,
                                "q3": 89,
                                "q4": 92,
                                "reported_final": 91
                            }
                        ],
                        "reported_general_average": 90.5
                    }
                    
                    If a grade is missing or unclear, use null. Use numbers only for grades. If no general average is visible, set it to null.
                    """
                    
                    # Generate content
                    response = model.generate_content([prompt, image])
                    
                    # Extract JSON from response (clean markdown if present)
                    raw_text = response.text.strip()
                    # Remove markdown code block markers
                    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw_text)
                    if json_match:
                        json_str = json_match.group(1)
                    else:
                        json_str = raw_text
                    
                    # Try to parse JSON
                    data = json.loads(json_str)
                    
                    # Process subjects data
                    results = []
                    total_computed = 0
                    valid_count = 0
                    
                    for item in data.get('subjects', []):
                        subject = item.get('subject', 'Unknown')
                        q1 = item.get('q1')
                        q2 = item.get('q2')
                        q3 = item.get('q3')
                        q4 = item.get('q4')
                        reported_final = item.get('reported_final')
                        
                        # Compute average if all quarters available
                        if None not in [q1, q2, q3, q4]:
                            computed_final = round((q1 + q2 + q3 + q4) / 4)  # DepEd rounding to whole number
                            total_computed += computed_final
                            valid_count += 1
                            
                            if reported_final is not None:
                                status = "✅ Tama" if computed_final == reported_final else "❌ Mali"
                            else:
                                status = "⚠️ Walang nakasulat na final"
                        else:
                            computed_final = "Incomplete"
                            status = "⚠️ Kulang ang quarterly grades"
                        
                        results.append({
                            "Subject": subject,
                            "Q1": q1 if q1 is not None else "—",
                            "Q2": q2 if q2 is not None else "—",
                            "Q3": q3 if q3 is not None else "—",
                            "Q4": q4 if q4 is not None else "—",
                            "Nakasulat na Final": reported_final if reported_final is not None else "—",
                            "Na-compute na Final": computed_final,
                            "Status": status
                        })
                    
                    # Display subject grades table
                    st.markdown("---")
                    st.subheader("📚 Subject Grades Check")
                    df = pd.DataFrame(results)
                    st.dataframe(df, use_container_width=True, height=400)
                    
                    # General Average checking
                    st.markdown("---")
                    st.subheader("📈 General Average Check")
                    if valid_count > 0:
                        computed_avg = round(total_computed / valid_count, 2)
                        reported_avg = data.get('reported_general_average')
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Nakasulat na General Average", reported_avg if reported_avg is not None else "—")
                        with col2:
                            st.metric("Na-compute ng System", computed_avg)
                        
                        if reported_avg is not None:
                            if abs(float(reported_avg) - computed_avg) < 0.01:  # allow small floating point difference
                                st.success("✅ Tama ang General Average!")
                            else:
                                st.error("❌ Mali ang General Average. Pakisuri ang mga grades.")
                        else:
                            st.info("ℹ️ Walang nakasulat na General Average sa report card.")
                    else:
                        st.warning("Walang kumpletong quarterly grades na makuha. Hindi makalkula ang general average.")
                    
                    # Optional: download results as CSV
                    st.markdown("---")
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 I-download ang resulta (CSV)",
                        data=csv,
                        file_name="grade_check_results.csv",
                        mime="text/csv",
                    )
                    
                except json.JSONDecodeError as je:
                    st.error("❌ Hindi ma-parse ang sagot mula sa Gemini. Maaaring hindi malinaw ang larawan o may ibang problema.")
                    st.text("Raw response:")
                    st.code(raw_text)
                except Exception as e:
                    st.error(f"May naging error: {e}")
                    st.info("Subukan ang ibang model sa sidebar o tiyaking malinaw ang larawan.")

    else:
        st.info("📸 Pumili ng larawan ng report card upang magsimula.")

# Footer
st.markdown("---")
st.markdown("<footer>© 2025 Report Card Checker | Gamit ang Google Gemini AI</footer>", unsafe_allow_html=True)
