# -*- coding: utf-8 -*-
import time, random
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional
import pandas as pd
import streamlit as st

APP_NAME = "Walking Buddies"
st.set_page_config(page_title=APP_NAME, page_icon="👟", layout="wide")

def _ensure_state():
    ss = st.session_state
    ss.setdefault("users", {})
    ss.setdefault("teams", {})
    ss.setdefault("invites", [])
    ss.setdefault("routes", [])
    ss.setdefault("messages", [])
    ss.setdefault("photos", [])
    ss.setdefault("reminders", {
        "walk_enabled": True, "walk_every_min": 120,
        "stand_enabled": True, "stand_every_min": 30,
        "next_walk_at": None, "next_stand_at": None, "snooze_minutes": 10,
    })
    ss.setdefault("challenge_catalog", [
        {"id":"daily_5000","name":"Daily Step Goal","desc":"Hit 5,000 steps today","type":"daily_steps","target":5000,"period":"daily","reward_points":50},
        {"id":"weekend_walkathon","name":"Weekend Walkathon","desc":"Walk 10 miles Sat–Sun","type":"distance_period","target_miles":10.0,"period":"weekend","reward_points":150},
        {"id":"photo_share","name":"Photo Challenge","desc":"Share a scenic walk photo this week","type":"boolean_weekly","target":1,"period":"weekly","reward_points":20},
        {"id":"invite_3","name":"Invite Challenge","desc":"Invite 3 friends this month","type":"count_monthly","target":3,"period":"monthly","reward_points":100},
        {"id":"team_100_miles","name":"Team Mileage Goal","desc":"Teams aim for 100 miles combined this week","type":"team_distance_weekly","target_miles":100.0,"period":"weekly","reward_points":300},
        {"id":"relay_pass_baton","name":"Relay Challenge","desc":"Each member walks 2 miles this week","type":"team_each_member_distance_weekly","target_miles":2.0,"period":"weekly","reward_points":200},
        {"id":"city_explorer","name":"City Explorer","desc":"Walk 5 distinct neighborhoods this month","type":"distinct_routes_monthly","target_count":5,"period":"monthly","reward_points":120},
    ])
    ss.setdefault("custom_challenges", [])
    ss.setdefault("user_challenges", {})
    ss.setdefault("team_battles", [])
    ss.setdefault("reward_catalog", [
        {"id":"badge_10_walks","type":"badge","name":"First 10 Walks","cost":0,"desc":"Milestone badge after 10 walks"},
        {"id":"badge_100_miles","type":"badge","name":"100 Miles Club","cost":0,"desc":"Milestone badge after 100 miles"},
        {"id":"coupon_sneakers","type":"coupon","name":"Sneaker Discount $10","cost":300,"desc":"$10 off partner sneakers"},
        {"id":"coupon_cafe","type":"coupon","name":"Local Cafe $5","cost":150,"desc":"$5 voucher at partner cafe"},
        {"id":"giftcard","type":"gift","name":"Gift Card $20","cost":800,"desc":"Generic gift card"},
        {"id":"premium_challenge","type":"unlock","name":"Exclusive Challenge Pack","cost":400,"desc":"Unlock premium challenge set"},
    ])
    ss.setdefault("badges", {})
    ss.setdefault("collectibles", {})
    ss.setdefault("privacy_defaults", {
        "profileVisibility": "private",
        "showCity": True,
        "showCompany": False,
        "leaderboards": {"public": False, "alias": "", "teamVisible": True},
        "discoverability": {"byCity": True, "byCompany": False},
        "routes": {"defaultShare": "private"},
        "photos": {"defaultAudience": "friends", "stripEXIF": True, "autoExpireDays": 365},
        "messaging": {"allowRequests": "friends_of_friends", "readReceipts": False, "blocked": []},
        "notifications": {"genericContent": True, "quietHours": "22:00-07:00"},
        "health": {"appleHealth": {"steps": True, "distance": False}, "googleFit": {"steps": True}},
        "analytics": {"crash": True, "performance": True, "researchProgram": False},
        "security": {"appLock": False, "twoFA": False},
    })
    ss.setdefault("timer_running", False)
    ss.setdefault("timer_started_at", None)
    ss.setdefault("timer_accum_sec", 0)
    ss.setdefault("timer_prompt_open", False)
    ss.setdefault("timer_save_minutes", 0)
    ss.setdefault("timer_save_steps", 0)
    ss.setdefault("timer_save_miles", 0.0)
_ensure_state()

POINT_RULES = {"base_per_minute":1,"streak_7":10,"streak_30":50,"group_walk_bonus":20,"invite_bonus":50,"photo_share":5}
TIERS=[("Platinum",5000),("Gold",1000),("Silver",500),("Bronze",0)]

def ensure_user(uid: str, name: Optional[str]=None)->Dict[str,Any]:
    user = st.session_state.users.setdefault(uid, {
        "name": name or uid, "points":0, "team":None, "company":"", "city":"", "available_times":"Mornings",
        "buddies": set(), "walk_dates":[], "steps_log":{}, "minutes_log":{}, "distance_miles_log":{},
        "photos_this_week":0, "invites_this_month":0, "routes_completed_month": set(), "mood_log":{}, "avatar_level":1,
        "privacy": st.session_state.privacy_defaults.copy()
    })
    if "privacy" not in user: user["privacy"] = st.session_state.privacy_defaults.copy()
    return user

def calc_streak(dates: List[datetime])->int:
    if not dates: return 0
    ds = sorted({d.date() for d in dates}, reverse=True)
    streak = 0; today = date.today()
    for d in ds:
        if d == today - timedelta(days=streak): streak += 1
        elif d < today - timedelta(days=streak): break
    return streak

def tier_for_points(p:int)->str:
    for name, th in TIERS:
        if p>=th: return name
    return "Bronze"

def total_walks(u): return len(u.get("walk_dates",[]))
def total_miles(u): return sum(float(v) for v in u.get("distance_miles_log",{}).values())

def add_points(uid, pts, reason=""):
    u=ensure_user(uid,uid); u["points"]=int(u.get("points",0))+int(pts)
    if reason: st.toast(f"+{pts} pts: {reason}")

def evolve_avatar(user_id: str):
    u = ensure_user(user_id, user_id)
    miles = total_miles(u); streak = calc_streak(u["walk_dates"])
    level = 1
    if miles >= 50 or streak >= 14: level = 2
    if miles >= 150 or streak >= 30: level = 3
    if miles >= 300 or streak >= 60: level = 4
    u["avatar_level"] = level

def check_and_award_badges(user_id: str):
    u = ensure_user(user_id, user_id)
    b = st.session_state.badges.setdefault(user_id, set())
    if total_walks(u) >= 10: b.add("badge_10_walks")
    if total_miles(u) >= 100.0: b.add("badge_100_miles")
    evolve_avatar(user_id)

def award_walk(uid, minutes, steps, miles, is_group, shared_photo, mood=None):
    u=ensure_user(uid,uid); today=date.today().isoformat()
    u["walk_dates"].append(datetime.now())
    u["minutes_log"][today]=int(u["minutes_log"].get(today,0))+int(minutes)
    u["steps_log"][today]=int(u["steps_log"].get(today,0))+int(steps)
    u["distance_miles_log"][today]=float(u["distance_miles_log"].get(today,0.0))+float(miles)
    gained=int(minutes)*POINT_RULES["base_per_minute"]
    if is_group: gained+=POINT_RULES["group_walk_bonus"]
    if shared_photo: gained+=POINT_RULES["photo_share"]; u["photos_this_week"]=int(u.get("photos_this_week",0))+1
    s=calc_streak(u["walk_dates"])
    if s>=30: gained+=POINT_RULES["streak_30"]
    elif s>=7: gained+=POINT_RULES["streak_7"]
    u["points"]=int(u.get("points",0))+gained
    if mood: u["mood_log"][today]=mood
    if random.random()<0.25:
        col=st.session_state.collectibles.setdefault(uid,{"coins":0,"items":set()})
        coin=random.randint(1,10); col["coins"]+=coin; st.toast(f"🪙 Found {coin} coins!")
    check_and_award_badges(uid)
    return gained, u["points"], s

def invite_friend(uid, email):
    st.session_state.invites.append({"inviter":uid,"friend":email,"ts":time.time()})
    u=ensure_user(uid,uid); u["points"]=int(u.get("points",0))+POINT_RULES["invite_bonus"]
    u["invites_this_month"]=int(u.get("invites_this_month",0))+1
    return u["points"]

def is_friend(a,b)->bool:
    ua = ensure_user(a, a); return b in ua.get("buddies", set())

def same_team(a,b)->bool:
    ua, ub = ensure_user(a, a), ensure_user(b, b)
    return ua.get("team") and ua.get("team")==ub.get("team")

def can_view(owner_id: str, viewer_id: str, audience: str)->bool:
    if owner_id == viewer_id: return True
    if audience == "public": return True
    if audience == "friends": return is_friend(owner_id, viewer_id)
    if audience == "team": return same_team(owner_id, viewer_id)
    return False

def discoverable_to(viewer_id: str, owner_id: str)->bool:
    if viewer_id == owner_id: return True
    o = ensure_user(owner_id, owner_id)
    d = o["privacy"].get("discoverability", {"byCity": True, "byCompany": False})
    return bool(d.get("byCity", True))

def leaderboard_display_name(u: Dict[str,Any])->str:
    lb = u.get("privacy",{}).get("leaderboards", {})
    alias = (lb.get("alias") or "").strip()
    if alias: return alias
    name = (u.get("name") or "User").strip()
    parts = name.split()
    if len(parts)>=2: return f"{parts[0]} {parts[1][0]}."
    return name

def get_leaderboards(viewer_id: str):
    users=st.session_state.users; rows=[]; team_points={}; city_rows=[]; comp_rows=[]
    for uid,u in users.items():
        lb = u.get("privacy",{}).get("leaderboards", {"public": False, "teamVisible": True})
        include_public = bool(lb.get("public", False))
        same_team_ok = same_team(uid, viewer_id) and bool(lb.get("teamVisible", True))
        if not (include_public or same_team_ok or uid==viewer_id):
            continue
        display = leaderboard_display_name(u)
        rows.append({"user":display,"points":int(u.get("points",0)),"team":u.get("team") or "","city":(u.get("city","") if u.get("privacy",{}).get("showCity",True) else ""), "company":(u.get("company","") if u.get("privacy",{}).get("showCompany",False) else "")})
        if u.get("team"):
            if include_public or same_team_ok or uid==viewer_id:
                team_points[u["team"]] = team_points.get(u["team"],0) + int(u.get("points",0))

    users_df=pd.DataFrame(rows, columns=["user","points","team","city","company"])
    if not users_df.empty: users_df=users_df.sort_values("points",ascending=False).reset_index(drop=True)
    teams_df=pd.DataFrame([{"team":k,"points":v} for k,v in team_points.items()], columns=["team","points"])
    if not teams_df.empty: teams_df=teams_df.sort_values("points",ascending=False).reset_index(drop=True)

    if not users_df.empty:
        y,w,_=date.today().isocalendar(); monday=date.fromisocalendar(y,w,1)
        cities=set([r["city"] for r in rows if r["city"]])
        for c in cities:
            total=0
            for uid,u in users.items():
                show_city = u.get("privacy",{}).get("showCity", True)
                if not show_city: continue
                if u.get("city","")==c:
                    for i in range(7):
                        di=(monday+timedelta(days=i)).isoformat()
                        total+=int(u.get("steps_log",{}).get(di,0))
            city_rows.append({"city":c,"steps_week":total})
    city_df=pd.DataFrame(city_rows)
    if not city_df.empty: city_df=city_df.sort_values("steps_week",ascending=False).reset_index(drop=True)

    comp_rows=[]
    companies=set([r["company"] for r in rows if r["company"]])
    for co in companies:
        pts=0
        for uid,u in users.items():
            if u.get("company","")==co and u.get("privacy",{}).get("showCompany", False):
                pts+=int(u.get("points",0))
        comp_rows.append({"company":co,"points":pts})
    company_df=pd.DataFrame(comp_rows)
    if not company_df.empty: company_df=company_df.sort_values("points",ascending=False).reset_index(drop=True)

    return users_df, teams_df, city_df, company_df

def init_reminders():
    r=st.session_state.reminders; now=datetime.now()
    if r.get("next_walk_at") is None and r.get("walk_enabled",True): r["next_walk_at"]=now+timedelta(minutes=int(r.get("walk_every_min",120)))
    if r.get("next_stand_at") is None and r.get("stand_enabled",True): r["next_stand_at"]=now+timedelta(minutes=int(r.get("stand_every_min",30)))

def check_and_display_reminders():
    r=st.session_state.reminders; now=datetime.now()
    if r.get("walk_enabled") and r.get("next_walk_at") and now>=r["next_walk_at"]:
        st.warning("🚶 Time for a walk reminder!")
        c1,c2,c3=st.columns(3)
        with c1:
            if st.button("Start Walk Now"): r["next_walk_at"]=now+timedelta(minutes=int(r.get("walk_every_min",120))); st.success("Great! Log your walk in the 'Log Walk' tab.")
        with c2:
            if st.button("Snooze 10 min"): r["next_walk_at"]=now+timedelta(minutes=int(r.get("snooze_minutes",10))); st.info("Snoozed.")
        with c3:
            if st.button("Dismiss"): r["next_walk_at"]=now+timedelta(minutes=int(r.get("walk_every_min",120)))
    if r.get("stand_enabled") and r.get("next_stand_at") and now>=r["next_stand_at"]:
        st.info("🧍 Stand/Stretch reminder!")
        c1,c2=st.columns(2)
        with c1:
            if st.button("I Stood/Stretch"): r["next_stand_at"]=now+timedelta(minutes=int(r.get("stand_every_min",30))); st.success("Nice! Keep moving 🎉")
        with c2:
            if st.button("Snooze 5 min"): r["next_stand_at"]=now+timedelta(minutes=5); st.info("Snoozed.")

def _period_key(ch):
    p = ch.get("period"); today = date.today()
    if p == "daily": return today.isoformat()
    if p == "weekly":
        y, w, _ = today.isocalendar(); return f"{y}-W{w:02d}"
    if p == "weekend":
        wd = today.weekday()
        saturday = today + timedelta(days=(5 - wd)) if wd <= 5 else today - timedelta(days=(wd - 5))
        return f"weekend-{saturday.isoformat()}"
    if p == "monthly": return f"{today.year}-{today.month:02d}"
    return "alltime"

def get_challenge_by_id(ch_id: str):
    for c in st.session_state.challenge_catalog:
        if c["id"] == ch_id: return c
    for c in st.session_state.custom_challenges:
        if c["id"] == ch_id: return c
    return None

def _ensure_user_challenge(uid, ch_id):
    uc = st.session_state.user_challenges.setdefault(uid, {})
    if ch_id not in uc:
        uc[ch_id] = {"joined": False, "progress": {}, "completed": False, "last_reset": None}
    ch = get_challenge_by_id(ch_id)
    if ch:
        key=_period_key(ch)
        if uc[ch_id]["last_reset"] != key:
            uc[ch_id]["progress"] = {}
            uc[ch_id]["completed"] = False
            uc[ch_id]["last_reset"] = key
    return uc[ch_id]

def join_challenge(uid, ch_id):
    _ensure_user_challenge(uid, ch_id)["joined"]=True; st.success("Joined challenge!")

def _dates_for_period(period) -> List[str]:
    today = date.today()
    if period == "daily": return [today.isoformat()]
    if period == "weekly":
        y, w, _ = today.isocalendar(); monday = date.fromisocalendar(y, w, 1)
        return [(monday + timedelta(days=i)).isoformat() for i in range(7)]
    if period == "monthly":
        start = date(today.year, today.month, 1)
        import calendar
        days = calendar.monthrange(today.year, today.month)[1]
        return [(start + timedelta(days=i)).isoformat() for i in range(days)]
    if period == "weekend":
        wd = today.weekday(); saturday = today + timedelta(days=(5 - wd)) if wd <= 5 else today - timedelta(days=(wd - 5))
        return [saturday.isoformat(), (saturday + timedelta(days=1)).isoformat()]
    return [today.isoformat()]

def _sum_steps_period(u, period): return sum(int(u["steps_log"].get(d, 0)) for d in _dates_for_period(period))
def _sum_minutes_period(u, period): return sum(int(u["minutes_log"].get(d, 0)) for d in _dates_for_period(period))
def _sum_miles_period(u, period): return sum(float(u["distance_miles_log"].get(d, 0.0)) for d in _dates_for_period(period))
def _count_walks_period(u, period):
    ds = set(_dates_for_period(period)); return sum(1 for dt in u.get("walk_dates", []) if dt.date().isoformat() in ds)

def complete_challenge_if_eligible(uid, ch):
    uc = _ensure_user_challenge(uid, ch["id"])
    if uc["completed"] or not uc["joined"]: return False
    u = ensure_user(uid, uid)
    if ch["id"] == "daily_5000":
        if int(u["steps_log"].get(date.today().isoformat(), 0)) >= int(ch["target"]):
            uc["completed"] = True; add_points(uid, ch["reward_points"], ch["name"]); return True
    elif ch["id"] == "weekend_walkathon":
        wd=date.today().weekday(); saturday = date.today()+timedelta(days=(5-wd)) if wd<=5 else date.today()-timedelta(days=(wd-5)); sunday=saturday+timedelta(days=1)
        total=float(u["distance_miles_log"].get(saturday.isoformat(),0.0))+float(u["distance_miles_log"].get(sunday.isoformat(),0.0))
        if total >= float(ch["target_miles"]):
            uc["completed"] = True; add_points(uid, ch["reward_points"], ch["name"]); return True
    elif ch["id"] == "photo_share":
        if int(u.get("photos_this_week", 0)) >= 1:
            uc["completed"] = True; add_points(uid, ch["reward_points"], ch["name"]); return True
    elif ch["id"] == "invite_3":
        if int(u.get("invites_this_month", 0)) >= int(ch["target"]):
            uc["completed"] = True; add_points(uid, ch["reward_points"], ch["name"]); return True
    elif ch["id"] == "city_explorer":
        if len(u.get("routes_completed_month", set())) >= int(ch["target_count"]):
            uc["completed"] = True; add_points(uid, ch["reward_points"], ch["name"]); return True
    if ch.get("custom", False):
        metric=ch.get("metric","steps"); period=ch.get("period","weekly"); target=float(ch.get("target_value",0))
        val = 0.0
        if metric == "steps": val = _sum_steps_period(u, period)
        elif metric == "minutes": val = _sum_minutes_period(u, period)
        elif metric == "miles": val = _sum_miles_period(u, period)
        elif metric == "walks": val = _count_walks_period(u, period)
        if val >= target: uc["completed"] = True; add_points(uid, int(ch.get("reward_points",0)), ch["name"]); return True
    return False

def update_challenges_after_walk(uid):
    for ch in (st.session_state.challenge_catalog + st.session_state.custom_challenges):
        _ensure_user_challenge(uid, ch["id"]); complete_challenge_if_eligible(uid, ch)

def find_local_buddies(viewer_id: str):
    me = ensure_user(viewer_id, viewer_id); city = me.get("city","").strip().lower()
    if not city: return []
    res = []
    for oid, u in st.session_state.users.items():
        if oid == viewer_id: continue
        # discoverability + showCity must allow
        if not u.get("privacy",{}).get("showCity", True): continue
        disc = u.get("privacy",{}).get("discoverability", {"byCity": True})
        if not disc.get("byCity", True): continue
        if (u.get("city","").strip().lower() == city):
            vis = u.get("privacy",{}).get("profileVisibility","private")
            if vis in ("public","friends","team"):
                res.append({"user_id": oid, "name": u.get("name", oid), "available_times": u.get("available_times","")})
    return res

def send_message(sender_id, recipient_id, text):
    r_user = ensure_user(recipient_id, recipient_id)
    prefs = r_user.get("privacy",{}).get("messaging", {"allowRequests":"friends_of_friends"})
    allowed = False
    if is_friend(recipient_id, sender_id): allowed = True
    elif prefs.get("allowRequests") == "anyone": allowed = True
    elif prefs.get("allowRequests") == "friends_of_friends": allowed = same_team(recipient_id, sender_id)
    if recipient_id in prefs.get("blocked", []): allowed = False
    if not allowed: st.error("This user does not accept message requests."); return
    st.session_state.messages.append({"from": sender_id, "to": recipient_id, "text": text, "ts": datetime.now().isoformat(timespec="seconds")})

def get_conversation(a,b):
    msgs = [m for m in st.session_state.messages if (m["from"]==a and m["to"]==b) or (m["from"]==b and m["to"]==a)]
    msgs.sort(key=lambda x: x["ts"]); return msgs

def add_route(uid, name, distance_km, notes, audience):
    st.session_state.routes.append({"user_id": uid, "name": name, "distance_km": float(distance_km), "notes": notes, "created_at": datetime.now().isoformat(timespec="seconds"), "audience": audience})
    u = ensure_user(uid, uid); u["routes_completed_month"].add(name)

def list_routes(uid): return [r for r in st.session_state.routes if r["user_id"] == uid]
def delete_route(uid, name): st.session_state.routes = [r for r in st.session_state.routes if not (r["user_id"]==uid and r["name"]==name)]

st.sidebar.title("👤 Profile")
user_id = st.sidebar.text_input("Your username", value="martha").strip() or "guest"
display_name = st.sidebar.text_input("Display name", value="Martha").strip() or user_id
city = st.sidebar.text_input("City", value="Atlanta").strip()
company = st.sidebar.text_input("Company (for leagues)", value="HealthCo").strip()
avail = st.sidebar.selectbox("Usual walk time", ["Mornings","Lunch","Evenings","Weekends"], index=0)
if st.sidebar.button("Save Profile"):
    u=ensure_user(user_id, display_name); u["name"]=display_name; u["city"]=city; u["company"]=company; u["available_times"]=avail; st.success("Profile saved!")

st.sidebar.markdown("---")
st.sidebar.title("👥 Team")
team_name = st.sidebar.text_input("Create/Join team", value="Comeback Kids").strip()
team_city = st.sidebar.text_input("Team City (optional)", value=city).strip()
team_company = st.sidebar.text_input("Team Company (optional)", value=company).strip()
if st.sidebar.button("Join Team"):
    u=ensure_user(user_id, display_name); u["team"]=team_name
    team=st.session_state.teams.setdefault(team_name, {"captain":user_id,"members":set(),"city":team_city,"company":team_company})
    team["members"].add(user_id); team["city"]=team_city; team["company"]=team_company
    st.success(f"You joined team: {team_name}")

st.sidebar.markdown("---")
st.sidebar.title("🔔 Reminders")
def init_reminders_sidebar():
    r=st.session_state.reminders; now=datetime.now()
    if r.get("next_walk_at") is None and r.get("walk_enabled",True): r["next_walk_at"]=now+timedelta(minutes=int(r.get("walk_every_min",120)))
    if r.get("next_stand_at") is None and r.get("stand_enabled",True): r["next_stand_at"]=now+timedelta(minutes=int(r.get("stand_every_min",30)))
init_reminders_sidebar()
r = st.session_state.reminders
c1,c2 = st.sidebar.columns(2)
with c1: r["walk_enabled"] = st.checkbox("Walk reminders", value=r.get("walk_enabled",True))
with c2: r["stand_enabled"] = st.checkbox("Stand/stretch", value=r.get("stand_enabled",True))
r["walk_every_min"] = st.sidebar.number_input("Walk every (min)", 15, 360, int(r.get("walk_every_min",120)))
r["stand_every_min"] = st.sidebar.number_input("Stand every (min)", 5, 120, int(r.get("stand_every_min",30)))
r["snooze_minutes"] = st.sidebar.number_input("Snooze (min)", 5, 60, int(r.get("snooze_minutes",10)))
if st.sidebar.button("Apply & Reset Timers"):
    now=datetime.now()
    if r.get("walk_enabled"): r["next_walk_at"]=now+timedelta(minutes=int(r.get("walk_every_min",120)))
    if r.get("stand_enabled"): r["next_stand_at"]=now+timedelta(minutes=int(r.get("stand_every_min",30)))
    st.sidebar.success("Reminder timers reset.")
st.sidebar.caption("Reminders run locally while the app is open.")

st.title("👟 Walking Buddies — Social Walking for Healthier Lifestyles")
tab_dash, tab_log, tab_leader, tab_challenges, tab_community, tab_rewards, tab_routes, tab_messages, tab_privacy = st.tabs(
    ["Dashboard","Log Walk","Leaderboards","Challenges","Community","Rewards","Routes","Messages","Privacy"]
)

def check_and_display_reminders():
    r=st.session_state.reminders; now=datetime.now()
    if r.get("walk_enabled") and r.get("next_walk_at") and now>=r["next_walk_at"]:
        st.warning("🚶 Time for a walk reminder!")
        c1,c2,c3=st.columns(3)
        with c1:
            if st.button("Start Walk Now"): r["next_walk_at"]=now+timedelta(minutes=int(r.get("walk_every_min",120))); st.success("Great! Log your walk in the 'Log Walk' tab.")
        with c2:
            if st.button("Snooze 10 min"): r["next_walk_at"]=now+timedelta(minutes=int(r.get("snooze_minutes",10))); st.info("Snoozed.")
        with c3:
            if st.button("Dismiss"): r["next_walk_at"]=now+timedelta(minutes=int(r.get("walk_every_min",120)))
    if r.get("stand_enabled") and r.get("next_stand_at") and now>=r["next_stand_at"]:
        st.info("🧍 Stand/Stretch reminder!")
        c1,c2=st.columns(2)
        with c1:
            if st.button("I Stood/Stretch"): r["next_stand_at"]=now+timedelta(minutes=int(r.get("stand_every_min",30))); st.success("Nice! Keep moving 🎉")
        with c2:
            if st.button("Snooze 5 min"): r["next_stand_at"]=now+timedelta(minutes=5); st.info("Snoozed.")

with tab_dash:
    st.subheader("Personal Dashboard")
    u=ensure_user(user_id, display_name)
    c1,c2,c3,c4=st.columns(4)
    with c1: st.metric("Points", int(u.get("points",0)))
    with c2: st.metric("Tier", tier_for_points(int(u.get("points",0))))
    with c3: st.metric("Total Walks", total_walks(u))
    with c4: st.metric("Miles (All-Time)", f"{total_miles(u):.1f}")
    st.progress(min(total_walks(u)/10,1.0), text=f"First 10 Walks: {total_walks(u)}/10")
    st.progress(min(total_miles(u)/100.0,1.0), text=f"100 Miles Club: {total_miles(u):.1f}/100.0")
    st.write(f"### Avatar Level: {u.get('avatar_level',1)}")
    st.divider()
    st.subheader("⏰ Reminders")
    check_and_display_reminders()

with tab_log:
    st.subheader("Log a Walk")
    st.markdown("#### ⏱️ Timer")
    running = st.session_state.get("timer_running", False)
    started_at = st.session_state.get("timer_started_at", None)
    accum = int(st.session_state.get("timer_accum_sec", 0))
    def _now(): return time.time()
    elapsed_sec = accum + (int(_now()-float(started_at)) if running and started_at else 0)
    st.info(f"Elapsed: **{elapsed_sec//60:02d}:{elapsed_sec%60:02d}** (mm:ss)")
    col_p1, col_p2 = st.columns(2)
    with col_p1: steps_per_min = st.number_input("Steps per minute", 20, 220, 100, 5, key="k_steps_per_min")
    with col_p2: miles_per_min = st.number_input("Miles per minute", 0.01, 0.20, 0.05, 0.005, format="%.3f", key="k_miles_per_min")
    c1,c2,c3,c4 = st.columns(4)
    with c1:
        if st.button("Start", disabled=running):
            st.session_state.timer_running=True; st.session_state.timer_started_at=_now(); st.session_state.timer_accum_sec=0; st.success("Timer started.")
    with c2:
        if st.button("Pause", disabled=not running):
            if running and started_at:
                st.session_state.timer_accum_sec = accum + int(_now()-float(started_at))
            st.session_state.timer_running=False; st.session_state.timer_started_at=None; st.info("Paused.")
    with c3:
        if st.button("Resume", disabled=running or accum==0):
            st.session_state.timer_running=True; st.session_state.timer_started_at=_now(); st.success("Resumed.")
    with c4:
        if st.button("Stop & Save", disabled=(not running and accum==0)):
            total_sec = accum + (int(_now()-float(started_at)) if running and started_at else 0)
            minutes_auto = max(1, total_sec//60)
            st.session_state["timer_save_minutes"]=minutes_auto
            st.session_state["timer_save_steps"]=int(minutes_auto*steps_per_min)
            st.session_state["timer_save_miles"]=round(minutes_auto*miles_per_min,2)
            st.session_state.timer_running=False; st.session_state.timer_started_at=None; st.session_state.timer_accum_sec=0; st.session_state["timer_prompt_open"]=True
    if st.session_state.get("timer_prompt_open"):
        st.warning("Save your timed walk:")
        tc1,tc2,tc3 = st.columns(3)
        with tc1: minutes_c = st.number_input("Minutes", 1, 300, int(st.session_state.get("timer_save_minutes", 10)))
        with tc2: steps_c   = st.number_input("Steps", 0, 200000, int(st.session_state.get("timer_save_steps", 1000)))
        with tc3: miles_c   = st.number_input("Miles", 0.0, 100.0, float(st.session_state.get("timer_save_miles", 0.5)), step=0.01, format="%.2f")
        is_group_c = st.checkbox("Group walk", value=False, key="k_timer_group")
        photo_c = st.checkbox("Shared a scenic photo", value=False, key="k_timer_photo")
        mood_c = st.selectbox("How do you feel now?", ["😀 Energized","🙂 Good","😐 Meh","😕 Tired","😔 Low"], index=1, key="k_timer_mood")
        b1,b2 = st.columns(2)
        with b1:
            if st.button("Save Walk"):
                g,t,streak = award_walk(user_id, int(minutes_c), int(steps_c), float(miles_c), is_group_c, photo_c, mood_c); update_challenges_after_walk(user_id)
                st.success(f"Saved timed walk: +{g} points! Total: {t} | Streak: {streak} day(s)."); st.session_state["timer_prompt_open"]=False
        with b2:
            if st.button("Cancel"):
                st.session_state["timer_prompt_open"]=False; st.info("Canceled.")
    st.divider()
    st.markdown("#### Manual Entry")
    colA,colB,colC = st.columns(3)
    with colA: minutes = st.number_input("Minutes", 1, 300, 30, key="k_manual_min")
    with colB: steps   = st.number_input("Steps", 0, 100000, 3500, key="k_manual_steps")
    with colC: miles_in= st.number_input("Miles", 0.0, 100.0, 1.5, step=0.01, format="%.2f", key="k_manual_miles")
    is_group = st.checkbox("Group walk", key="k_manual_group")
    photo    = st.checkbox("Shared a scenic photo", key="k_manual_photo")
    mood     = st.selectbox("How do you feel now?", ["😀 Energized","🙂 Good","😐 Meh","😕 Tired","😔 Low"], index=1, key="k_manual_mood")
    if st.button("Submit Walk"):
        g,t,streak = award_walk(user_id, minutes, steps, miles_in, is_group, photo, mood); update_challenges_after_walk(user_id); st.success(f"+{g} points! Total: {t} | Streak: {streak} day(s).")

with tab_leader:
    st.subheader("Leaderboards")
    users_df, teams_df, city_df, company_df = get_leaderboards(user_id)
    st.write("#### Individuals (privacy-aware)")
    st.dataframe(users_df if not users_df.empty else pd.DataFrame([], columns=["user","points","team","city","company"]), use_container_width=True)
    st.write("#### Teams")
    st.dataframe(teams_df if not teams_df.empty else pd.DataFrame([], columns=["team","points"]), use_container_width=True)
    st.write("#### City vs City (weekly steps)")
    st.dataframe(city_df if not city_df.empty else pd.DataFrame([], columns=["city","steps_week"]), use_container_width=True)
    st.write("#### Company Leagues")
    st.dataframe(company_df if not company_df.empty else pd.DataFrame([], columns=["company","points"]), use_container_width=True)

def join_or_leave_ui(uid, ch):
    uc = st.session_state.user_challenges.setdefault(uid, {}).setdefault(ch["id"], {"joined": False, "progress": {}, "completed": False, "last_reset": None})
    if uc["joined"]:
        if st.button(f"Leave '{ch['name']}'", key=f"leave_{ch['id']}"): uc["joined"] = False; st.info("Left challenge.")
    else:
        if st.button(f"Join '{ch['name']}'", key=f"join_{ch['id']}"): uc["joined"] = True; st.success("Joined challenge!")

def show_progress_ui(uid, ch):
    _ = st.session_state.user_challenges.setdefault(uid, {}).setdefault(ch["id"], {"joined": False, "progress": {}, "completed": False, "last_reset": None})
    u = ensure_user(uid, uid)
    if ch["id"] == "daily_5000":
        steps_today = int(u["steps_log"].get(date.today().isoformat(), 0))
        st.progress(min(steps_today / ch["target"], 1.0)); st.caption(f"{steps_today:,} / {ch['target']:,} steps today")
    elif ch["id"] == "weekend_walkathon":
        wd = date.today().weekday(); sat = date.today()+timedelta(days=(5-wd)) if wd<=5 else date.today()-timedelta(days=(wd-5)); sun = sat + timedelta(days=1)
        total = float(u["distance_miles_log"].get(sat.isoformat(), 0.0)) + float(u["distance_miles_log"].get(sun.isoformat(), 0.0))
        target = ch["target_miles"]; st.progress(min(total/target,1.0)); st.caption(f"{total:.2f} / {target:.2f} miles this weekend")
    elif ch["id"] == "photo_share":
        count = int(u["photos_this_week"]); st.progress(1.0 if count >= 1 else 0.0); st.caption("Photo shared this week" if count >= 1 else "No photo shared yet")
    if st.button(f"Check & Complete '{ch['name']}'", key=f"complete_{ch['id']}"):
        st.success("✅ Completed!") if complete_challenge_if_eligible(uid, ch) else st.warning("Not eligible yet—keep going!")

with tab_challenges:
    st.subheader("Challenges")
    st.caption("Join a challenge to track progress and claim points when you meet the target.")
    all_ch = list(st.session_state.challenge_catalog) + list(st.session_state.custom_challenges)
    for ch in all_ch:
        st.markdown(f"### {ch['name']}"); st.write(ch["desc"]); join_or_leave_ui(user_id, ch); show_progress_ui(user_id, ch); st.divider()
    st.markdown("## Create a Personalized Challenge")
    with st.form("create_custom"):
        name = st.text_input("Challenge name")
        desc = st.text_area("Description", height=80)
        scope = st.selectbox("Scope", ["individual","team"])
        metric = st.selectbox("Metric", ["steps","minutes","miles","walks"])
        target_value = st.number_input("Target value", min_value=1.0, value=10.0)
        period = st.selectbox("Period", ["daily","weekly","monthly","weekend"], index=1)
        reward_points = st.number_input("Reward points", min_value=0, value=100, step=10)
        submitted = st.form_submit_button("Create Challenge")
        if submitted:
            cid=f"custom_{int(time.time()*1000)}"
            st.session_state.custom_challenges.append({"id":cid,"name":name.strip(),"desc":desc.strip(),"custom":True,"scope":scope,"metric":metric,"target_value":float(target_value),"period":period,"reward_points":int(reward_points),"creator":user_id})
            st.success("Custom challenge created!")

with tab_community:
    st.subheader("Community")
    st.write("### Photo Feed (privacy-aware)")
    visible = []
    for p in sorted(st.session_state.photos, key=lambda x: x["ts"], reverse=True):
        if can_view(p["user_id"], user_id, p.get("audience","friends")):
            visible.append(p)
    if visible:
        for p in visible[:20]:
            poster = st.session_state.users.get(p["user_id"], {}).get("name", p["user_id"])
            st.write(f"**{poster}** [{p['ts']}]: {p['caption']} ({p.get('audience','friends')})")
            if p.get("img_bytes"): st.image(p["img_bytes"], width=480)
    else:
        st.info("No visible photos yet.")
    st.divider()
    st.write("### Find Local Buddies")
    buddies = find_local_buddies(user_id)
    u = ensure_user(user_id, display_name)
    if buddies:
        for b in buddies:
            col1, col2, col3 = st.columns([3,2,1])
            with col1: st.write(f"**{b['name']}** — {b['available_times']}")
            with col2:
                if st.button(f"Message {b['name']}", key=f"msg_{b['user_id']}"):
                    u["buddies"].add(b["user_id"]); st.session_state["active_chat"] = b["user_id"]; st.success(f"Chat with {b['name']} in Messages.")
            with col3:
                if st.button(f"Add Buddy", key=f"add_{b['user_id']}"):
                    u["buddies"].add(b["user_id"]); st.toast(f"Added {b['name']} as a buddy")
    else:
        st.info("No local matches yet. Update your city in profile and invite friends.")

with tab_rewards:
    st.subheader("Rewards & Badges")
    u=ensure_user(user_id, display_name)
    col1,col2 = st.columns(2)
    with col1:
        st.metric("Points", int(u.get("points",0))); st.metric("Tier", tier_for_points(int(u.get("points",0))))
        earned = st.session_state.badges.get(user_id, set())
        st.write("**Badges Earned:** " + (", ".join(earned) if earned else "None yet"))
        st.progress(min(total_walks(u)/10,1.0), text=f"First 10 Walks: {total_walks(u)}/10")
        st.progress(min(total_miles(u)/100.0,1.0), text=f"100 Miles: {total_miles(u):.1f}/100.0")
    with col2:
        st.markdown("### Redeem Rewards")
        for item in st.session_state.reward_catalog:
            c = st.container(border=True)
            with c:
                st.write(f"**{item['name']}** — {item['desc']} ({item['cost']} pts)")
                can = int(u.get("points",0)) >= int(item["cost"])
                if st.button(f"Redeem '{item['name']}'", disabled=not can, key=f"redeem_{item['id']}"):
                    u["points"] -= int(item["cost"]); st.success(f"Redeemed {item['name']}!")

with tab_routes:
    st.subheader("Training Log & Routes")
    rc1, rc2 = st.columns([2,1])
    with rc1:
        route_name = st.text_input("Route name")
        route_km = st.number_input("Distance (km)", 0.1, 200.0, 3.0, step=0.1, format="%.1f")
        route_notes = st.text_area("Notes (optional)", height=80)
        audience = st.selectbox("Share with", ["private","friends","team","public"], index=0)
    with rc2:
        if st.button("Add Route"):
            if route_name.strip(): add_route(user_id, route_name.strip(), route_km, route_notes.strip(), audience); st.success(f"Route '{route_name}' added.")
            else: st.error("Please provide a route name.")
    user_routes = list_routes(user_id)
    if user_routes:
        st.write("### My Routes")
        df = pd.DataFrame(user_routes); st.dataframe(df[["name","distance_km","notes","audience","created_at"]], use_container_width=True)
        del_name = st.selectbox("Delete a route", [""] + [r["name"] for r in user_routes])
        if st.button("Delete Selected Route"):
            if del_name: delete_route(user_id, del_name); st.success(f"Deleted route '{del_name}'.")
    else:
        st.info("No routes yet — add your first route above.")

with tab_messages:
    st.subheader("Messages")
    u = ensure_user(user_id, display_name)
    buddy_choices = sorted(list(u.get("buddies", set())))
    buddy = st.selectbox("Select a buddy", [""] + buddy_choices, index=0)
    if buddy:
        msgs = get_conversation(user_id, buddy)
        for m in msgs:
            who = "You" if m["from"] == user_id else st.session_state.users.get(m["from"],{}).get("name", m["from"])
            st.write(f"**{who}** [{m['ts']}]: {m['text']}")
        new_msg = st.text_input("Write a message")
        if st.button("Send"):
            if new_msg.strip(): send_message(user_id, buddy, new_msg.strip()); st.experimental_rerun()
    else:
        st.info("Add buddies from the Community tab to start messaging.")

with tab_privacy:
    st.subheader("Privacy Center")
    u = ensure_user(user_id, display_name)
    p = u["privacy"]
    st.markdown("### Profile visibility")
    p["profileVisibility"] = st.selectbox("Who can see your profile?", ["private","friends","team","public"], index=["private","friends","team","public"].index(p.get("profileVisibility","private")))
    c1,c2 = st.columns(2)
    with c1: p["showCity"] = st.checkbox("Show my city", value=bool(p.get("showCity", True)))
    with c2: p["showCompany"] = st.checkbox("Show my company", value=bool(p.get("showCompany", False)))
    st.markdown("---")
    st.markdown("### Leaderboards")
    lb = p.get("leaderboards", {"public": False, "alias": "", "teamVisible": True})
    lb["public"] = st.checkbox("Appear on public leaderboards", value=bool(lb.get("public", False)))
    lb["teamVisible"] = st.checkbox("Show me on my team's leaderboard", value=bool(lb.get("teamVisible", True)))
    lb["alias"] = st.text_input("Leaderboard alias (optional)", value=lb.get("alias",""))
    p["leaderboards"] = lb
    st.markdown("---")
    st.markdown("### Discoverability")
    disc = p.get("discoverability", {"byCity": True, "byCompany": False})
    disc["byCity"] = st.checkbox("Allow people in my city to find me", value=bool(disc.get("byCity", True)))
    disc["byCompany"] = st.checkbox("Allow coworkers to find me", value=bool(disc.get("byCompany", False)))
    p["discoverability"] = disc
    st.markdown("---")
    st.markdown("### Routes & Photos")
    routes = p.get("routes", {"defaultShare": "private"})
    routes["defaultShare"] = st.selectbox("Default route sharing", ["private","friends","team","public"], index=["private","friends","team","public"].index(routes.get("defaultShare","private")))
    p["routes"] = routes
    photos = p.get("photos", {"defaultAudience": "friends", "stripEXIF": True, "autoExpireDays": 365})
    photos["defaultAudience"] = st.selectbox("Default photo audience", ["private","friends","team","public"], index=["private","friends","team","public"].index(photos.get("defaultAudience","friends")))
    photos["stripEXIF"] = st.checkbox("Strip photo EXIF (location)", value=bool(photos.get("stripEXIF", True)))
    photos["autoExpireDays"] = st.number_input("Auto-hide photos after (days)", min_value=0, max_value=3650, value=int(photos.get("autoExpireDays",365)))
    p["photos"] = photos
    st.markdown("---")
    st.markdown("### Messaging")
    msg = p.get("messaging", {"allowRequests":"friends_of_friends","readReceipts": False,"blocked":[]})
    msg["allowRequests"] = st.selectbox("Who can message you?", ["anyone","friends_of_friends","friends_only"], index=["anyone","friends_of_friends","friends_only"].index(msg.get("allowRequests","friends_of_friends")))
    msg["readReceipts"] = st.checkbox("Send read receipts", value=bool(msg.get("readReceipts", False)))
    blocked = msg.get("blocked", [])
    block_user = st.text_input("Block user (enter username)")
    if st.button("Block"):
        if block_user and block_user not in blocked: blocked.append(block_user); st.success(f"Blocked {block_user}")
    msg["blocked"] = blocked
    p["messaging"] = msg
    st.markdown("---")
    st.markdown("### Security")
    sec = p.get("security", {"appLock": False, "twoFA": False})
    sec["appLock"] = st.checkbox("Enable app lock (passcode/biometric)", value=bool(sec.get("appLock", False)))
    sec["twoFA"] = st.checkbox("Enable 2FA for sign-in", value=bool(sec.get("twoFA", False)))
    p["security"] = sec
    if st.button("Save Privacy Settings"):
        u["privacy"] = p; st.success("Privacy settings saved."); st.balloons()

st.caption("Offline demo with in-memory storage + privacy controls. For production, add persistence (DB) and auth; connect Apple Health/Google Fit; enforce server-side.")
