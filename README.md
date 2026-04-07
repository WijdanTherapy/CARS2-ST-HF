# CARS2 Dual-App System
## Wijdan Therapy Center — Clinical Assessment Platform

---

## Overview

Two separate Streamlit apps for the CARS-2 assessment workflow:

| App | Purpose | Who Uses It |
|-----|---------|-------------|
| `qpc_app/app.py` | Parent/caregiver QPC questionnaire | Parents / Caregivers |
| `clinician_app/app.py` | CARS2-ST / CARS2-HF assessment | Clinicians |

Both apps:
- Support **Arabic / English UI toggle**
- Generate **English-only PDF reports**
- Send reports automatically to **wijdan.psyc@gmail.com**
- Never show or allow download of the report in the UI

---

## Project Structure

```
cars2_system/
├── qpc_app/
│   └── app.py                  # QPC Streamlit app
├── clinician_app/
│   └── app.py                  # Clinician Streamlit app
├── shared/
│   ├── cars2_data.py           # All CARS2 items, scoring logic, translations
│   ├── qpc_report.py           # QPC PDF generator
│   ├── clinician_report.py     # Clinician PDF generator (with charts)
│   ├── groq_narrative.py       # AI narrative via Groq API
│   ├── qpc_parser.py           # Parse QPC data from uploaded PDF
│   └── email_utils.py          # Gmail SMTP email sender
├── .streamlit/
│   └── secrets.toml.template   # Copy → secrets.toml and fill in
├── requirements.txt
└── README.md
```

---

## Local Setup

### 1. Clone / download the project

```bash
cd cars2_system
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure secrets

Copy the template and fill in your credentials:

```bash
cp .streamlit/secrets.toml.template .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml`:

```toml
[email]
sender = "yourapp@gmail.com"
password = "your_gmail_app_password"   # Gmail App Password (not your real password)

[groq]
api_key = "gsk_your_groq_api_key"

[admin]
password = "your_admin_password"
```

> **Gmail App Password**: Go to myaccount.google.com → Security → 2-Step Verification → App Passwords. Generate a password for "Mail".

### 4. Run the apps

**QPC App:**
```bash
streamlit run qpc_app/app.py --server.port 8501
```

**Clinician App:**
```bash
streamlit run clinician_app/app.py --server.port 8502
```

---

## Streamlit Cloud Deployment

### Step 1: Push to GitHub

Create **two separate GitHub repos** (or two branches), one per app:

```
repo-1: cars2-qpc     → contains qpc_app/ + shared/ + requirements.txt
repo-2: cars2-clinician → contains clinician_app/ + shared/ + requirements.txt
```

Or use a **monorepo** with two Streamlit Cloud apps pointing to different `app.py` files.

### Step 2: Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **New app**
3. Connect your GitHub repo
4. Set **Main file path**:
   - QPC: `qpc_app/app.py`
   - Clinician: `clinician_app/app.py`
5. Click **Advanced settings** → **Secrets**
6. Paste the contents of your `secrets.toml` (without the filename header)

### Step 3: Set secrets in Streamlit Cloud

In the Streamlit Cloud dashboard → your app → Settings → Secrets, paste:

```toml
[email]
sender = "yourapp@gmail.com"
password = "your_gmail_app_password"

[groq]
api_key = "gsk_your_key"

[admin]
password = "your_admin_password"
```

---

## Workflow

### QPC Flow (Parent/Caregiver)
1. Parent opens QPC app URL
2. Selects language (Arabic / English)
3. Enters child demographics
4. Completes all 6 sections of the QPC questionnaire
5. Clicks **Submit**
6. App generates PDF and sends to wijdan.psyc@gmail.com
7. Parent sees only "Thank you" message

### Clinician Flow
1. Clinician opens Clinician app URL
2. Selects language
3. Optionally uploads QPC PDF (to extract parent data)
4. Enters/confirms demographics
5. System recommends ST or HF form based on age/IQ/verbal fluency
6. Clinician rates all 15 CARS2 items (1–4 scale, with half-points)
7. Adds optional clinical notes
8. Clicks **Submit & Generate Report**
9. System:
   - Calculates raw score, T-score, percentile, severity group
   - Generates domain profile chart
   - Calls Groq API for AI clinical narrative
   - Builds premium PDF report
   - Sends to wijdan.psyc@gmail.com
10. Clinician sees score summary on screen (no PDF download)

---

## Report Contents (Clinician PDF)

1. **Demographics** — client info, rater, date, form used
2. **Scores & Classification** — raw score, T-score, percentile, severity group (color-coded)
3. **Domain Profile Chart** — line chart of all 15 domains vs clinical threshold
4. **Item Ratings Table** — all 15 items with rating and level indicator
5. **QPC Summary** (if uploaded) — parent ratings with flagged elevations
6. **Integrated Interpretation** — clinician vs caregiver comparison
7. **AI Clinical Narrative** — Groq-generated professional paragraphs
8. **Clinician's Observations** — free-text notes

---

## Scoring Logic

### CARS2-ST Severity Groups
| Age | Minimal-to-No | Mild-Moderate | Severe |
|-----|--------------|---------------|--------|
| < 13 | 15–29.5 | 30–36.5 | ≥37 |
| ≥ 13 | 15–27.5 | 28–34.5 | ≥35 |

### CARS2-HF Severity Groups
| Age | Minimal-to-No | Mild-Moderate | Severe |
|-----|--------------|---------------|--------|
| All | 15–27.5 | 28–33.5 | ≥34 |

---

## Future Upgrades (already structured for)

- **Auto-link QPC to Clinician**: Replace manual upload with session token
- **Clinician Dashboard**: Admin view of all past cases
- **Multi-case Management**: Case list with search and filter
- **PDF Archive**: Store reports in Supabase or Google Drive

---

## Important Notes

- The CARS-2 is a **clinician-rated** instrument — not a self-report tool
- The QPC is **unscored** — it provides supplementary parent observations
- This system does **not provide a diagnosis** — only structured assessment data
- Reports include a disclaimer that diagnosis requires comprehensive evaluation

---

*Developed for Wijdan Therapy Center. CARS-2 © Western Psychological Services.*
