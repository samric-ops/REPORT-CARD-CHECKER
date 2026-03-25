import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import re
import math

# Custom rounding for grades (DepEd style)
def round_grade(avg):
    """
    Rounds a numeric average to the nearest integer.
    If the decimal part is 0.5 or higher, round up; otherwise round down.
    """
    return math.floor(avg + 0.5)

# Page config
st.set_page_config(page_title="Report Card Checker", page_icon="📝", layout="wide")

# Custom CSS
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
    footer {
        text-align: center;
        font-size: 0.8rem;
        color: #6c757d;
        margin-top: 3rem;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">📝 Report Card Grade Checker</div>', unsafe_allow_html=True)
st.markdown('<div class="subheader">I-upload ang larawan ng report card para awtomatikong suriin ang mga kalkulasyon.</div>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("🔑 Settings")
    api_key = st.text_input("Google Gemini API Key", type="password", 
                            help="Kumuha ng API key mula sa Google AI Studio")
    
    if api_key:
        try:
            genai.configure(api_key=api_key)
            models = genai.list_models()
            available_models = [m.name for m in models if 'generateContent' in m.supported_generation_methods]
            if not available_models:
                st.error("Walang available na modelo para sa generateContent. Tiyaking tama ang API key.")
                st.stop()
            selected_model_full = st.selectbox(
                "Pumili ng Gemini model",
                available_models,
                format_func=lambda x: x.replace('models/', '')
            )
        except Exception as e:
            st.error(f"Error connecting to Gemini: {e}")
            st.stop()
    else:
        st.info("Maglagay ng API key para makapili ng modelo.")
        st.stop()
    
    st.markdown("---")
    st.markdown("### Paano gamitin")
    st.markdown("""
    1. Ipasok ang iyong Gemini API key.
    2. Pumili ng model (automatic na naglo-load ng available models).
    3. I-upload ang larawan ng report card (JPG/PNG).
    4. I-click ang **Check Grades**.
    5. Tingnan ang resulta sa ibaba.
    """)

# Main area
if api_key:
    uploaded_file = st.file_uploader("Pumili ng larawan (JPG, PNG)", type=['jpg', 'jpeg', 'png'])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Report Card", use_container_width=True)

        if st.button("🔍 Check Grades", type="primary"):
            with st.spinner("Binabasa ang report card at kinukuha ang mga grado..."):
                try:
                    model = genai.GenerativeModel(selected_model_full)
                    
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
                    
                    response = model.generate_content([prompt, image])
                    
                    # Extract JSON from response
                    raw_text = response.text.strip()
                    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw_text)
                    if json_match:
                        json_str = json_match.group(1)
                    else:
                        json_str = raw_text
                    
                    data = json.loads(json_str)
                    
                    # Process subjects
                    results = []
                    total_for_general = 0      # sum of computed finals for subjects WITH reported final
                    count_for_general = 0      # number of subjects WITH reported final
                    
                    for item in data.get('subjects', []):
                        subject = item.get('subject', 'Unknown')
                        q1 = item.get('q1')
                        q2 = item.get('q2')
                        q3 = item.get('q3')
                        q4 = item.get('q4')
                        reported_final = item.get('reported_final')
                        
                        # Compute the correct final grade from quarters
                        if None not in [q1, q2, q3, q4]:
                            avg = (q1 + q2 + q3 + q4) / 4.0
                            computed_final = round_grade(avg)
                            
                            # Only include in general average if this subject has a reported final grade
                            if reported_final is not None:
                                total_for_general += computed_final
                                count_for_general += 1
                            
                            # Determine status
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
                    st.subheader("📚 Subject Grades Check")
                    df = pd.DataFrame(results)
                    st.dataframe(df, use_container_width=True, height=400)
                    
                    # General Average
                    st.subheader("📈 General Average Check")
                    if count_for_general > 0:
                        computed_avg_decimal = total_for_general / count_for_general
                        computed_avg_rounded = round_grade(computed_avg_decimal)  # round to integer
                        reported_avg = data.get('reported_general_average')
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Nakasulat na General Average", reported_avg if reported_avg is not None else "—")
                        with col2:
                            st.metric("Na-compute ng System (batay sa mga asignaturang may final grade)", computed_avg_rounded)
                        
                        if reported_avg is not None:
                            # Convert both to integers for comparison (after rounding)
                            if int(computed_avg_rounded) == int(reported_avg):
                                st.success("✅ Tama ang General Average!")
                            else:
                                st.error("❌ Mali ang General Average. Pakisuri ang mga grades.")
                        else:
                            st.info("ℹ️ Walang nakasulat na General Average sa report card.")
                    else:
                        st.warning("Walang kumpletong quarterly grades na makuha. Hindi makalkula ang general average.")
                    
                    # Download button
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 I-download ang resulta (CSV)",
                        data=csv,
                        file_name="grade_check_results.csv",
                        mime="text/csv",
                    )
                    
                except json.JSONDecodeError:
                    st.error("❌ Hindi ma-parse ang sagot mula sa Gemini. Maaaring hindi malinaw ang larawan.")
                    st.text("Raw response:")
                    st.code(raw_text)
                except Exception as e:
                    st.error(f"May naging error: {e}")
                    st.info("Subukan ang ibang model sa sidebar o tiyaking malinaw ang larawan.")
    else:
        st.info("📸 Pumili ng larawan ng report card upang magsimula.")
else:
    st.warning("🔑 Mangyaring ilagay ang iyong Gemini API key sa sidebar para makapagsimula.")

# Footer
st.markdown("---")
st.markdown("<footer>© 2025 Report Card Checker | Gamit ang Google Gemini AI</footer>", unsafe_allow_html=True)
