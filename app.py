import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json

# Setup the page
st.set_page_config(page_title="Report Card Checker", layout="wide")
st.title("📝 Report Card Grade Checker")
st.write("Mag-upload ng picture o screenshot ng report card para ma-check ang totals at general average.")

# API Key input para secure
api_key = st.text_input("Enter your Google Gemini API Key:", type="password")

if api_key:
    genai.configure(api_key=api_key)
    
    # File uploader (supports camera capture on mobile if opened in browser)
    uploaded_file = st.file_uploader("Upload Report Card Image (JPG/PNG)", type=['jpg', 'jpeg', 'png'])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption='Uploaded Report Card', use_container_width=True)

        if st.button("🔍 Check Grades"):
            with st.spinner("Binabasa at kinocompute ang grades... Please wait."):
                try:
                    # Gamitin natin ang Gemini Vision model para basahin ang table
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    
                    prompt = """
                    Analyze this image of a report card. Extract the subject names, the 4 quarterly grades, and the final grade for each subject. 
                    Also, extract the overall General Average if visible.
                    Return ONLY a valid JSON structure like this, without markdown formatting:
                    {
                        "subjects": [
                            {"subject": "Math", "q1": 90, "q2": 91, "q3": 89, "q4": 92, "reported_final": 91}
                        ],
                        "reported_general_average": 90.5
                    }
                    If a grade is missing or blank, use null.
                    """
                    
                    response = model.generate_content([prompt, image])
                    
                    # Linisin ang response para makuha ang JSON
                    json_text = response.text.strip().replace('```json', '').replace('```', '')
                    data = json.loads(json_text)
                    
                    # I-process ang data at i-compute ang tama
                    results = []
                    total_computed_finals = 0
                    valid_subjects_count = 0

                    for item in data.get('subjects', []):
                        subj = item.get('subject', 'Unknown')
                        q1 = item.get('q1')
                        q2 = item.get('q2')
                        q3 = item.get('q3')
                        q4 = item.get('q4')
                        rep_final = item.get('reported_final')
                        
                        # Compute average kung kumpleto ang quarters
                        if None not in [q1, q2, q3, q4]:
                            computed_final = round((q1 + q2 + q3 + q4) / 4) # Rounding standard in DepEd
                            total_computed_finals += computed_final
                            valid_subjects_count += 1
                            
                            status = "✅ Tama" if computed_final == rep_final else "❌ MALI"
                        else:
                            computed_final = "Incomplete"
                            status = "⚠️ Hindi kumpleto"

                        results.append({
                            "Subject": subj,
                            "Q1": q1, "Q2": q2, "Q3": q3, "Q4": q4,
                            "Nakasulat na Final": rep_final,
                            "Na-compute na Final": computed_final,
                            "Status": status
                        })

                    # Display the Table
                    df = pd.DataFrame(results)
                    st.subheader("📊 Subject Grades Checking")
                    st.dataframe(df, use_container_width=True)

                    # General Average Checking
                    if valid_subjects_count > 0:
                        computed_gen_avg = round((total_computed_finals / valid_subjects_count), 2) # Rounded to 2 decimal places
                        rep_gen_avg = data.get('reported_general_average')
                        
                        st.subheader("📈 General Average Checking")
                        st.write(f"**Nakasulat na General Average:** {rep_gen_avg}")
                        st.write(f"**Na-compute ng System:** {computed_gen_avg}")
                        
                        if rep_gen_avg:
                            if float(rep_gen_avg) == computed_gen_avg:
                                st.success("✅ TAMA ang pag-compute ng General Average!")
                            else:
                                st.error("❌ MALI ang General Average. Pakicheck ulit ang computation.")

                except Exception as e:
                    st.error(f"May naging error sa pagbasa ng picture. Siguraduhing malinaw ang image. Error details: {e}")
