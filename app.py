import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import re
import math

# Custom rounding for grades (DepEd style: 0.5 rounds up)
def round_grade(avg):
    return math.floor(avg + 0.5)

# Page config
st.set_page_config(page_title="Report Card Checker", page_icon="📝", layout="wide")

# Custom CSS
st.markdown("""
    <style>
    .main-header { font-size: 2.5rem; color: #1f4e3f; text-align: center; margin-bottom: 1rem; }
    .subheader { text-align: center; color: #4a6a5c; margin-bottom: 2rem; }
    footer { text-align: center; font-size: 0.8rem; color: #6c757d; margin-top: 3rem; }
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
                    
                    # --- Build dictionary of all subjects with quarter grades ---
                    subjects = {}
                    for item in data.get('subjects', []):
                        name = item.get('subject', 'Unknown').strip()
                        q1 = item.get('q1')
                        q2 = item.get('q2')
                        q3 = item.get('q3')
                        q4 = item.get('q4')
                        reported_final = item.get('reported_final')
                        
                        subjects[name] = {
                            'q1': q1, 'q2': q2, 'q3': q3, 'q4': q4,
                            'reported_final': reported_final,
                            'has_quarters': None not in [q1, q2, q3, q4]
                        }
                    
                    # --- Identify MAPEH and its subcomponents ---
                    normalized_names = {key.strip().lower(): key for key in subjects}
                    mapeh_key = None
                    subcomponents = ['music', 'arts', 'pe', 'health']
                    sub_mapping = {}  # maps subcomponent name to original key
                    
                    # Find MAPEH entry
                    for norm_name, orig_name in normalized_names.items():
                        if 'mapeh' in norm_name:
                            mapeh_key = orig_name
                            break
                    
                    # Find subcomponent entries (allow variations)
                    for sc in subcomponents:
                        for norm_name, orig_name in normalized_names.items():
                            if norm_name == sc or (sc == 'pe' and 'physical' in norm_name) or (sc in norm_name):
                                sub_mapping[sc] = orig_name
                                break
                    
                    # Store MAPEH data separately (original vs computed)
                    mapeh_computed_quarters = {'q1': None, 'q2': None, 'q3': None, 'q4': None}
                    mapeh_quarter_status = {}
                    mapeh_reported_final = None
                    mapeh_computed_final = None
                    
                    # --- Compute MAPEH quarterly grades if subcomponents exist ---
                    if mapeh_key and len(sub_mapping) == 4:
                        # Get original MAPEH data
                        orig_mapeh = subjects[mapeh_key]
                        mapeh_reported_final = orig_mapeh.get('reported_final')
                        
                        # Collect subcomponent grades per quarter
                        mapeh_q = {'q1': [], 'q2': [], 'q3': [], 'q4': []}
                        for sc, key in sub_mapping.items():
                            sub = subjects[key]
                            if sub['has_quarters']:
                                for q in ['q1', 'q2', 'q3', 'q4']:
                                    if sub[q] is not None:
                                        mapeh_q[q].append(sub[q])
                        
                        # Compute correct quarterlies
                        for q in ['q1', 'q2', 'q3', 'q4']:
                            if len(mapeh_q[q]) == 4:
                                avg = sum(mapeh_q[q]) / 4.0
                                mapeh_computed_quarters[q] = round_grade(avg)
                            else:
                                mapeh_computed_quarters[q] = None
                        
                        # Compare with reported MAPEH quarterlies
                        for q in ['q1', 'q2', 'q3', 'q4']:
                            reported = orig_mapeh[q]
                            computed = mapeh_computed_quarters[q]
                            if computed is not None and reported is not None:
                                if computed != reported:
                                    mapeh_quarter_status[q] = f"❌ Mali (dapat {computed})"
                                else:
                                    mapeh_quarter_status[q] = "✅ Tama"
                            elif computed is None:
                                mapeh_quarter_status[q] = "⚠️ Kulang ang subcomponents"
                            else:
                                mapeh_quarter_status[q] = "⚠️ Walang nakasulat"
                        
                        # Compute MAPEH final grade from corrected quarterlies
                        if all(v is not None for v in mapeh_computed_quarters.values()):
                            mapeh_computed_final = round_grade(sum(mapeh_computed_quarters.values()) / 4.0)
                        else:
                            mapeh_computed_final = "Incomplete"
                        
                        # Mark that we have computed MAPEH values (to avoid later recomputation)
                        subjects[mapeh_key]['has_mapeh_computed'] = True
                        subjects[mapeh_key]['mapeh_computed_quarters'] = mapeh_computed_quarters
                        subjects[mapeh_key]['mapeh_computed_final'] = mapeh_computed_final
                        subjects[mapeh_key]['mapeh_quarter_status'] = mapeh_quarter_status
                    else:
                        # No MAPEH or missing subcomponents: use original quarterlies for final
                        if mapeh_key:
                            subjects[mapeh_key]['has_mapeh_computed'] = False
                    
                    # --- Compute final grades for all subjects ---
                    for name, info in subjects.items():
                        # Skip MAPEH if we already computed its final
                        if name == mapeh_key and info.get('has_mapeh_computed'):
                            # Already have computed_final stored
                            continue
                        
                        # For all other subjects, compute final from own quarters if possible
                        if info['has_quarters']:
                            info['computed_final'] = round_grade((info['q1'] + info['q2'] + info['q3'] + info['q4']) / 4.0)
                        else:
                            info['computed_final'] = "Incomplete"
                    
                    # --- Build results table ---
                    results = []
                    core_names = ['filipino', 'english', 'mathematics', 'science', 
                                  'araling panlipunan', 'edukasyon sa pagpapakatao',
                                  'technology and livelihood education', 'mapeh']
                    
                    total_for_general = 0
                    count_for_general = 0
                    
                    for name, info in subjects.items():
                        subject = name
                        # For MAPEH, use original reported quarterlies for display
                        if name == mapeh_key:
                            q1 = info['q1']
                            q2 = info['q2']
                            q3 = info['q3']
                            q4 = info['q4']
                            reported_final = info.get('reported_final')
                            
                            # Get computed values if available
                            if info.get('has_mapeh_computed'):
                                computed_final = info['mapeh_computed_final']
                                quarter_status = info['mapeh_quarter_status']
                                # Build status string for MAPEH quarters
                                status_str = ", ".join([f"{q.upper()}: {s}" for q, s in quarter_status.items()])
                                # Determine final grade status
                                if reported_final is not None:
                                    if computed_final != "Incomplete":
                                        final_status = "✅ Tama" if computed_final == reported_final else "❌ Mali"
                                    else:
                                        final_status = "⚠️ Kulang ang quarterly grades"
                                else:
                                    final_status = "⚠️ Walang nakasulat na final"
                            else:
                                # No subcomponents, treat like regular subject
                                computed_final = info.get('computed_final', "Incomplete")
                                status_str = "—"
                                if reported_final is not None:
                                    if info['has_quarters'] and computed_final != "Incomplete":
                                        final_status = "✅ Tama" if computed_final == reported_final else "❌ Mali"
                                    else:
                                        final_status = "⚠️ Kulang ang quarterly grades"
                                else:
                                    final_status = "⚠️ Walang nakasulat na final"
                        else:
                            # Regular subject
                            q1 = info['q1']
                            q2 = info['q2']
                            q3 = info['q3']
                            q4 = info['q4']
                            reported_final = info.get('reported_final')
                            computed_final = info.get('computed_final', "Incomplete")
                            status_str = ""
                            if reported_final is not None:
                                if info['has_quarters'] and computed_final != "Incomplete":
                                    final_status = "✅ Tama" if computed_final == reported_final else "❌ Mali"
                                else:
                                    final_status = "⚠️ Kulang ang quarterly grades"
                            else:
                                final_status = "⚠️ Walang nakasulat na final"
                        
                        # Determine if this subject is core for general average
                        normalized = name.lower()
                        is_core = any(normalized.startswith(core) or core in normalized for core in core_names)
                        
                        # Use the correct computed final for general average
                        # For MAPEH with subcomponents, use computed_final; for others, use their computed_final
                        if is_core:
                            if name == mapeh_key and info.get('has_mapeh_computed'):
                                final_for_avg = computed_final if computed_final != "Incomplete" else None
                            else:
                                final_for_avg = computed_final if computed_final != "Incomplete" else None
                            
                            if final_for_avg is not None and isinstance(final_for_avg, (int, float)):
                                total_for_general += final_for_avg
                                count_for_general += 1
                        
                        results.append({
                            "Subject": subject,
                            "Q1": q1 if q1 is not None else "—",
                            "Q2": q2 if q2 is not None else "—",
                            "Q3": q3 if q3 is not None else "—",
                            "Q4": q4 if q4 is not None else "—",
                            "Nakasulat na Final": reported_final if reported_final is not None else "—",
                            "Na-compute na Final": computed_final,
                            "Status (Final)": final_status,
                            "MAPEH Quarterly Check": status_str
                        })
                    
                    # Display subject grades table
                    if results:
                        st.subheader("📚 Subject Grades Check")
                        df = pd.DataFrame(results)
                        # Reorder columns
                        cols = ["Subject", "Q1", "Q2", "Q3", "Q4", "Nakasulat na Final", "Na-compute na Final", "Status (Final)", "MAPEH Quarterly Check"]
                        df = df[cols]
                        st.dataframe(df, use_container_width=True, height=400)
                    else:
                        st.warning("Walang nakitang subject sa report card.")
                    
                    # General Average
                    st.subheader("📈 General Average Check")
                    if count_for_general > 0:
                        computed_avg_decimal = total_for_general / count_for_general
                        computed_avg_rounded = round_grade(computed_avg_decimal)
                        reported_avg = data.get('reported_general_average')
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Nakasulat na General Average", reported_avg if reported_avg is not None else "—")
                        with col2:
                            st.metric("Na-compute ng System (batay sa core subjects)", computed_avg_rounded)
                        
                        if reported_avg is not None:
                            if int(computed_avg_rounded) == int(reported_avg):
                                st.success("✅ Tama ang General Average!")
                            else:
                                st.error("❌ Mali ang General Average. Pakisuri ang mga grades.")
                        else:
                            st.info("ℹ️ Walang nakasulat na General Average sa report card.")
                    else:
                        st.warning("Walang sapat na quarterly grades para sa core subjects. Hindi makalkula ang general average.")
                    
                    # Download button
                    if results:
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
