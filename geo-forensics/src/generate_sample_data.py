"""
generate_sample_data.py - יצירת נתונים סינתטיים לפיתוח
=======================================================
יוצר קובץ Excel מדומה של נתוני PFAS באזור נחל הקישון (מפרץ חיפה).

הנתונים מדמים:
- מקור תעשייתי עם ריכוז גבוה (פרופיל PFOS-dominant)
- פלומה של זיהום שהולכת ונחלשת במורד הזרם
- תחנות רקע עם פרופיל כימי שונה
- מט"ש עם חתימה ייחודית

הקובץ נוצר בפורמט Excel עם שמות עמודות בעברית,
בדיוק כמו שהיה מגיע מרשות המים.

הרצה:
    python -m src.generate_sample_data
"""

import random
from datetime import datetime, timedelta

import pandas as pd


def generate_sample_data() -> pd.DataFrame:
    """יוצר DataFrame סינתטי של נתוני PFAS."""

    random.seed(42)

    # PFAS compounds
    compounds = ["PFOS", "PFOA", "PFHxS", "PFNA", "PFDA", "PFUnDA", "PFBS", "GenX"]

    # =================================================================
    # הגדרת תחנות - ITM coordinates באזור מפרץ חיפה / נחל הקישון
    # =================================================================
    stations = []

    # --- מקור חשוד: אזור תעשייתי (ריכוז גבוה, פרופיל PFOS-dominant) ---
    source_profile = {
        "PFOS": 8.5, "PFOA": 3.2, "PFHxS": 1.8, "PFNA": 0.5,
        "PFDA": 0.3, "PFUnDA": 0.1, "PFBS": 0.8, "GenX": 0.2,
    }
    stations.append({
        "name": "קידוח תעשייתי - סולתם",
        "x": 198500, "y": 741200,
        "source_type": "קידוח ניטור",
        "profile": source_profile,
        "noise": 0.15,
    })

    # --- פלומה: תחנות במורד הזרם (ריכוז יורד, פרופיל דומה) ---
    plume_stations = [
        ("קידוח K-12", 198800, 740800, 0.75),  # 400m downstream, 75% of source
        ("קידוח K-15", 199200, 740400, 0.50),  # 800m, 50%
        ("קידוח K-18", 199600, 739900, 0.30),  # 1300m, 30%
        ("קידוח K-22", 200100, 739400, 0.15),  # 1800m, 15%
        ("קידוח K-25", 200500, 738900, 0.08),  # 2300m, 8%
        ("קידוח K-28", 200900, 738400, 0.04),  # 2800m, 4%
    ]
    for name, x, y, factor in plume_stations:
        stations.append({
            "name": name,
            "x": x, "y": y,
            "source_type": "קידוח ניטור",
            "profile": {k: v * factor for k, v in source_profile.items()},
            "noise": 0.2,
        })

    # --- מט"ש: פרופיל שונה (PFOA-dominant, GenX גבוה) ---
    wwtp_profile = {
        "PFOS": 0.8, "PFOA": 4.5, "PFHxS": 0.3, "PFNA": 1.2,
        "PFDA": 0.6, "PFUnDA": 0.2, "PFBS": 2.1, "GenX": 1.8,
    }
    wwtp_stations = [
        ("מט\"ש חיפה - פליטה", 200200, 742000),
        ("קידוח M-3 (ליד מט\"ש)", 200500, 741700),
        ("קידוח M-7 (מורד מט\"ש)", 200900, 741300),
    ]
    for i, (name, x, y) in enumerate(wwtp_stations):
        factor = [1.0, 0.6, 0.3][i]
        stations.append({
            "name": name,
            "x": x, "y": y,
            "source_type": "מט\"ש" if i == 0 else "קידוח ניטור",
            "profile": {k: v * factor for k, v in wwtp_profile.items()},
            "noise": 0.2,
        })

    # --- רקע: תחנות רחוקות עם ריכוז נמוך ופרופיל שונה ---
    bg_profile = {
        "PFOS": 0.05, "PFOA": 0.08, "PFHxS": 0.02, "PFNA": 0.01,
        "PFDA": 0.01, "PFUnDA": 0.0, "PFBS": 0.03, "GenX": 0.01,
    }
    bg_stations = [
        ("קידוח B-1 (כרמל)", 194500, 743500),
        ("קידוח B-2 (נשר)", 196000, 744000),
        ("קידוח B-3 (טירת כרמל)", 195000, 738000),
        ("מעיין B-4", 193000, 742000),
        ("קידוח B-5 (קריות)", 202000, 743000),
    ]
    for name, x, y in bg_stations:
        stations.append({
            "name": name,
            "x": x, "y": y,
            "source_type": "מעיין" if "מעיין" in name else "קידוח הפקה",
            "profile": bg_profile,
            "noise": 0.4,
        })

    # --- נחל: תחנות מים עיליים ---
    stream_profile = {
        "PFOS": 2.0, "PFOA": 1.5, "PFHxS": 0.8, "PFNA": 0.3,
        "PFDA": 0.15, "PFUnDA": 0.05, "PFBS": 0.5, "GenX": 0.1,
    }
    stream_stations = [
        ("נחל הקישון - גשר הזיו", 199000, 741500, 1.0),
        ("נחל הקישון - יוקנעם", 197000, 737000, 0.4),
        ("נחל הקישון - שפך", 201000, 742500, 0.8),
    ]
    for name, x, y, factor in stream_stations:
        stations.append({
            "name": name,
            "x": x, "y": y,
            "source_type": "מים עיליים",
            "profile": {k: v * factor for k, v in stream_profile.items()},
            "noise": 0.3,
        })

    # =================================================================
    # יצירת שורות נתונים (כל תחנה × כל תרכובת × 3 תאריכי דיגום)
    # =================================================================
    rows = []
    base_dates = [
        datetime(2024, 3, 15),
        datetime(2024, 9, 20),
        datetime(2025, 3, 10),
    ]

    for station in stations:
        for date in base_dates:
            # Add some random variation to date
            actual_date = date + timedelta(days=random.randint(-5, 5))

            for compound in compounds:
                base_conc = station["profile"].get(compound, 0.0)

                # Add noise
                noise_factor = 1 + random.gauss(0, station["noise"])
                noise_factor = max(0, noise_factor)  # Don't go negative
                concentration = round(base_conc * noise_factor, 4)

                # Below detection limit -> show as 0
                if concentration < 0.005:
                    concentration = 0.0

                rows.append({
                    "שם תחנה": station["name"],
                    "X (ITM)": station["x"],
                    "Y (ITM)": station["y"],
                    "תאריך דיגום": actual_date.strftime("%d/%m/%Y"),
                    "סוג מקור": station["source_type"],
                    "סמל תרכובת": compound,
                    "ריכוז (µg/L)": concentration,
                })

    df = pd.DataFrame(rows)
    return df


def save_sample_data():
    """יוצר ושומר את הקובץ הסינתטי."""
    import os

    df = generate_sample_data()

    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sample")
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, "sample_pfas.xlsx")
    df.to_excel(filepath, index=False, engine="openpyxl")

    print(f"✓ נוצר קובץ סינתטי: {filepath}")
    print(f"  {len(df)} שורות, {df['שם תחנה'].nunique()} תחנות, {df['סמל תרכובת'].nunique()} תרכובות")

    return filepath


if __name__ == "__main__":
    save_sample_data()
