import csv
import json
import os
import re
from typing import Any, Dict, Optional


INPUT_CSV = "data/anthropic_jobs.csv"
STATE_WAGE_CSV = "data/state_wage_employment.csv"
STATE_PROJECTIONS_CSV = "data/state_projections.csv"
OUTPUT_JSON = "data/enriched_jobs.json"


STATE_FIPS_TO_ABBR = {
    "1": "AL", "2": "AK", "4": "AZ", "5": "AR", "6": "CA", "8": "CO", "9": "CT",
    "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL",
    "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD",
    "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE",
    "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV",
    "55": "WI", "56": "WY", "72": "PR",
}

STATE_NAME_TO_ABBR = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "district of columbia": "DC",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "puerto rico": "PR",
}


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text)
    return text


def clamp(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    return max(min_value, min(value, max_value))


def parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text == "#":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Any) -> Optional[int]:
    number = parse_float(value)
    if number is None:
        return None
    return int(round(number))


def normalize_occ_code(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""

    text = text.replace(".00", "")
    text = re.sub(r"\.0+$", "", text)

    match = re.search(r"(\d{2}-\d{4})", text)
    if match:
        return match.group(1)

    return text


def normalize_state(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip()
    if not text:
        return ""

    upper = text.upper()
    if upper in STATE_NAME_TO_ABBR.values():
        return upper

    numeric = parse_int(text)
    if numeric is not None:
        return STATE_FIPS_TO_ABBR.get(str(numeric), "")

    lower = text.lower()
    if lower in STATE_NAME_TO_ABBR:
        return STATE_NAME_TO_ABBR[lower]

    return ""


def normalize_row_keys(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = {}
    for key, value in row.items():
      normalized[str(key).strip().lower()] = value
    return normalized


def get_first(row: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


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
            return f"{title} shows moderate to elevated AI exposure because parts of the role involve research, writing, analysis, or structured information work that AI can increasingly support."
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


def load_state_wage_data(filepath: str) -> Dict[str, Dict[str, Dict[str, Any]]]:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Could not find state wage file: {filepath}")

    results: Dict[str, Dict[str, Dict[str, Any]]] = {}

    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for raw_row in reader:
            row = normalize_row_keys(raw_row)

            state = normalize_state(get_first(row, "prim_state", "state", "state_abbr", "statecode", "state_code"))
            occ_code = normalize_occ_code(get_first(row, "occ_code", "occcode", "soc_code", "soccode"))

            if not state:
                state = normalize_state(get_first(row, "area_title", "area", "state_name"))

            if not state or not occ_code:
                continue

            entry = {
                "title": (get_first(row, "occ_title", "title", "occupation_title") or "").strip() or None,
                "employment": parse_int(get_first(row, "tot_emp", "employment")),
                "mean_wage": parse_int(get_first(row, "a_mean", "mean_wage")),
                "median_wage": parse_int(get_first(row, "a_median", "median_wage")),
                "annual_p10": parse_int(get_first(row, "a_pct10")),
                "annual_p25": parse_int(get_first(row, "a_pct25")),
                "annual_p75": parse_int(get_first(row, "a_pct75")),
                "annual_p90": parse_int(get_first(row, "a_pct90")),
                "jobs_per_1000": parse_float(get_first(row, "jobs_1000")),
                "location_quotient": parse_float(get_first(row, "loc_quotient", "location_quotient")),
            }

            results.setdefault(occ_code, {})[state] = entry

    return results


def load_state_projection_data(filepath: str) -> Dict[str, Dict[str, Dict[str, Any]]]:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Could not find state projections file: {filepath}")

    results: Dict[str, Dict[str, Dict[str, Any]]] = {}

    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for raw_row in reader:
            row = normalize_row_keys(raw_row)

            stfips_raw = get_first(row, "stfips", "statefips", "state_fips")
            occ_code = normalize_occ_code(get_first(row, "occcode", "occ_code", "soc_code"))
            state = normalize_state(stfips_raw)

            if not state:
                state = normalize_state(get_first(row, "area", "state", "state_name"))

            if not state or not occ_code:
                continue

            entry = {
                "title": (get_first(row, "title", "occ_title", "occupation_title") or "").strip() or None,
                "projected_base_employment": parse_int(get_first(row, "base")),
                "projected_employment": parse_int(get_first(row, "projected")),
                "percent_change": parse_float(get_first(row, "percentchange", "percent_change")),
                "avg_annual_openings": parse_int(get_first(row, "avgannualopenings", "avg_annual_openings")),
            }

            results.setdefault(occ_code, {})[state] = entry

    return results


def merge_state_data(
    wage_data: Dict[str, Dict[str, Dict[str, Any]]],
    projection_data: Dict[str, Dict[str, Dict[str, Any]]]
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    merged: Dict[str, Dict[str, Dict[str, Any]]] = {}

    all_occ_codes = set(wage_data.keys()) | set(projection_data.keys())

    for occ_code in all_occ_codes:
        merged[occ_code] = {}
        states = set(wage_data.get(occ_code, {}).keys()) | set(projection_data.get(occ_code, {}).keys())

        for state in states:
            merged[occ_code][state] = {}
            merged[occ_code][state].update(wage_data.get(occ_code, {}).get(state, {}))
            merged[occ_code][state].update(projection_data.get(occ_code, {}).get(state, {}))

    return merged


def build_state_summary(state_data: Dict[str, Any]) -> Dict[str, Any]:
    valid_mean_wages = [
        value["mean_wage"]
        for value in state_data.values()
        if isinstance(value.get("mean_wage"), int)
    ]
    valid_growth = [
        value["percent_change"]
        for value in state_data.values()
        if isinstance(value.get("percent_change"), float)
    ]
    valid_openings = [
        value["avg_annual_openings"]
        for value in state_data.values()
        if isinstance(value.get("avg_annual_openings"), int)
    ]

    summary: Dict[str, Any] = {
        "states_available": len(state_data),
    }

    if valid_mean_wages:
        summary["mean_state_wage_avg"] = round(sum(valid_mean_wages) / len(valid_mean_wages))
        summary["highest_mean_wage"] = max(valid_mean_wages)
        summary["lowest_mean_wage"] = min(valid_mean_wages)

    if valid_growth:
        summary["avg_percent_change"] = round(sum(valid_growth) / len(valid_growth), 2)
        summary["highest_percent_change"] = round(max(valid_growth), 2)
        summary["lowest_percent_change"] = round(min(valid_growth), 2)

    if valid_openings:
        summary["avg_annual_openings_avg"] = round(sum(valid_openings) / len(valid_openings))
        summary["highest_avg_annual_openings"] = max(valid_openings)
        summary["lowest_avg_annual_openings"] = min(valid_openings)

    return summary


def main():
    if not os.path.exists(INPUT_CSV):
        raise FileNotFoundError(f"Could not find input file: {INPUT_CSV}")

    wage_data = load_state_wage_data(STATE_WAGE_CSV)
    projection_data = load_state_projection_data(STATE_PROJECTIONS_CSV)
    merged_state_data = merge_state_data(wage_data, projection_data)

    print("Sample wage occ codes:", list(wage_data.keys())[:8])
    print("Sample projection occ codes:", list(projection_data.keys())[:8])
    print("States for 15-1251 in wage data:", list(wage_data.get("15-1251", {}).keys())[:10])
    print("States for 15-1251 in projection data:", list(projection_data.get("15-1251", {}).keys())[:10])
    print("States for 15-1251 after merge:", list(merged_state_data.get("15-1251", {}).keys())[:10])

    jobs = []

    with open(INPUT_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            occ_code = normalize_occ_code(row.get("occ_code"))
            title = (row.get("title") or "").strip()
            observed_exposure = float(row["observed_exposure"])

            jobs.append({
                "occ_code": occ_code,
                "title": title,
                "slug": slugify(title),
                "observed_exposure": round(observed_exposure, 4),
            })

    jobs.sort(key=lambda x: x["observed_exposure"], reverse=True)

    total_jobs = len(jobs)

    matched_jobs = 0

    for index, job in enumerate(jobs):
        probability = calculate_probability(job["observed_exposure"])
        percentile = round(((total_jobs - index - 1) / max(total_jobs - 1, 1)) * 100)
        family = get_job_family(job["occ_code"])
        state_data = merged_state_data.get(job["occ_code"], {})

        if state_data:
            matched_jobs += 1

        job["odds_ai_replaces_major_parts_of_job"] = probability
        job["ai_risk_rank"] = index + 1
        job["more_ai_exposed_than_pct_of_jobs"] = percentile
        job["risk_level"] = get_risk_level(probability)
        job["job_family"] = family
        job["explanation"] = build_explanation(job["title"], probability, family)
        job["comparison_text"] = build_comparison_text(percentile)
        job["state_data"] = state_data
        job["state_summary"] = build_state_summary(state_data)

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)

    print(f"Built {len(jobs)} jobs")
    print(f"Loaded wage states for {len(wage_data)} occupation codes")
    print(f"Loaded projection states for {len(projection_data)} occupation codes")
    print(f"Matched state data for {matched_jobs} jobs")
    print(f"Saved output to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
