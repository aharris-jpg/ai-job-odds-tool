import csv
import json
import math
import os
import re


INPUT_CSV = "data/anthropic_jobs.csv"
OUTPUT_JSON = "data/enriched_jobs.json"


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text)
    return text


def clamp(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    return max(min_value, min(value, max_value))


def calculate_ai_replacement_probability(observed_exposure: float) -> float:
    # Simple first-pass model:
    # probability = exposure × adoption factor
    adoption_factor = 0.6
    return round(clamp(observed_exposure * adoption_factor), 4)


def get_risk_level(probability: float) -> str:
    if probability >= 0.60:
        return "Very High"
    if probability >= 0.45:
        return "High"
    if probability >= 0.30:
        return "Moderate"
    if probability >= 0.15:
        return "Low"
    return "Minimal"


def get_job_family(occ_code: str) -> str:
    prefix = occ_code.split("-")[0]

    family_map = {
        "11": "management",
        "13": "business_finance",
        "15": "computer_math",
        "17": "engineering",
        "19": "science",
        "21": "community_social",
        "23": "legal",
        "25": "education",
        "27": "arts_media",
        "29": "healthcare_practitioners",
        "31": "healthcare_support",
        "33": "protective_service",
        "35": "food_service",
        "37": "cleaning_grounds",
        "39": "personal_service",
        "41": "sales",
        "43": "office_admin",
        "45": "farming_forestry",
        "47": "construction",
        "49": "repair_maintenance",
        "51": "production",
        "53": "transportation",
    }

    return family_map.get(prefix, "other")


def build_explanation(title: str, probability: float, family: str, percentile: int) -> str:
    if family in ["computer_math", "office_admin", "business_finance", "arts_media"]:
        if probability >= 0.45:
            return (
                f"{title} ranks among the most AI-exposed jobs in the dataset because much of the role "
                f"involves digital, text-based, analytical, or information-processing work that AI can already assist with."
            )
        if probability >= 0.20:
            return (
                f"{title} has moderate AI exposure because some parts of the job overlap with work AI can already help perform, "
                f"but many responsibilities still depend on human judgment and expertise."
            )
        return (
            f"{title} has relatively low AI exposure compared with other digital and office-based roles, "
            f"though some tasks may still be supported by AI tools."
        )

    if family in ["construction", "repair_maintenance", "food_service", "cleaning_grounds", "transportation", "farming_forestry"]:
        return (
            f"{title} ranks among the less AI-exposed occupations because much of the work depends on physical activity, "
            f"manual skill, or on-site problem-solving that current AI systems cannot perform directly."
        )

    if family in ["healthcare_practitioners", "healthcare_support", "community_social", "protective_service"]:
        return (
            f"{title} tends to be less exposed to AI because the role involves in-person care, physical procedures, "
            f"or real-world decision-making that still relies heavily on human presence."
        )

    if family in ["education", "legal", "science", "engineering"]:
        if probability >= 0.30:
            return (
                f"{title} shows moderate to elevated AI exposure because parts of the job involve research, writing, analysis, "
                f"or structured information work that AI can increasingly support."
            )
        return (
            f"{title} has relatively limited AI exposure because many core parts of the role still depend on expert judgment, "
            f"specialized knowledge, or real-world interaction."
        )

    if percentile >= 90:
        return f"{title} ranks among the most AI-exposed occupations in the dataset."
    if percentile <= 10:
        return f"{title} ranks among the least AI-exposed occupations in the dataset."
    return f"{title} has a middle-range level of AI exposure compared with other jobs in the dataset."


def build_comparison_text(percentile: int) -> str:
    if percentile >= 99:
        return "This job is more AI-exposed than almost every occupation in the dataset."
    if percentile >= 90:
        return f"This job is more AI-exposed than {percentile}% of jobs in the dataset."
    if percentile >= 60:
        return f"This job ranks above average for AI exposure and is more exposed than {percentile}% of occupations."
    if percentile >= 40:
        return f"This job sits near the middle of the dataset and has a typical level of AI exposure."
    if percentile >= 10:
        return f"This job is less AI-exposed than most occupations and sits below the middle of the dataset."
    return "This job ranks among the least AI-exposed occupations in the dataset."


def main():
    if not os.path.exists(INPUT_CSV):
        raise FileNotFoundError(f"Could not find input file: {INPUT_CSV}")

    jobs = []

    with open(INPUT_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row["title"].strip()
            occ_code = row["occ_code"].strip()
            observed_exposure = float(row["observed_exposure"])

            jobs.append({
                "occ_code": occ_code,
                "title": title,
                "slug": slugify(title),
                "observed_exposure": round(observed_exposure, 4),
            })

    # Rank by observed exposure descending
    jobs.sort(key=lambda x: x["observed_exposure"], reverse=True)

    total_jobs = len(jobs)

    for index, job in enumerate(jobs, start=1):
        probability = calculate_ai_replacement_probability(job["observed_exposure"])
        percentile = round(((total_jobs - index) / max(total_jobs - 1, 1)) * 100)

        family = get_job_family(job["occ_code"])

        job["odds_ai_replaces_major_parts_of_job"] = probability
        job["risk_level"] = get_risk_level(probability)
        job["ai_risk_rank"] = index
        job["more_ai_exposed_than_pct_of_jobs"] = percentile
        job["job_family"] = family
        job["explanation"] = build_explanation(job["title"], probability, family, percentile)
        job["comparison_text"] = build_comparison_text(percentile)

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)

    print(f"Built {len(jobs)} job records")
    print(f"Saved to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
