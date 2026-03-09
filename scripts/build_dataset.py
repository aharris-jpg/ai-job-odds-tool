import csv
import json
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


def calculate_probability(observed_exposure: float) -> float:
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
        "11": "Management",
        "13": "Business & Finance",
        "15": "Computer & Math",
        "17": "Engineering",
        "19": "Science",
        "21": "Community & Social Service",
        "23": "Legal",
        "25": "Education",
        "27": "Arts & Media",
        "29": "Healthcare Practitioners",
        "31": "Healthcare Support",
        "33": "Protective Service",
        "35": "Food Service",
        "37": "Cleaning & Grounds",
        "39": "Personal Service",
        "41": "Sales",
        "43": "Office & Admin",
        "45": "Farming & Forestry",
        "47": "Construction",
        "49": "Repair & Maintenance",
        "51": "Production",
        "53": "Transportation",
    }

    return family_map.get(prefix, "Other")


def build_explanation(title: str, probability: float, family: str) -> str:
    if family in ["Computer & Math", "Office & Admin", "Business & Finance", "Arts & Media", "Sales"]:
        if probability >= 0.45:
            return f"{title} ranks among the most AI-exposed jobs because much of the role involves digital, analytical, or information-based work that AI can already assist with."
        if probability >= 0.20:
            return f"{title} has moderate AI exposure because some parts of the role overlap with work AI can already help perform, while other responsibilities still depend on human judgment."
        return f"{title} has relatively low AI exposure compared with other digital and office-based roles, though some tasks may still be supported by AI tools."

    if family in ["Construction", "Repair & Maintenance", "Food Service", "Cleaning & Grounds", "Transportation", "Farming & Forestry"]:
        return f"{title} ranks among the less AI-exposed occupations because much of the work depends on physical activity, manual skill, or on-site problem-solving that current AI systems cannot perform directly."

    if family in ["Healthcare Practitioners", "Healthcare Support", "Community & Social Service", "Protective Service"]:
        return f"{title} tends to be less exposed to AI because the role involves in-person care, physical procedures, or real-world decision-making that still relies heavily on human presence."

    if family in ["Education", "Legal", "Science", "Engineering"]:
        if probability >= 0.30:
            return f"{title} shows moderate to elevated AI exposure because parts of the job involve research, writing, analysis, or structured information work that AI can increasingly support."
        return f"{title} has relatively limited AI exposure because many core parts of the role still depend on expert judgment, specialized knowledge, or real-world interaction."

    return f"{title} has a mixed level of AI exposure compared with other jobs in the dataset."


def build_comparison_text(percentile: int) -> str:
    if percentile >= 99:
        return "This job is more AI-exposed than almost every occupation in the dataset."
    if percentile >= 90:
        return f"This job is more AI-exposed than {percentile}% of jobs in the dataset."
    if percentile >= 60:
        return f"This job ranks above average for AI exposure and is more exposed than {percentile}% of occupations."
    if percentile >= 40:
        return "This job sits near the middle of the dataset and has a typical level of AI exposure."
    if percentile >= 10:
        return "This job is less AI-exposed than most occupations and sits below the middle of the dataset."
    return "This job ranks among the least AI-exposed occupations in the dataset."


def main():
    if not os.path.exists(INPUT_CSV):
        raise FileNotFoundError(f"Could not find input file: {INPUT_CSV}")

    jobs = []

    with open(INPUT_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            occ_code = row["occ_code"].strip()
            title = row["title"].strip()
            observed_exposure = float(row["observed_exposure"])

            jobs.append({
                "occ_code": occ_code,
                "title": title,
                "slug": slugify(title),
                "observed_exposure": round(observed_exposure, 4),
            })

    jobs.sort(key=lambda x: x["observed_exposure"], reverse=True)

    total_jobs = len(jobs)

    for index, job in enumerate(jobs):
        probability = calculate_probability(job["observed_exposure"])
        percentile = round(((total_jobs - index - 1) / max(total_jobs - 1, 1)) * 100)
        family = get_job_family(job["occ_code"])

        job["odds_ai_replaces_major_parts_of_job"] = probability
        job["ai_risk_rank"] = index + 1
        job["more_ai_exposed_than_pct_of_jobs"] = percentile
        job["risk_level"] = get_risk_level(probability)
        job["job_family"] = family
        job["explanation"] = build_explanation(job["title"], probability, family)
        job["comparison_text"] = build_comparison_text(percentile)

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)

    print(f"Built {len(jobs)} jobs")
    print(f"Saved output to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
