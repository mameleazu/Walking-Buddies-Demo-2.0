# -*- coding: utf-8 -*-
import time, random
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional
import pandas as pd
import streamlit as st

APP_NAME = "Walking Buddies"
st.set_page_config(page_title=APP_NAME, page_icon="👟", layout="wide")

# =========================
# Session State & Defaults
# =========================
def _ensure_state():
    ss = st.session_state
    ss.setdefault("users", {})
    ss.setdefault("teams", {})  # team -> {"captain": uid, "members": set(), "roles": {uid: Role}, "city":..., "company":...}
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
    ss.setdefault("timer_save_cals", 0)
    # Motivational quotes
    ss.setdefault("quotes", [
        "Small steps add up to big wins.",
        "You’re one walk away from a better mood.",
        "Consistency beats intensity—just show up.",
        "Your future self will thank you for this walk.",
        "Movement is medicine—dose daily.",
        "Walk the talk: today is your day.",
        "Streaks start with day one. This is it.",
        "Miles make mindsets—go get yours.",
        "Breathe in progress, breathe out doubt.",
        "Make sidewalks your superpower."
    ])
_ensure_state()

POINT_RULES = {"base_per_minute":1,"streak_7":10,"streak_30":50,"group_walk_bonus":20,"invite_bonus":50,"photo_share":5}
TIERS=[("Platinum",5000),("Gold",1000),("Silver",500),("Bronze",0)]
ROLES=["Captain","Co-Captain","Player"]

# =========================
# Helpers
# =========================
def ensure_user(uid: str, name: Optional[str]=None)->Dict[str,Any]:
    user = st.session_state.users.setdefault(uid, {
        "name": name or uid, "points":0, "team":None, "company":"", "city":"", "available_times":"Mornings",
        "buddies": set(), "walk_dates":[], "steps_log":{}, "minutes_log":{}, "distance_miles_log":{},
        "calories_log":{},  # NEW
        "photos_this_week":0, "invites_this_month":0, "routes_completed_month": set(), "mood_log":{}, "avatar_level":1,
        "privacy": st.session_state.privacy_defaults.copy()
    })
    if "privacy" not in user: user["privacy"] = st.session_state.privacy_defaults.copy()
    if "calories_log" not in user: user["calories_log"] = {}
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
def total_calories(u): return sum(int(v) for v in u.get("calories_log",{}).values())

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

def award_walk(uid, minutes, steps, miles, calories, is_group, shared_photo, mood=None):
    u=ensure_user(uid,uid); today=date.today().isoformat()
    u["walk_dates"].append(datetime.now())
    u["minutes_log"][today]=int(u["minutes_log"].get(today,0))+int(minutes)
    u["steps_log"][today]=int(u["steps_log"].get(today,0))+int(steps)
    u["distance_miles_log"][today]=float(u["distance_miles_log"].get(today,0.0))+float(miles)
    u["calories_log"][today]=int(u["calories_log"].get(today,0))+int(calories)
    gained=int(minutes)*POINT_RULES["base_per_minute"]
    if is_group: gained+=POINT_RULES["group_walk_bonus"]
    if shared_photo: gained+=POINT_RULES["photo_share"]; u["photos_this_week"]=int(u.get("photos_this_week",0))+1
    s=calc_streak(u["walk_dates"])
    if s>=30: gained+=POINT_RULES["streak_30"]
    elif s>=7: gained+=POINT_RULES["streak_7"]
    u["points"]=int(u.get("points",0))+gained
    if mood: u["mood_log"][today]=mood
    check_and_award_badges(uid)
    return gained, u["points"], s

def invite_friend(uid, email):
    st.session_state.invites.append({"inviter":uid,"friend":email,"ts":time.time()})
    u=ensure_user(uid,uid); u["points"]=int(u.get("points",0))+POINT_RULES["invite_bonus"]
    u["invites_this_month"]=int(u.get("invites_this_month",0))+1
    return u["points"]

# Privacy helpers
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

def leaderboard_display_name(u: Dict[str,Any])->str:
    lb = u.get("privacy",{}).get("leaderboards", {})
    alias = (lb.get("alias") or "").strip()
    if alias: return alias
    name = (u.get("name") or "User").strip()
    parts = name.split()
    if len(parts)>=2: return f"{parts[0]} {parts[1][0]}."
    return name

# =========================
# Leaderboards (expanded team table)
# =========================
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

    # Build expanded team-member table with roles
    team_member_rows=[]
    for tname, tinfo in st.session_state.teams.items():
        for member in sorted(list(tinfo.get("members", set()))):
            u = ensure_user(member, member)
            # Only show if viewer is allowed to see them (public LB or same team or self)
            lb = u.get("privacy",{}).get("leaderboards", {"public": False, "teamVisible": True})
            include_public = bool(lb.get("public", False))
            same_team_ok = same_team(member, viewer_id) and bool(lb.get("teamVisible", True))
            if not (include_public or same_team_ok or member==viewer_id):
                continue
            role = tinfo.get("roles", {}).get(member, "Player")
            team_member_rows.append({
                "team": tname,
                "user": leaderboard_display_name(u),
                "points": int(u.get("points",0)),
                "role": role
            })
    team_members_df = pd.DataFrame(team_member_rows, columns=["team","user","points","role"])
    if not team_members_df.empty: team_members_df = team_members_df.sort_values(["team","role","points"], ascending=[True, True, False]).reset_index(drop=True)

    return users_df, teams_df, team_members_df, pd.DataFrame(city_rows), pd.DataFrame(comp_rows)

# =========================
# Reminders
# =========================
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

# =========================
# Routes, Photos, Messaging (minimal to keep demo concise)
# =========================
def add_route(uid, name, distance_km, notes, audience):
    st.session_state.routes.append({"user_id": uid, "name": name, "distance_km": float(distance_km), "notes": notes, "created_at": datetime.now().isoformat(timespec="seconds"), "audience": audience})
    u = ensure_user(uid, uid); u["routes_completed_month"].add(name)
def list_routes(uid): return [r for r in st.session_state.routes if r["user_id"] == uid]
def delete_route(uid, name): st.session_state.routes = [r for r in st.session_state.routes if not (r["user_id"]==uid and r["name"]==name)]
def send_message(sender_id, recipient_id, text):
    prefs = ensure_user(recipient_id).get("privacy",{}).get("messaging", {"allowRequests":"friends_of_friends","blocked":[]})
    allowed = True
    if recipient_id in prefs.get("blocked", []): allowed = False
    if not allowed: st.error("Recipient is not accepting messages."); return
    st.session_state.messages.append({"from": sender_id, "to": recipient_id, "text": text, "ts": datetime.now().isoformat(timespec="seconds")})
def get_conversation(a,b):
    msgs = [m for m in st.session_state.messages if (m["from"]==a and m["to"]==b) or (m["from"]==b and m["to"]==a)]
    msgs.sort(key=lambda x: x["ts"]); return msgs

# =========================
# Sidebar: Profile, Team (with Role), Reminders
# =========================
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
    team=st.session_state.teams.setdefault(team_name, {"captain":user_id,"members":set(),"roles":{}, "city":team_city,"company":team_company})
    team["members"].add(user_id); team["city"]=team_city; team["company"]=team_company
    if not team.get("roles"): team["roles"][user_id] = "Captain"; team["captain"]=user_id
    else: team["roles"].setdefault(user_id, "Player")
    st.success(f"You joined team: {team_name}")
# Allow role change for current team
if team_name and team_name in st.session_state.teams and user_id in st.session_state.teams[team_name].get("members", set()):
    team = st.session_state.teams[team_name]
    cur_role = team.get("roles", {}).get(user_id, "Player")
    new_role = st.sidebar.selectbox("Your team role", ROLES, index=ROLES.index(cur_role))
    if st.sidebar.button("Update Role"):
        team["roles"][user_id] = new_role
        if new_role == "Captain": team["captain"] = user_id
        st.sidebar.success("Role updated.")

st.sidebar.markdown("---")
st.sidebar.title("🔔 Reminders")
init_reminders()
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

# =========================
# Main UI Tabs
# =========================
st.title("👟 Walking Buddies — Social Walking for Healthier Lifestyles")
tab_dash, tab_log, tab_leader, tab_challenges, tab_community, tab_rewards, tab_routes, tab_messages, tab_privacy = st.tabs(
    ["Dashboard","Log Walk","Leaderboards","Challenges","Community","Rewards","Routes","Messages","Privacy"]
)

# Dashboard
with tab_dash:
    st.subheader("Personal Dashboard")
    u=ensure_user(user_id, display_name)
    # Daily Motivational Quote
    idx = (date.today().toordinal()) % len(st.session_state.quotes)
    st.info(f"🗣️ **Today’s motivation:** {st.session_state.quotes[idx]}")

    c1,c2,c3,c4=st.columns(4)
    with c1: st.metric("Points", int(u.get("points",0)))
    with c2: st.metric("Tier", tier_for_points(int(u.get("points",0))))
    with c3: st.metric("Total Walks", total_walks(u))
    with c4: st.metric("Miles (All-Time)", f"{total_miles(u):.1f}")

    c5,c6 = st.columns(2)
    today_iso = date.today().isoformat()
    with c5: st.metric("Calories Today", int(u.get("calories_log",{}).get(today_iso,0)))
    with c6: st.metric("Calories (All-Time)", int(total_calories(u)))

    st.progress(min(total_walks(u)/10,1.0), text=f"First 10 Walks: {total_walks(u)}/10")
    st.progress(min(total_miles(u)/100.0,1.0), text=f"100 Miles Club: {total_miles(u):.1f}/100.0")
    st.write(f"### Avatar Level: {u.get('avatar_level',1)}")
    st.divider()
    st.subheader("⏰ Reminders")
    check_and_display_reminders()

# Log Walk (Timer + Manual) with calories
with tab_log:
    st.subheader("Log a Walk")
    st.markdown("#### ⏱️ Timer")
    running = st.session_state.get("timer_running", False)
    started_at = st.session_state.get("timer_started_at", None)
    accum = int(st.session_state.get("timer_accum_sec", 0))
    def _now(): return time.time()
    elapsed_sec = accum + (int(_now()-float(started_at)) if running and started_at else 0)
    st.info(f"Elapsed: **{elapsed_sec//60:02d}:{elapsed_sec%60:02d}** (mm:ss)")
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1: steps_per_min = st.number_input("Steps per minute", 20, 220, 100, 5, key="k_steps_per_min")
    with col_p2: miles_per_min = st.number_input("Miles per minute", 0.01, 0.20, 0.05, 0.005, format="%.3f", key="k_miles_per_min")
    with col_p3: cals_per_min  = st.number_input("Calories per minute", 1, 50, 5, 1, key="k_cals_per_min")

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
            st.session_state["timer_save_cals"]=int(minutes_auto*cals_per_min)
            st.session_state.timer_running=False; st.session_state.timer_started_at=None; st.session_state.timer_accum_sec=0; st.session_state["timer_prompt_open"]=True
    if st.session_state.get("timer_prompt_open"):
        st.warning("Save your timed walk:")
        tc1,tc2,tc3,tc4 = st.columns(4)
        with tc1: minutes_c = st.number_input("Minutes", 1, 300, int(st.session_state.get("timer_save_minutes", 10)))
        with tc2: steps_c   = st.number_input("Steps", 0, 200000, int(st.session_state.get("timer_save_steps", 1000)))
        with tc3: miles_c   = st.number_input("Miles", 0.0, 100.0, float(st.session_state.get("timer_save_miles", 0.5)), step=0.01, format="%.2f")
        with tc4: cals_c    = st.number_input("Calories", 0, 5000, int(st.session_state.get("timer_save_cals", 50)))
        is_group_c = st.checkbox("Group walk", value=False, key="k_timer_group")
        photo_c = st.checkbox("Shared a scenic photo", value=False, key="k_timer_photo")
        mood_c = st.selectbox("How do you feel now?", ["😀 Energized","🙂 Good","😐 Meh","😕 Tired","😔 Low"], index=1, key="k_timer_mood")
        b1,b2 = st.columns(2)
        with b1:
            if st.button("Save Walk"):
                g,t,streak = award_walk(user_id, int(minutes_c), int(steps_c), float(miles_c), int(cals_c), is_group_c, photo_c, mood_c)
                st.success(f"Saved timed walk: +{g} points! Total: {t} | Streak: {streak} day(s).")
                st.session_state["timer_prompt_open"]=False
        with b2:
            if st.button("Cancel"):
                st.session_state["timer_prompt_open"]=False; st.info("Canceled.")
    st.divider()
    st.markdown("#### Manual Entry")
    colA,colB,colC,colD = st.columns(4)
    with colA: minutes = st.number_input("Minutes", 1, 300, 30, key="k_manual_min")
    with colB: steps   = st.number_input("Steps", 0, 100000, 3500, key="k_manual_steps")
    with colC: miles_in= st.number_input("Miles", 0.0, 100.0, 1.5, step=0.01, format="%.2f", key="k_manual_miles")
    with colD: cals_in = st.number_input("Calories", 0, 5000, 120, key="k_manual_cals")
    is_group = st.checkbox("Group walk", key="k_manual_group")
    photo    = st.checkbox("Shared a scenic photo", key="k_manual_photo")
    mood     = st.selectbox("How do you feel now?", ["😀 Energized","🙂 Good","😐 Meh","😕 Tired","😔 Low"], index=1, key="k_manual_mood")
    if st.button("Submit Walk"):
        g,t,streak = award_walk(user_id, minutes, steps, miles_in, cals_in, is_group, photo, mood)
        st.success(f"+{g} points! Total: {t} | Streak: {streak} day(s).")

# Leaderboards (with expanded team member table & roles)
with tab_leader:
    st.subheader("Leaderboards")
    users_df, teams_df, team_members_df, city_df, company_df = get_leaderboards(user_id)
    st.write("#### Individuals (privacy-aware)")
    st.dataframe(users_df if not users_df.empty else pd.DataFrame([], columns=["user","points","team","city","company"]), use_container_width=True)
    st.write("#### Teams (aggregate points)")
    st.dataframe(teams_df if not teams_df.empty else pd.DataFrame([], columns=["team","points"]), use_container_width=True)
    st.write("#### Team Members & Roles")
    st.dataframe(team_members_df if not team_members_df.empty else pd.DataFrame([], columns=["team","user","points","role"]), use_container_width=True)

# Challenges (kept from full build, simplified list)
with tab_challenges:
    st.subheader("Challenges")
    st.caption("Join a challenge to track progress and claim points when you meet the target.")
    for ch in (st.session_state.challenge_catalog + st.session_state.custom_challenges):
        st.markdown(f"**{ch['name']}** — {ch['desc']} *(+{ch.get('reward_points',0)} pts)*")
        st.divider()

# Community (minimal feed sample)
with tab_community:
    st.subheader("Community")
    st.info("Photo feed and buddy finder respect privacy settings. (Demo content when photos are posted.)")

# Rewards
with tab_rewards:
    st.subheader("Rewards & Badges")
    u=ensure_user(user_id, display_name)
    col1,col2 = st.columns(2)
    with col1:
        st.metric("Points", int(u.get("points",0))); st.metric("Tier", tier_for_points(int(u.get("points",0))))
        earned = st.session_state.badges.get(user_id, set())
        st.write("**Badges Earned:** " + (", ".join(earned) if earned else "None yet"))
    with col2:
        st.markdown("### Redeem Rewards")
        for item in st.session_state.reward_catalog:
            c = st.container(border=True)
            with c:
                st.write(f"**{item['name']}** — {item['desc']} ({item['cost']} pts)")
                can = int(u.get("points",0)) >= int(item["cost"])
                if st.button(f"Redeem '{item['name']}'", disabled=not can, key=f"redeem_{item['id']}"):
                    u["points"] -= int(item["cost"]); st.success(f"Redeemed {item['name']}!")

# Routes
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

# Messages
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

# Privacy Center (kept concise for this merge)
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
    st.markdown("### Messaging & Security")
    msg = p.get("messaging", {"allowRequests":"friends_of_friends","readReceipts": False,"blocked":[]})
    msg["allowRequests"] = st.selectbox("Who can message you?", ["anyone","friends_of_friends","friends_only"], index=["anyone","friends_of_friends","friends_only"].index(msg.get("allowRequests","friends_of_friends")))
    msg["readReceipts"] = st.checkbox("Send read receipts", value=bool(msg.get("readReceipts", False)))
    blocked = msg.get("blocked", [])
    block_user = st.text_input("Block user (enter username)")
    if st.button("Block"):
        if block_user and block_user not in blocked: blocked.append(block_user); st.success(f"Blocked {block_user}")
    msg["blocked"] = blocked
    p["messaging"] = msg
    sec = p.get("security", {"appLock": False, "twoFA": False})
    sec["appLock"] = st.checkbox("Enable app lock (passcode/biometric)", value=bool(sec.get("appLock", False)))
    sec["twoFA"] = st.checkbox("Enable 2FA for sign-in", value=bool(sec.get("twoFA", False)))
    p["security"] = sec
    if st.button("Save Privacy Settings"):
        u["privacy"] = p; st.success("Privacy settings saved."); st.balloons()
