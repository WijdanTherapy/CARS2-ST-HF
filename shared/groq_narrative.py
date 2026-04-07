# shared/groq_narrative.py
"""
Generates clinical narrative using Groq API (llama-3.3-70b-versatile).
"""
import streamlit as st

MODEL = "llama-3.3-70b-versatile"


def _build_prompt(
    child_name, age, gender, form_type, raw_score,
    t_score, percentile, severity_label,
    items_data, ratings, qpc_data=None
):
    domain_lines = "\n".join([
        f"  {i+1}. {items_data[i]['en']}: {ratings[i]}/4"
        for i in range(len(ratings))
    ])
    elevated = [
        f"{items_data[i]['en']} ({ratings[i]})"
        for i in range(len(ratings)) if ratings[i] >= 2.5
    ]
    qpc_block = ""
    if qpc_data:
        severe = [k for k, v in qpc_data.items() if str(v) == "2"]
        mild   = [k for k, v in qpc_data.items() if str(v) == "1"]
        qpc_block = (
            f"\n\nParent/Caregiver QPC Report:\n"
            f"  Severe concerns reported: {', '.join(severe) if severe else 'None'}\n"
            f"  Mild-moderate concerns: {', '.join(mild) if mild else 'None'}"
        )

    pronoun = "he" if "Male" in (gender or "") or "ذكر" in (gender or "") else "she"
    pronoun_p = "his" if pronoun == "he" else "her"

    return f"""You are a licensed clinical psychologist writing a professional assessment report.
Generate a comprehensive clinical narrative for the following CARS-2 assessment results.
Write in clear, professional English. Use 4–5 well-structured paragraphs.
Do NOT include scores or numbers in the narrative — describe the clinical picture in qualitative terms.
Do NOT suggest a definitive diagnosis. Use language such as "consistent with," "may indicate," "warrants further evaluation."
Do NOT use bullet points. Write flowing paragraphs only.

CLIENT:
  Name: {child_name}
  Age: {age} years
  Gender: {gender or "Not specified"}
  Pronoun: {pronoun}/{pronoun_p}
  Form: CARS2-{form_type}

RESULTS:
  Total Raw Score: {raw_score}
  T-Score: {t_score}
  Percentile: {percentile}
  Severity Classification: {severity_label}

DOMAIN RATINGS (1=age-appropriate, 4=severely abnormal):
{domain_lines}

CLINICALLY ELEVATED DOMAINS (≥2.5):
  {', '.join(elevated) if elevated else 'None'}{qpc_block}

Write the narrative now. Paragraph 1: Introduction and referral context.
Paragraph 2: Communication and social interaction observations.
Paragraph 3: Sensory, behavioral, and adaptive patterns.
Paragraph 4: Cognitive and emotional functioning.
Paragraph 5: Summary, recommendations, and limitations.
"""


def generate_narrative(
    child_name, age, gender, form_type, raw_score,
    t_score, percentile, severity_info,
    items_data, ratings, qpc_data=None
) -> str:
    """
    Call Groq API to generate clinical narrative.
    Returns narrative string. Falls back to a structured placeholder on error.
    """
    severity_label = severity_info["label"] if severity_info else "Unknown"
    prompt = _build_prompt(
        child_name, age, gender, form_type, raw_score,
        t_score, percentile, severity_label,
        items_data, ratings, qpc_data
    )

    try:
        from groq import Groq
        api_key = st.secrets["groq"]["api_key"]
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert clinical psychologist specializing in autism spectrum disorder assessment. "
                        "You write professional, nuanced, and clinically accurate narrative reports. "
                        "Your writing is compassionate, precise, and evidence-informed."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=1500,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        # Fallback placeholder narrative
        elevated = [
            items_data[i]["en"]
            for i in range(len(ratings)) if ratings[i] >= 2.5
        ]
        severity_label = severity_info["label"] if severity_info else "Unknown"
        pronoun = "he" if "Male" in (gender or "") or "ذكر" in (gender or "") else "she"
        pronoun_p = "his" if pronoun == "he" else "her"

        fallback = (
            f"{child_name} is a {age}-year-old individual referred for a structured behavioral assessment "
            f"using the Childhood Autism Rating Scale, Second Edition (CARS-2). "
            f"The CARS2-{form_type} form was selected based on {pronoun_p} age and estimated level of functioning. "
            f"The assessment was conducted through direct clinical observation and, where available, "
            f"parent/caregiver report via the CARS2-QPC.\n\n"
        )
        if elevated:
            fallback += (
                f"During the assessment, the following domains were rated at or above the clinical threshold: "
                f"{', '.join(elevated[:5])}{'...' if len(elevated) > 5 else ''}. "
                f"These areas reflect behavioral patterns that diverge meaningfully from age-typical expectations "
                f"and are associated with features of Autism Spectrum Disorder.\n\n"
            )
        fallback += (
            f"The overall profile obtained is classified as: {severity_label}. "
            f"This classification reflects the cumulative severity and breadth of behavioral features "
            f"observed across the 15 rated domains. The clinician is encouraged to contextualize these "
            f"findings within the broader developmental history and multi-informant data.\n\n"
            f"It is important to note that the CARS-2 is a behavioral rating scale and does not constitute "
            f"a diagnosis of Autism Spectrum Disorder in isolation. A comprehensive evaluation — including "
            f"developmental history, cognitive assessment, speech-language evaluation, and input from multiple "
            f"informants across settings — is recommended to arrive at a differential diagnosis.\n\n"
            f"Intervention planning should be guided by the specific domain profiles identified in this "
            f"assessment, with particular attention to areas of greatest functional impact. "
            f"Follow-up evaluation at regular intervals is advised to track developmental progress.\n\n"
            f"[NOTE: AI narrative generation was unavailable. This is an auto-generated placeholder. "
            f"Please replace with a clinician-authored narrative. Error: {str(e)[:100]}]"
        )
        return fallback
