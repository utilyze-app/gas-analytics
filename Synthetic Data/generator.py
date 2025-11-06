
import csv, random, math
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Tuple

# ------------------------------
# Config and scaling parameters
# ------------------------------

RNG_SEED = 1337

# Cooking scaling by occupancy (events/day and factor applied to base event sizes)
COOKING_RULES = {
    1: {"events": (1, 2), "factor": 0.6},
    2: {"events": (2, 2), "factor": 0.8},
    3: {"events": (2, 3), "factor": 1.0},
    4: {"events": (2, 3), "factor": 1.2},
    5: {"events": (3, 3), "factor": 1.3},
}

# Hot water rules
SHOWER_THERMS = 0.10  # per shower
DISHWASHER_THERMS = 0.05  # per day if present
LAUNDRY_DAILY_RANGE = (0.08, 0.10)  # if water heater present and occupancy 2-4

# Dryer rules
DRYER_THERMS_PER_LOAD = 0.30

# Kenny baseline cooking events (summer + winter overlays use similar)
# Values here are the typical event sizes before occupancy factor
COOKING_EVENT_SIZES = {
    "breakfast": (0.02, 0.025),
    "lunch": (0.012, 0.018),  # occasional
    "dinner": (0.025, 0.035),
}

# Variation
VARIATION_PCT = (0.10, 0.15)  # +-10-15%


@dataclass
class Scenario:
    scenario_id: str
    season: str  # "summer" or "winter"
    start_date: str  # "YYYY-MM-DD"
    end_date: str    # "YYYY-MM-DD"
    home_sqft: int
    occupancy: int
    appliances: str  # e.g., "furnace+stove", "furnace+water_heater+stove", etc.
    temps_csv: str   # path to a CSV with columns: date,time,temp
    out_csv: str     # output path

def frand(a: float, b: float) -> float:
    return random.uniform(a, b)

def with_variation(val: float) -> float:
    sign = 1 if random.random() < 0.5 else -1
    pct = frand(*VARIATION_PCT)
    return max(0.0, val * (1 + sign * pct))

def parse_datetime(d: str, t: str) -> datetime:
    return datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M:%S")

def daterange(start: datetime, end: datetime):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(hours=1)

def load_temps(temps_csv: str) -> Dict[datetime, float]:
    temps: Dict[datetime, float] = {}
    with open(temps_csv, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            dt = parse_datetime(row["date"], row["time"])
            temps[dt] = float(row["temp"])
    return temps

def base_heating_rate_sqft(home_sqft: int) -> float:
    # base_heating = 0.12 × (sqft/2000) at the 50-60°F band baseline
    return 0.12 * (home_sqft / 2000.0)

def heating_for_temp(temp_f: float, base_heating: float) -> float:
    # HEATING FORMULA (Winter only):
    # Above 70°F: 0
    # 60-70°F: base × 0.3
    # 50-60°F: base × 0.6
    # 40-50°F: base × 0.9
    # Below 40°F: base × 1.2
    if temp_f > 70:
        return 0.0
    if temp_f > 60:
        return base_heating * 0.3
    if temp_f > 50:
        return base_heating * 0.6
    if temp_f > 40:
        return base_heating * 0.9
    return base_heating * 1.2

def choose_event_hours(season: str, occupancy: int) -> Dict[str, List[int]]:
    # Returns hours for breakfast/lunch/dinner events for a day
    # Summer guide suggests peaks at 7am, 11am, 6-8pm, winter similar overlay.
    # We pick specific hours with some randomness.
    breakfast_hour = 7  # 7am
    dinner_hour = 18    # start at 6pm

    # Optional lunch at 11am with some chance
    lunch_hours = []
    if random.random() < 0.4:
        lunch_hours = [11]

    # Breakfast probability differs for 1-person summer special case, but we keep general
    return {
        "breakfast": [breakfast_hour],
        "lunch": lunch_hours,
        "dinner": [dinner_hour + random.choice([0, 1, 2])],  # 6-8pm window
    }

def showers_for_day(occupancy: int) -> List[int]:
    # Each person 1 shower/day at ~7am or ~8pm
    hours = []
    for _ in range(occupancy):
        hours.append(random.choice([7, 20]))
    return hours

def dryer_load_hours_for_week(occupancy: int) -> int:
    # Frequency: (occupancy/2) loads per week, round to nearest int >= 0
    return max(0, round(occupancy / 2))

def distribute_dryer_hours(start_date: datetime, end_date: datetime, occupancy: int) -> Dict[datetime, int]:
    # Returns a mapping of datetimes for which dryer runs happen (one hour per load)
    loads_per_week = dryer_load_hours_for_week(occupancy)
    day = start_date
    dryer_times = {}
    while day <= end_date:
        # For each week block
        week_start = day
        # choose windows: evenings 19-22 or weekend 10-14
        candidate_hours = []
        for i in range(7):
            d = week_start + timedelta(days=i)
            is_weekend = d.weekday() >= 5
            if is_weekend:
                candidate_hours.extend([(d, h) for h in range(10, 14)])
            else:
                candidate_hours.extend([(d, h) for h in range(19, 22)])
        random.shuffle(candidate_hours)
        for j in range(loads_per_week):
            if j < len(candidate_hours):
                d, h = candidate_hours[j]
                dryer_times[datetime(d.year, d.month, d.day, h, 0, 0)] = 1
        day = week_start + timedelta(days=7)
    return dryer_times

def target_daily_avg(season: str, occupancy: int, home_sqft: int) -> float:
    # Returns a reasonable target daily total based on prompt ranges, used for avg_usage column
    if season == "summer":
        # From prompts:
        if occupancy == 1: return 0.20  # 0.15-0.25
        if occupancy == 2: return 0.35  # 0.30-0.40
        if occupancy == 3: return 0.50  # 0.45-0.55
        if occupancy == 4: return 0.60  # 0.55-0.65
        if occupancy == 5: return 0.70  # 0.65-0.75
        return 0.50
    else:
        # Winter by sqft midpoints
        sqft_to_daily = {
            1000: 2.0,
            1200: 2.25,
            1400: 2.5,
            1600: 2.7,
            1800: 3.0,
            2000: 3.0,
            2200: 3.5,
            2400: 3.8,
            2600: 4.1,
            2800: 4.4,
            3000: 4.75,
        }
        # default linear-ish
        return sqft_to_daily.get(home_sqft, 3.0)

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def generate_scenario(sc: Scenario):
    random.seed(RNG_SEED + hash(sc.scenario_id) % 1000000)

    # Load temps
    temps = load_temps(sc.temps_csv)

    start_dt = datetime.strptime(sc.start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(sc.end_date, "%Y-%m-%d")
    # Align to hour
    start_dt = start_dt.replace(hour=0, minute=0, second=0)
    end_dt = end_dt.replace(hour=23, minute=0, second=0)

    # Appliance flags
    has_furnace = "furnace" in sc.appliances
    has_stove = "stove" in sc.appliances
    has_water_heater = "water_heater" in sc.appliances
    has_dryer = "dryer" in sc.appliances

    # Precompute dryer schedule if needed
    dryer_hours_map = {}
    if has_dryer:
        dryer_hours_map = distribute_dryer_hours(start_dt, end_dt, sc.occupancy)

    # Prepare output
    out_rows = []
    base_heat = base_heating_rate_sqft(sc.home_sqft) if has_furnace else 0.0

    # avg_usage column: daily target / 24
    daily_target = target_daily_avg(sc.season, sc.occupancy, sc.home_sqft)
    avg_usage_col = round(daily_target / 24.0, 6)

    # Iterate per hour
    cur = start_dt
    last_written_date = None

    while cur <= end_dt:
        dstr = cur.strftime("%Y-%m-%d")
        tstr = cur.strftime("%H:%M:%S")
        temp = float(temps.get(cur, 72.0))  # fallback if missing

        usage = 0.0

        # Season logic
        if sc.season == "summer":
            # No heating in summer
            if has_stove:
                # Cooking sparse events
                hours = choose_event_hours(sc.season, sc.occupancy)
                # Decide breakfast and dinner presence per day only once
                day_seed = hash((sc.scenario_id, dstr)) % 100000
                rnd = random.Random(day_seed)
                # Breakfast probability (special for 1-person)
                breakfast_prob = 0.30 if sc.occupancy == 1 else 0.6
                dinner_prob = 0.80 if sc.occupancy == 1 else 0.9
                lunch_prob = 0.25

                if cur.hour in hours["breakfast"] and rnd.random() < breakfast_prob:
                    ev = rnd.uniform(*COOKING_EVENT_SIZES["breakfast"])
                    ev *= COOKING_RULES.get(sc.occupancy, {"factor":1.0})["factor"]
                    usage += ev

                if cur.hour in hours["dinner"] and rnd.random() < dinner_prob:
                    ev = rnd.uniform(*COOKING_EVENT_SIZES["dinner"])
                    ev *= COOKING_RULES.get(sc.occupancy, {"factor":1.0})["factor"]
                    usage += ev

                if hours["lunch"] and cur.hour in hours["lunch"] and rnd.random() < lunch_prob:
                    ev = rnd.uniform(*COOKING_EVENT_SIZES["lunch"])
                    ev *= COOKING_RULES.get(sc.occupancy, {"factor":1.0})["factor"]
                    usage += ev

            if has_water_heater:
                # Showers: occupancy × 0.10 therms per day at 7 or 20
                s_hours = showers_for_day(sc.occupancy)
                if cur.hour in s_hours:
                    usage += SHOWER_THERMS

            if has_dryer:
                if cur in dryer_hours_map:
                    usage += DRYER_THERMS_PER_LOAD

            # Zero usage 90-95% of hours naturally emerges since events are sparse

        else:  # winter
            if has_furnace:
                heat = heating_for_temp(temp, base_heat)
                usage += heat

            # Overlay activities
            if has_stove:
                hours = choose_event_hours(sc.season, sc.occupancy)
                day_seed = hash((sc.scenario_id, dstr)) % 100000
                rnd = random.Random(day_seed + 42)
                # Higher presence in winter
                if cur.hour in hours["breakfast"] and rnd.random() < 0.75:
                    ev = rnd.uniform(*COOKING_EVENT_SIZES["breakfast"])
                    ev *= COOKING_RULES.get(sc.occupancy, {"factor":1.0})["factor"]
                    usage += ev
                if hours["lunch"] and cur.hour in hours["lunch"] and rnd.random() < 0.4:
                    ev = rnd.uniform(*COOKING_EVENT_SIZES["lunch"])
                    ev *= COOKING_RULES.get(sc.occupancy, {"factor":1.0})["factor"]
                    usage += ev
                if cur.hour in hours["dinner"] and rnd.random() < 0.9:
                    ev = rnd.uniform(*COOKING_EVENT_SIZES["dinner"])
                    ev *= COOKING_RULES.get(sc.occupancy, {"factor":1.0})["factor"]
                    usage += ev

            if has_water_heater:
                s_hours = showers_for_day(sc.occupancy)
                if cur.hour in s_hours:
                    usage += SHOWER_THERMS

            if has_dryer and cur in dryer_hours_map:
                usage += DRYER_THERMS_PER_LOAD

        # Variation to avoid robotic patterns
        if usage > 0:
            usage = with_variation(usage)

        # Guardrails
        usage = max(0.0, round(usage, 3))

        out_rows.append({
            "date": dstr,
            "time": tstr,
            "temp": int(round(temp)),
            "usage_therms": f"{usage:.3f}",
            "avg_usage": f"{avg_usage_col:.6f}",
            "season": sc.season,
            "home_sqft": sc.home_sqft,
            "occupancy": sc.occupancy,
            "appliances": sc.appliances,
        })
        cur += timedelta(hours=1)

    # Write CSV
    with open(sc.out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date","time","temp","usage_therms","avg_usage","season","home_sqft","occupancy","appliances"])
        w.writeheader()
        w.writerows(out_rows)


def run_from_config(config_csv: str):
    # Read scenarios and run one by one
    with open(config_csv, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            sc = Scenario(
                scenario_id=row["scenario_id"],
                season=row["season"].lower(),
                start_date=row["start_date"],
                end_date=row["end_date"],
                home_sqft=int(row["home_sqft"]),
                occupancy=int(row["occupancy"]),
                appliances=row["appliances"].lower(),
                temps_csv=row["temps_csv"],
                out_csv=row["out_csv"],
            )
            generate_scenario(sc)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="Path to scenarios.csv")
    args = ap.parse_args()
    run_from_config(args.config)
