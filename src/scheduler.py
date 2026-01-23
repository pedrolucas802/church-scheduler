from datetime import date, datetime, time
import calendar
import random

ROLES = ["OBS", "FIXED", "MOBILE"]

def month_services(year: int, month: int):
    services = []
    _, last_day = calendar.monthrange(year, month)
    for day in range(1, last_day + 1):
        d = date(year, month, day)
        wd = d.weekday()  # Mon=0 ... Sun=6
        if wd == 3:  # Thu
            services.append(datetime.combine(d, time(19, 30)))
        if wd == 6:  # Sun
            for hh, mm in [(10, 0), (15, 0), (17, 0), (19, 30)]:
                services.append(datetime.combine(d, time(hh, mm)))
    services.sort()
    return services

def pick_candidate(candidates, total_assigned, role_counts, role, used):
    # fairness: fewest total, then fewest in role, then random tie-break
    pool = [c for c in candidates if c["id"] not in used]
    if not pool:
        return None
    random.shuffle(pool)
    pool.sort(key=lambda c: (total_assigned[c["id"]], role_counts[c["id"]][role]))
    return pool[0]

def generate_assignments(volunteers, services, seed=42, prefer_mobile=True):
    """
    volunteers: list of dicts with fields:
      id, name, thu_ok, sun_ok, can_obs, can_fixed, can_mobile, active
    returns: dict[dt_iso] -> {role: volunteer_id or None}
    """
    random.seed(seed)
    total_assigned = {v["id"]: 0 for v in volunteers}
    role_counts = {v["id"]: {r: 0 for r in ROLES} for v in volunteers}

    out = {}
    for dt in services:
        is_thu = dt.weekday() == 3
        is_sun = dt.weekday() == 6

        def available(v):
            if not v["active"]:
                return False
            if is_thu and not v["thu_ok"]:
                return False
            if is_sun and not v["sun_ok"]:
                return False
            return True

        used = set()
        dt_iso = dt.isoformat()

        # Candidate lists per role
        cand_obs = [v for v in volunteers if available(v) and v["can_obs"]]
        cand_fix = [v for v in volunteers if available(v) and v["can_fixed"]]
        cand_mob = [v for v in volunteers if available(v) and v["can_mobile"]]

        obs = pick_candidate(cand_obs, total_assigned, role_counts, "OBS", used)
        if obs:
            used.add(obs["id"])
            total_assigned[obs["id"]] += 1
            role_counts[obs["id"]]["OBS"] += 1

        fixed = pick_candidate(cand_fix, total_assigned, role_counts, "FIXED", used)
        if fixed:
            used.add(fixed["id"])
            total_assigned[fixed["id"]] += 1
            role_counts[fixed["id"]]["FIXED"] += 1

        mobile = None
        if prefer_mobile:
            mobile = pick_candidate(cand_mob, total_assigned, role_counts, "MOBILE", used)
            if mobile:
                used.add(mobile["id"])
                total_assigned[mobile["id"]] += 1
                role_counts[mobile["id"]]["MOBILE"] += 1

        out[dt_iso] = {
            "OBS": obs["id"] if obs else None,
            "FIXED": fixed["id"] if fixed else None,
            "MOBILE": mobile["id"] if mobile else None,
        }

    return out