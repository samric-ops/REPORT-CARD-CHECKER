import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import re
import math

# -------------------------
# DepEd rounding rule
# -------------------------
def round_grade(avg):
    return math.floor(avg + 0.5)

# -------------------------
# Page config
# -------------------------
st.set_page_config(
    page_title="Report Card Checker",
    page_icon="📝",
    layout="wide"
)

st.markdown("""
<style>
.main-header {
    font-size: 2.5rem;
    color: #1f4e3f;
    text-align: center;
}
.subheader {
    text-align: center;
    color: #4a6a5c;
    margin-bottom: 2rem;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">📝 Report Card Grade Checker</div>', unsafe_allow_html=True)
st.markdown('<div class="subheader">Ina‑analyze ang report card at chine‑check ang maling computations</div>', unsafe_allow_html=True)

# -------------------------
# Sidebar
# -------------------------
with st.sidebar:
    st.header("🔑 Settings")
    api_key = st.text_input("Google Gemini API Key", type="password")

    if api_key:
        try:
            genai.configure(api_key=api_key)
            models = genai.list_models()
            available = [
                m.name for m in models
                if "generateContent" in m.supported_generation_methods
            ]
            selected_model = st.selectbox(
                "Pumili ng Gemini model",
                available,
                format_func=lambda x: x.replace("models/", "")
            )
        except Exception as e:
            st.error(e)
            st.stop()
    else:
        st.info("Maglagay ng API key")
        st.stop()

# -------------------------
# Upload Image
# -------------------------
uploaded = st.file_uploader("📸 I-upload ang report card", type=["jpg", "jpeg", "png"])

if uploaded:
    image = Image.open(uploaded)
    st.image(image, use_container_width=True)

    if st.button("🔍 Check Grades", type="primary"):
        with st.spinner("Sinusuri ang grades..."):

            model = genai.GenerativeModel(selected_model)

            prompt = """
            Analyze this report card image.
            Extract subject names, quarterly grades (Q1–Q4), and final grade.
            Return ONLY valid JSON:

            {
              "subjects": [
                {
                  "subject": "MAPEH",
                  "q1": 86,
                  "q2": 87,
                  "q3": 88,
                  "q4": 89,
                  "reported_final": 88
                }
              ],
              "reported_general_average": 88
            }
            """

            response = model.generate_content([prompt, image])
            raw = response.text.strip()

            match = re.search(r"\{[\s\S]*\}", raw)
            data = json.loads(match.group())

            # -------------------------
            # Build subject dict
            # -------------------------
            subjects = {}

            for s in data["subjects"]:
                name = s["subject"].strip()
                subjects[name] = {
                    "q1": s.get("q1"),
                    "q2": s.get("q2"),
                    "q3": s.get("q3"),
                    "q4": s.get("q4"),
                    "reported_final": s.get("reported_final"),
                    "has_quarters": None not in [s.get("q1"), s.get("q2"), s.get("q3"), s.get("q4")]
                }

            # -------------------------
            # Detect MAPEH + components
            # -------------------------
            mapeh_key = None
            subs = {}

            for name in subjects:
                lname = name.lower()
                if "mapeh" in lname:
                    mapeh_key = name
                elif lname in ["music", "arts", "pe", "health"]:
                    subs[lname] = name

            # -------------------------
            # Compute MAPEH correctly
            # -------------------------
            if mapeh_key and len(subs) == 4:

                computed_q = {}

                for q in ["q1", "q2", "q3", "q4"]:
                    values = [subjects[sub][q] for sub in subs.values()]
                    avg = sum(values) / 4
                    computed_q[q] = round_grade(avg)

                computed_final = round_grade(sum(computed_q.values()) / 4)

                subjects[mapeh_key]["computed_q"] = computed_q
                subjects[mapeh_key]["computed_final"] = computed_final

            # -------------------------
            # Compute finals (others)
            # -------------------------
            for name, s in subjects.items():
                if "computed_final" not in s:
                    if s["has_quarters"]:
                        s["computed_final"] = round_grade(
                            (s["q1"] + s["q2"] + s["q3"] + s["q4"]) / 4
                        )
                    else:
                        s["computed_final"] = "Incomplete"

            # -------------------------
            # Results table
            # -------------------------
            rows = []

            for name, s in subjects.items():
                # Handle MAPEH Q1 status only if computed_q exists
                if name == mapeh_key and "computed_q" in s:
                    cq1 = s["computed_q"]["q1"]
                    q1_status = "✅ Tama" if s["q1"] == cq1 else "❌ Mali"
                else:
                    cq1 = "—"
                    q1_status = "—"

                # Final grade status
                if s["reported_final"] is not None:
                    final_status = (
                        "✅ Tama"
                        if s["reported_final"] == s["computed_final"]
                        else "❌ Mali"
                    )
                else:
                    final_status = "⚠️ Walang Final"

                rows.append({
                    "Subject": name,
                    "Q1 (Image)": s["q1"],
                    "Computed Q1 (MAPEH)": cq1,
                    "Q1 Status": q1_status,
                    "Reported Final": s["reported_final"],
                    "Computed Final": s["computed_final"],
                    "Final Status": final_status
                })

            df = pd.DataFrame(rows)
            st.subheader("📊 Grade Verification Result")
            st.dataframe(df, use_container_width=True)

            # -------------------------
            # Download
            # -------------------------
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Result (CSV)",
                csv,
                "grade_check_results.csv",
                "text/csv"
            )
