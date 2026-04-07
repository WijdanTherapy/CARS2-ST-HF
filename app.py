# clinician_app/app.py
"""
CARS2 Clinician App — ST/HF Assessment
Bilingual UI (Arabic/English), English-only report sent via email.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from datetime import date

from shared.cars2_data import (
    CARS2_ST_ITEMS, CARS2_HF_ITEMS, UI_TEXT,
    get_severity, get_tscore_percentile
)
from shared.clinician_report import generate_clinician_pdf
from shared.groq_narrative import generate_narrative
from shared.email_utils import send_report_email
from shared.qpc_parser import parse_qpc_pdf, get_qpc_summary

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CARS2 Clinician | Wijdan Therapy Center",
    page_icon="🧠",
    layout="wide",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  .block-container { padding-top: 1.5rem; }
  h1, h2, h3 { color: #1B2A4A; }
  .rating-row {
    background: #F8F9FA; border-radius: 6px;
    padding: 10px 14px; margin-bottom: 4px;
    border-left: 4px solid #2D6BA0;
  }
  .rating-row-elevated {
    background: #FEF9E7; border-radius: 6px;
    padding: 10px 14px; margin-bottom: 4px;
    border-left: 4px solid #E67E22;
  }
  .rating-row-severe {
    background: #FDEDEC; border-radius: 6px;
    padding: 10px 14px; margin-bottom: 4px;
    border-left: 4px solid #C0392B;
  }
  .section-banner {
    background: #1B2A4A; color: white;
    padding: 10px 16px; border-radius: 6px;
    margin: 16px 0 8px 0; font-weight: 600; font-size: 1em;
  }
  .stButton > button { border-radius: 6px; font-weight: 600; }
  div[data-testid="stRadio"] > div { flex-wrap: wrap; gap: 4px; }
  .step-active {
    background: #2D6BA0; color: white;
    padding: 8px; border-radius: 6px;
    text-align: center; font-size: 0.82em; font-weight: 600;
  }
  .step-done {
    background: #D5F5E3; color: #1B6B3A;
    padding: 8px; border-radius: 6px;
    text-align: center; font-size: 0.82em; font-weight: 600;
  }
  .step-todo {
    background: #F0F0F0; color: #888;
    padding: 8px; border-radius: 6px;
    text-align: center; font-size: 0.82em;
  }
</style>
""", unsafe_allow_html=True)

# ── Session state defaults ─────────────────────────────────────────────────────
DEFAULTS = {
    "lang": "en",
    "step": "demographics",
    "form_type": None,
    "submitted": False,
    "report_generated": False,
    "qpc_data": {},
    "admin_mode": False,
    "demo": {},
    "ratings_input": {},
    "clinician_notes": "",
    "cached_pdf": None,
    "cached_scores": {},
    "iq": 85,
}
for key, default in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🌐 Language / اللغة")
    lang_choice = st.radio(
        "lang_radio", ["English", "عربي"],
        label_visibility="collapsed", key="lang_radio"
    )
    st.session_state["lang"] = "ar" if lang_choice == "عربي" else "en"
    st.markdown("---")
    st.markdown("**CARS2 Clinician Assessment**  \nWijdan Therapy Center")
    st.markdown("---")
    st.markdown("**📋 Form Selection Guide:**")
    st.markdown(
        "**CARS2-ST** (Standard):\n"
        "- Age < 6, **or** IQ ≤ 79, **or** limited verbal ability\n\n"
        "**CARS2-HF** (High-Functioning):\n"
        "- Age ≥ 6 **and** IQ ≥ 80 **and** verbally fluent"
    )
    st.markdown("---")
    with st.expander("🔐 Admin"):
        admin_pw = st.text_input("Password", type="password", key="admin_pw_input")
        if st.button("Login", key="admin_btn"):
            try:
                correct = st.secrets.get("admin", {}).get("password", "wijdan2025")
            except Exception:
                correct = "wijdan2025"
            st.session_state["admin_mode"] = (admin_pw == correct)
            if st.session_state["admin_mode"]:
                st.success("Admin enabled")
            else:
                st.error("Incorrect password")

lang = st.session_state["lang"]
T = UI_TEXT[lang]
is_ar = lang == "ar"
dir_attr = 'dir="rtl"' if is_ar else ''

# ── Page Header ────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:#1B2A4A;padding:14px 22px;border-radius:8px;margin-bottom:14px;" {dir_attr}>
  <h1 style="color:white;margin:0;font-size:1.5em;">
    {'تقييم CARS-2 — نموذج الأخصائي' if is_ar else '🧠 CARS-2 Clinician Assessment'}
  </h1>
  <p style="color:#AED6F1;margin:4px 0 0 0;font-size:0.88em;">
    {'مقياس تصنيف اضطراب طيف التوحد عند الأطفال، الإصدار الثاني | مركز وجدان للعلاج النفسي'
     if is_ar else
     'Childhood Autism Rating Scale – 2nd Edition  |  Wijdan Therapy Center'}
  </p>
</div>
""", unsafe_allow_html=True)

# ── Step Indicator ─────────────────────────────────────────────────────────────
STEPS = ["demographics", "form_select", "assessment", "generate"]
STEP_LABELS_MAP = {
    "en": {"demographics": "1. Demographics", "form_select": "2. Form",
           "assessment": "3. Assessment", "generate": "4. Report"},
    "ar": {"demographics": "١. البيانات", "form_select": "٢. النموذج",
           "assessment": "٣. التقييم",   "generate": "٤. التقرير"},
}
curr_step = st.session_state["step"]
sc = st.columns(4)
for i, sk in enumerate(STEPS):
    with sc[i]:
        sl = STEP_LABELS_MAP[lang][sk]
        curr_idx = STEPS.index(curr_step)
        if sk == curr_step:
            cls = "step-active"
        elif i < curr_idx:
            cls = "step-done"
        else:
            cls = "step-todo"
        st.markdown(f'<div class="{cls}">{sl}</div>', unsafe_allow_html=True)
st.markdown("")

# ═══════════════════════════════════════════════════════════════════════════════
# SUBMITTED RESULTS SCREEN
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.get("submitted") and st.session_state.get("report_generated"):
    scores = st.session_state.get("cached_scores", {})
    sev_color = scores.get("sev_color", "#27AE60")

    st.markdown(f"""
    <div style="background:{sev_color}18;border:2px solid {sev_color};
                padding:20px;border-radius:10px;margin-bottom:16px;" {dir_attr}>
      <h2 style="color:{sev_color};margin:0 0 12px 0;">
        {'✅ تم إنشاء التقرير وإرساله' if is_ar else '✅ Report Generated & Sent'}
      </h2>
      <table style="width:100%;border-collapse:separate;border-spacing:6px;">
        <tr>
          <td style="background:white;padding:12px;border-radius:6px;text-align:center;width:25%">
            <div style="font-size:1.8em;font-weight:700;color:#1B2A4A;">{scores.get("raw","—")}</div>
            <div style="font-size:0.75em;color:#7F8C8D;">{'الدرجة الخام' if is_ar else 'Raw Score'}</div>
          </td>
          <td style="background:white;padding:12px;border-radius:6px;text-align:center;width:20%">
            <div style="font-size:1.8em;font-weight:700;color:#1B2A4A;">{scores.get("t","—")}</div>
            <div style="font-size:0.75em;color:#7F8C8D;">T-Score</div>
          </td>
          <td style="background:white;padding:12px;border-radius:6px;text-align:center;width:20%">
            <div style="font-size:1.8em;font-weight:700;color:#1B2A4A;">{scores.get("pct","—")}</div>
            <div style="font-size:0.75em;color:#7F8C8D;">{'الرتبة المئوية' if is_ar else 'Percentile'}</div>
          </td>
          <td style="background:{sev_color};padding:12px;border-radius:6px;text-align:center;width:35%">
            <div style="font-size:1em;font-weight:700;color:white;">{scores.get("sev_label","—")}</div>
            <div style="font-size:0.75em;color:rgba(255,255,255,0.8);">{'التصنيف' if is_ar else 'Severity Group'}</div>
          </td>
        </tr>
      </table>
    </div>
    """, unsafe_allow_html=True)

    if scores.get("email_sent"):
        st.success("📧 " + ("تم إرسال التقرير إلى بريد المركز بنجاح." if is_ar
                             else "Report successfully sent to clinic email."))
    else:
        st.warning("⚠️ " + ("فشل إرسال البريد الإلكتروني. تحقق من إعدادات SMTP في Streamlit Secrets."
                             if is_ar else
                             "Email delivery failed. Check SMTP credentials in Streamlit Secrets."))

    st.markdown("")
    if st.button("📋 " + ("تقييم جديد" if is_ar else "New Assessment"), type="primary"):
        for k in list(DEFAULTS.keys()):
            st.session_state[k] = DEFAULTS[k]
        st.rerun()
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: DEMOGRAPHICS
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state["step"] == "demographics":
    st.markdown(
        f'<div class="section-banner">{"١. بيانات الحالة" if is_ar else "1. Client Demographics"}</div>',
        unsafe_allow_html=True
    )

    with st.expander(
        "📎 " + ("رفع ملف QPC للوالدين — اختياري" if is_ar else "Upload Parent QPC PDF — Optional"),
        expanded=True
    ):
        st.caption(
            "ارفع ملف PDF لاستبيان الوالدين لدمجه في التقرير النهائي."
            if is_ar else
            "Upload the parent/caregiver QPC PDF to include their data in the final report."
        )
        uploaded_qpc = st.file_uploader("QPC PDF", type=["pdf"],
                                         label_visibility="collapsed", key="qpc_upload")
        if uploaded_qpc:
            parsed = parse_qpc_pdf(uploaded_qpc.read())
            if parsed:
                st.session_state["qpc_data"] = parsed
                summary = get_qpc_summary(parsed)
                st.success(
                    f"✅ {len(parsed)} items parsed — "
                    f"Severe: {summary.get('2',0)} | Mild: {summary.get('1',0)} | OK: {summary.get('0',0)}"
                )
            else:
                st.warning("⚠️ Could not parse QPC data. Continuing without it.")
                st.session_state["qpc_data"] = {}

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    saved_demo = st.session_state.get("demo", {})

    with c1:
        child_name = st.text_input(
            T["child_name"] + " *", key="d_name",
            value=saved_demo.get("child_name", ""),
            placeholder="Full name in English"
        )
        age_val = st.number_input(
            T["child_age"] + " *", min_value=1, max_value=30,
            value=saved_demo.get("age", 6), key="d_age"
        )
        gender_opts = [T["male"], T["female"]]
        saved_g = saved_demo.get("gender", T["male"])
        g_idx = gender_opts.index(saved_g) if saved_g in gender_opts else 0
        gender_val = st.radio(T["child_gender"] + " *", gender_opts,
                               horizontal=True, key="d_gender", index=g_idx)

    with c2:
        dob_val = st.text_input(T["dob"], key="d_dob",
                                  value=saved_demo.get("dob", ""),
                                  placeholder="DD/MM/YYYY")
        case_id_val = st.text_input(T["case_id"], key="d_caseid",
                                      value=saved_demo.get("case_id", ""),
                                      placeholder="Optional")
        ethnic_val = st.text_input(T["ethnic_bg"], key="d_ethnic",
                                     value=saved_demo.get("ethnic_bg", ""),
                                     placeholder="Optional")

    with c3:
        rater_val = st.text_input(T["rater_name"] + " *", key="d_rater",
                                    value=saved_demo.get("rater_name", ""))
        info_from_val = st.text_input(
            T["info_from"], key="d_infofrom",
            value=saved_demo.get("info_from", ""),
            placeholder="e.g. Direct observation + parent interview"
        )

    st.markdown("")
    _, col_btn = st.columns([3, 1])
    with col_btn:
        if st.button("Next →" if not is_ar else "التالي →",
                     type="primary", use_container_width=True, key="next_demo"):
            if not child_name.strip():
                st.error("⚠️ " + ("يرجى إدخال اسم الطفل." if is_ar else "Please enter the child's name."))
            elif not rater_val.strip():
                st.error("⚠️ " + ("يرجى إدخال اسم الفاحص." if is_ar else "Please enter the rater's name."))
            else:
                st.session_state["demo"] = {
                    "child_name": child_name.strip(),
                    "age": age_val,
                    "gender": gender_val,
                    "dob": dob_val,
                    "case_id": case_id_val,
                    "ethnic_bg": ethnic_val,
                    "rater_name": rater_val.strip(),
                    "info_from": info_from_val or "Direct observation",
                    "test_date": date.today(),
                }
                st.session_state["step"] = "form_select"
                st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: FORM SELECTION
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state["step"] == "form_select":
    demo = st.session_state.get("demo", {})
    age = demo.get("age", 6)

    st.markdown(
        f'<div class="section-banner">{"٢. اختيار نموذج التقييم" if is_ar else "2. Form Selection"}</div>',
        unsafe_allow_html=True
    )
    st.markdown(f"**{demo.get('child_name','')}  —  {age} {'yr' if not is_ar else 'سنة'}**")
    st.markdown("")

    c1, c2 = st.columns(2)
    with c1:
        iq_val = st.number_input(
            T["iq_level"] + " (estimated)",
            min_value=20, max_value=160,
            value=st.session_state.get("iq", 85),
            key="iq_input"
        )
    with c2:
        verbal_opts = [T["yes"], T["no"]]
        verbal_val = st.radio(T["verbal_fluent"], verbal_opts,
                               horizontal=True, key="verbal_input")
    verbal_fluent = (verbal_val == T["yes"])

    st.markdown("---")
    # Criteria display
    c_met, c_fail = [], []
    if age >= 6:   c_met.append(f"✅ Age ≥ 6  ({age} yr)")
    else:          c_fail.append(f"❌ Age < 6  ({age} yr)")
    if iq_val >= 80: c_met.append(f"✅ IQ ≥ 80  ({iq_val})")
    else:            c_fail.append(f"❌ IQ < 80  ({iq_val})")
    if verbal_fluent: c_met.append("✅ Verbally fluent")
    else:             c_fail.append("❌ Not verbally fluent")

    recommended = "HF" if not c_fail else "ST"

    col_crit, col_rec = st.columns(2)
    with col_crit:
        st.markdown(f"**{'المعايير:' if is_ar else 'Criteria:'}**")
        for c in c_met:  st.markdown(f"  {c}")
        for c in c_fail: st.markdown(f"  {c}")
    with col_rec:
        rc = "#2D6BA0" if recommended == "HF" else "#27AE60"
        st.markdown(f"""
        <div style="background:{rc}18;border:2px solid {rc};padding:14px;
                    border-radius:8px;text-align:center;">
          <div style="font-size:0.8em;color:#7F8C8D;">
          {'النموذج الموصى به' if is_ar else 'Recommended Form'}
          </div>
          <div style="font-size:2.2em;font-weight:700;color:{rc};">
          CARS2-{recommended}
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")
    override = st.checkbox(
        ("تجاوز التوصية" if is_ar else "Override recommendation"), key="override_chk"
    )
    if override:
        fc = st.radio(
            ("اختر النموذج" if is_ar else "Select form"),
            ["CARS2-ST (Standard)", "CARS2-HF (High-Functioning)"],
            key="form_override_choice", horizontal=True
        )
        final_form = "ST" if "ST" in fc else "HF"
    else:
        final_form = recommended

    col_back, _, col_next = st.columns([1, 3, 1])
    with col_back:
        if st.button("← " + ("رجوع" if is_ar else "Back"), use_container_width=True):
            st.session_state["step"] = "demographics"
            st.rerun()
    with col_next:
        if st.button("Start →" if not is_ar else "ابدأ →",
                     type="primary", use_container_width=True, key="start_btn"):
            st.session_state["form_type"] = final_form
            st.session_state["iq"] = iq_val
            st.session_state["ratings_input"] = {}
            st.session_state["step"] = "assessment"
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: ASSESSMENT
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state["step"] == "assessment":
    form_type = st.session_state.get("form_type", "ST")
    demo = st.session_state.get("demo", {})
    items = CARS2_ST_ITEMS if form_type == "ST" else CARS2_HF_ITEMS
    child_name = demo.get("child_name", "Client")
    age = demo.get("age", 6)

    st.markdown(
        f'<div class="section-banner">'
        f'{"٣. التقييم" if is_ar else f"3. CARS2-{form_type} — Ratings"}'
        f'  |  {child_name}'
        f'</div>',
        unsafe_allow_html=True
    )

    RATING_DISPLAY = ["1", "1.5", "2", "2.5", "3", "3.5", "4"]

    # Live score banner
    live_ratings = []
    for item in items:
        val_str = st.session_state.get(f"rating_item_{item['id']}", "1")
        try:
            live_ratings.append(float(val_str))
        except Exception:
            live_ratings.append(1.0)

    live_raw = round(sum(live_ratings), 1)
    live_sev = get_severity(form_type, live_raw, age)
    live_color = live_sev["color"] if live_sev else "#2D6BA0"
    elevated_n = sum(1 for r in live_ratings if r >= 2.5)

    st.markdown(f"""
    <div style="background:{live_color}18;border:1.5px solid {live_color};
                border-radius:8px;padding:10px 18px;margin-bottom:12px;
                display:flex;gap:24px;align-items:center;" {dir_attr}>
      <div style="text-align:center;min-width:60px;">
        <span style="font-size:1.7em;font-weight:700;color:{live_color};">{live_raw}</span>
        <div style="font-size:0.72em;color:#7F8C8D;">{'درجة' if is_ar else 'Raw'}</div>
      </div>
      <div style="text-align:center;min-width:60px;">
        <span style="font-size:1.7em;font-weight:700;color:{live_color};">{elevated_n}/15</span>
        <div style="font-size:0.72em;color:#7F8C8D;">{'مرتفعة' if is_ar else 'Elevated'}</div>
      </div>
      <div style="flex:1;">
        <span style="font-size:0.95em;font-weight:600;color:{live_color};">
          {live_sev['label'] if live_sev else '—'}
        </span>
        <div style="font-size:0.72em;color:#7F8C8D;">
          {'تصنيف مؤقت — يتحدث آلياً' if is_ar else 'Provisional — updates live'}
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Rating items
    saved_ratings = st.session_state.get("ratings_input", {})

    for item in items:
        iid = item["id"]
        item_name = item["ar"] if is_ar else item["en"]
        key = f"rating_item_{iid}"

        # Get current value for row coloring
        val_str = st.session_state.get(key, "1")
        try:
            cv = float(val_str)
        except Exception:
            cv = 1.0

        row_class = (
            "rating-row-severe" if cv >= 3.0 else
            "rating-row-elevated" if cv >= 2.5 else
            "rating-row"
        )

        st.markdown(
            f'<div class="{row_class}" {dir_attr}><b>{iid}. {item_name}</b></div>',
            unsafe_allow_html=True
        )

        with st.expander("📖 " + ("معايير التقييم" if is_ar else "Rating criteria")):
            for rv in [1, 2, 3, 4]:
                desc = item["ratings"][rv]["ar" if is_ar else "en"]
                badge = {1: "🟢 **1**", 2: "🟡 **2**", 3: "🟠 **3**", 4: "🔴 **4**"}[rv]
                st.markdown(f"{badge} — {desc}")
                if rv < 4:
                    st.caption("  1.5 / 2.5 / 3.5 = behavior falls between adjacent ratings")

        # Restore saved value
        sv = saved_ratings.get(iid, None)
        def_idx = (RATING_DISPLAY.index(str(sv)) if sv is not None and str(sv) in RATING_DISPLAY else 0)

        st.radio(
            label=item_name, options=RATING_DISPLAY,
            horizontal=True, key=key,
            label_visibility="collapsed", index=def_idx,
        )
        st.markdown("")

    st.markdown("---")
    clinician_notes = st.text_area(
        T["clinician_notes"], key="clin_notes",
        value=st.session_state.get("clinician_notes", ""),
        height=100,
        placeholder=(
            "Clinical observations, behavioral notes, session conditions..."
            if not is_ar else
            "ملاحظات إكلينيكية، ملاحظات سلوكية، ظروف الجلسة..."
        )
    )

    col_back, _, col_sub = st.columns([1, 2, 2])
    with col_back:
        if st.button("← " + ("رجوع" if is_ar else "Back"), use_container_width=True):
            st.session_state["step"] = "form_select"
            st.rerun()
    with col_sub:
        if st.button(
            ("✅ إرسال وإنشاء التقرير" if is_ar else "✅ Submit & Generate Report"),
            type="primary", use_container_width=True, key="submit_btn"
        ):
            final_r = {}
            for item in items:
                k = f"rating_item_{item['id']}"
                try:
                    final_r[item["id"]] = float(st.session_state.get(k, "1"))
                except Exception:
                    final_r[item["id"]] = 1.0
            st.session_state["ratings_input"] = final_r
            st.session_state["clinician_notes"] = clinician_notes
            st.session_state["report_generated"] = False  # ensure fresh generate
            st.session_state["submitted"] = False
            st.session_state["step"] = "generate"
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: GENERATE & SEND  — guarded by report_generated flag
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state["step"] == "generate":
    if st.session_state.get("report_generated"):
        # Already done — rerun to show results screen
        st.rerun()

    demo = st.session_state.get("demo", {})
    form_type = st.session_state.get("form_type", "ST")
    ratings_input = st.session_state.get("ratings_input", {})
    clinician_notes = st.session_state.get("clinician_notes", "")
    qpc_data = st.session_state.get("qpc_data", {})
    items = CARS2_ST_ITEMS if form_type == "ST" else CARS2_HF_ITEMS

    st.markdown(
        f'<div class="section-banner">{"٤. جارٍ إنشاء التقرير وإرساله..." if is_ar else "4. Generating & Sending Report..."}</div>',
        unsafe_allow_html=True
    )

    progress = st.progress(0, text="Starting...")

    # Step 1: Scores
    progress.progress(10, text="Calculating scores...")
    ratings_list = [ratings_input.get(item["id"], 1.0) for item in items]
    raw_score = round(sum(ratings_list), 1)
    age = demo.get("age", 6)
    severity_info = get_severity(form_type, raw_score, age)
    t_score, percentile = get_tscore_percentile(form_type, raw_score)

    # Step 2: Narrative
    progress.progress(30, text="Generating AI clinical narrative...")
    narrative = generate_narrative(
        child_name=demo.get("child_name", "Client"),
        age=age,
        gender=demo.get("gender", ""),
        form_type=form_type,
        raw_score=raw_score,
        t_score=t_score,
        percentile=percentile,
        severity_info=severity_info,
        items_data=items,
        ratings=ratings_list,
        qpc_data=qpc_data if qpc_data else None,
    )

    # Step 3: PDF
    progress.progress(65, text="Building PDF report...")
    child_name_str = demo.get("child_name", "Client")
    pdf_bytes = generate_clinician_pdf(
        child_name=child_name_str,
        age=age,
        gender=demo.get("gender", ""),
        dob=demo.get("dob", ""),
        ethnic_bg=demo.get("ethnic_bg", ""),
        case_id=demo.get("case_id", ""),
        rater_name=demo.get("rater_name", ""),
        info_from=demo.get("info_from", ""),
        test_date=demo.get("test_date", date.today()),
        form_type=form_type,
        items_data=items,
        ratings=ratings_list,
        raw_score=raw_score,
        t_score=t_score,
        percentile=percentile,
        severity_info=severity_info,
        clinician_notes=clinician_notes,
        narrative=narrative,
        qpc_data=qpc_data if qpc_data else None,
    )

    # Step 4: Email
    progress.progress(85, text="Sending email...")
    subject = f"CARS2-{form_type} Assessment: {child_name_str} | {date.today()}"
    body = (
        f"CARS2-{form_type} assessment completed.\n\n"
        f"Client: {child_name_str}\n"
        f"Age: {age} | Gender: {demo.get('gender','')}\n"
        f"Rater: {demo.get('rater_name','')}\n"
        f"Date: {demo.get('test_date', date.today())}\n"
        f"Raw Score: {raw_score} | T-Score: {t_score} | Percentile: {percentile}\n"
        f"Severity: {severity_info['label'] if severity_info else 'Unknown'}\n"
        f"QPC: {'Yes' if qpc_data else 'No'}\n\n"
        f"Full PDF attached.\n-- Wijdan Therapy Center CARS2 System"
    )
    email_sent = send_report_email(
        pdf_bytes=pdf_bytes,
        subject=subject,
        body=body,
        filename=f"CARS2_{form_type}_{child_name_str.replace(' ','_')}_{date.today()}.pdf"
    )

    progress.progress(100, text="✅ Done!")

    # Cache & mark done
    sev_color = severity_info["color"] if severity_info else "#27AE60"
    st.session_state["cached_scores"] = {
        "raw": raw_score,
        "t": t_score,
        "pct": percentile,
        "sev_label": severity_info["label"] if severity_info else "Unknown",
        "sev_color": sev_color,
        "email_sent": email_sent,
    }
    st.session_state["cached_pdf"] = pdf_bytes
    st.session_state["report_generated"] = True
    st.session_state["submitted"] = True
    st.rerun()
