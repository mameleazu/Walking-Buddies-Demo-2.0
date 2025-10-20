# -*- coding: utf-8 -*-
import os, io, random, time
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional
import pandas as pd
import streamlit as st

APP_NAME = "Walking Buddies"
st.set_page_config(page_title=APP_NAME, page_icon="👟", layout="wide")

# ---- state ----
def _ensure_state():
    ss = st.session_state
    ss.setdefault("users", {}); ss.setdefault("teams", {}); ss.setdefault("invites", [])
    ss.setdefault("routes", []); ss.setdefault("messages", []); ss.setdefault("photos", [])
    ss.setdefault("reminders", {"walk_enabled": True,"walk_every_min": 120,"stand_enabled": True,"stand_every_min": 30,"next_walk_at": None,"next_stand_at": None,"snooze_minutes": 10})
    ss.setdefault("group_walk_rooms", {})
    ss.setdefault("challenge_catalog", [
        {"id":"daily_5000","name":"Daily Step Goal","desc":"Hit 5,000 steps today","type":"daily_steps","target":5000,"period":"daily","reward_points":50},
        {"id":"weekend_walkathon","name":"Weekend Walkathon","desc":"Walk 10 miles Sat–Sun","type":"distance_period","target_miles":10.0,"period":"weekend","reward_points":150},
        {"id":"photo_share","name":"Photo Challenge","desc":"Share a scenic walk photo this week","type":"boolean_weekly","target":1,"period":"weekly","reward_points":20},
        {"id":"invite_3","name":"Invite Challenge","desc":"Invite 3 friends this month","type":"count_monthly","target":3,"period":"monthly","reward_points":100},
        {"id":"team_100_miles","name":"Team Mileage Goal","desc":"Teams aim for 100 miles combined this week","type":"team_distance_weekly","target_miles":100.0,"period":"weekly","reward_points":300},
    ])
    ss.setdefault("custom_challenges", []); ss.setdefault("user_challenges", {})
    ss.setdefault("reward_catalog", [
        {"id":"badge_10_walks","type":"badge","name":"First 10 Walks","cost":0,"desc":"Milestone badge after 10 walks"},
        {"id":"badge_100_miles","type":"badge","name":"100 Miles Club","cost":0,"desc":"Milestone badge after 100 miles"},
        {"id":"coupon_sneakers","type":"coupon","name":"Sneaker Discount $10","cost":300,"desc":"$10 off partner sneakers"},
        {"id":"coupon_cafe","type":"coupon","name":"Local Cafe $5","cost":150,"desc":"$5 voucher at partner cafe"},
        {"id":"giftcard","type":"gift","name":"Gift Card $20","cost":800,"desc":"Generic gift card"},
        {"id":"premium_challenge","type":"unlock","name":"Exclusive Challenge Pack","cost":400,"desc":"Unlock premium challenge set"},
    ])
    ss.setdefault("badges", {}); ss.setdefault("donations", []); ss.setdefault("collectibles", {})
    # timer
    ss.setdefault("timer_running", False); ss.setdefault("timer_started_at", None); ss.setdefault("timer_accum_sec", 0)
_ensure_state()

POINT_RULES = {"base_per_minute":1,"streak_7":10,"streak_30":50,"group_walk_bonus":20,"invite_bonus":50,"photo_share":5}
TIERS=[("Platinum",5000),("Gold",1000),("Silver",500),("Bronze",0)]

def ensure_user(uid, name=None):
    return st.session_state.users.setdefault(uid, {
        "name": name or uid, "points":0, "team":None, "company":"", "city":"", "available_times":"Mornings",
        "buddies": set(), "walk_dates":[], "steps_log":{}, "minutes_log":{}, "distance_miles_log":{},
        "photos_this_week":0, "invites_this_month":0, "routes_completed_month": set(), "mood_log":{}, "avatar_level":1
    })

def calc_streak(ds):
    if not ds: return 0
    dates=sorted({d.date() for d in ds}, reverse=True); s=0; today=date.today()
    for d in dates:
        if d == today - timedelta(days=s): s+=1
        elif d < today - timedelta(days=s): break
    return s

def tier_for_points(p):
    for name, th in TIERS:
        if p>=th: return name
    return "Bronze"

def total_walks(u): return len(u.get("walk_dates",[]))
def total_miles(u): return sum(float(v) for v in u.get("distance_miles_log",{}).values())

def add_points(uid, pts, reason=""):
    u=ensure_user(uid,uid); u["points"]=int(u.get("points",0))+int(pts)
    if reason: st.toast(f"+{pts} pts: {reason}")

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
    return gained, u["points"], s

def invite_friend(uid, email):
    st.session_state.invites.append({"inviter":uid,"friend":email,"ts":time.time()})
    u=ensure_user(uid,uid); u["points"]=int(u.get("points",0))+POINT_RULES["invite_bonus"]
    u["invites_this_month"]=int(u.get("invites_this_month",0))+1
    return u["points"]

def get_leaderboards():
    users=st.session_state.users; rows=[]; team_points={}; city_rows=[]; comp_rows=[]
    for uid,u in users.items():
        rows.append({"user":u.get("name") or uid,"points":int(u.get("points",0)),"team":u.get("team") or "","city":u.get("city",""),"company":u.get("company","")})
        if u.get("team"): team_points[u["team"]] = team_points.get(u["team"],0) + int(u.get("points",0))
    users_df=pd.DataFrame(rows, columns=["user","points","team","city","company"])
    if not users_df.empty: users_df=users_df.sort_values("points",ascending=False).reset_index(drop=True)
    teams_df=pd.DataFrame([{"team":k,"points":v} for k,v in team_points.items()], columns=["team","points"])
    if not teams_df.empty: teams_df=teams_df.sort_values("points",ascending=False).reset_index(drop=True)
    if not users_df.empty:
        cities=users_df["city"].dropna().unique()
        y,w,_=date.today().isocalendar(); monday=date.fromisocalendar(y,w,1)
        for c in cities:
            if not c: continue
            total=0
            for uid,u in users.items():
                if u.get("city","")==c:
                    for i in range(7):
                        di=(monday+timedelta(days=i)).isoformat()
                        total+=int(u.get("steps_log",{}).get(di,0))
            city_rows.append({"city":c,"steps_week":total})
    city_df=pd.DataFrame(city_rows)
    if not city_df.empty: city_df=city_df.sort_values("steps_week",ascending=False).reset_index(drop=True)
    if not users_df.empty:
        for co in users_df["company"].dropna().unique():
            if not co: continue
            comp_rows.append({"company":co,"points":int(users_df[users_df["company"]==co]["points"].sum())})
    company_df=pd.DataFrame(comp_rows)
    if not company_df.empty: company_df=company_df.sort_values("points",ascending=False).reset_index(drop=True)
    return users_df, teams_df, city_df, company_df

# Sidebar
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
if st.sidebar.button("Join Team"):
    u=ensure_user(user_id, display_name); u["team"]=team_name
    team=st.session_state.teams.setdefault(team_name, {"captain":user_id,"members":set()}); team["members"].add(user_id)
    st.success(f"You joined team: {team_name}")

st.sidebar.markdown("---")
st.sidebar.title("🔔 Reminders")
r=st.session_state.reminders
def _init_r():
    now=datetime.now()
    if r.get("next_walk_at") is None and r.get("walk_enabled",True): r["next_walk_at"]=now+timedelta(minutes=int(r.get("walk_every_min",120)))
    if r.get("next_stand_at") is None and r.get("stand_enabled",True): r["next_stand_at"]=now+timedelta(minutes=int(r.get("stand_every_min",30)))
_init_r()
c1,c2=st.sidebar.columns(2)
with c1: r["walk_enabled"]=st.checkbox("Walk reminders", value=r.get("walk_enabled",True))
with c2: r["stand_enabled"]=st.checkbox("Stand/stretch", value=r.get("stand_enabled",True))
r["walk_every_min"]=st.sidebar.number_input("Walk every (min)",15,360,int(r.get("walk_every_min",120)))
r["stand_every_min"]=st.sidebar.number_input("Stand every (min)",5,120,int(r.get("stand_every_min",30)))
r["snooze_minutes"]=st.sidebar.number_input("Snooze (min)",5,60,int(r.get("snooze_minutes",10)))
if st.sidebar.button("Apply & Reset Timers"):
    now=datetime.now()
    if r.get("walk_enabled"): r["next_walk_at"]=now+timedelta(minutes=int(r.get("walk_every_min",120)))
    if r.get("stand_enabled"): r["next_stand_at"]=now+timedelta(minutes=int(r.get("stand_every_min",30)))
    st.sidebar.success("Reminder timers reset.")
st.sidebar.caption("Reminders run locally while the app is open.")

# Main UI
st.title("👟 Walking Buddies — Social Walking for Healthier Lifestyles")
tab_dash, tab_log, tab_leader, tab_community, tab_rewards, tab_routes = st.tabs(["Dashboard","Log Walk","Leaderboards","Community","Rewards","Routes"])

with tab_dash:
    st.subheader("Personal Dashboard")
    u=ensure_user(user_id, display_name)
    c1,c2,c3,c4=st.columns(4)
    with c1: st.metric("Points", int(u.get("points",0)))
    with c2: st.metric("Tier", tier_for_points(int(u.get("points",0))))
    with c3: st.metric("Total Walks", total_walks(u))
    with c4: st.metric("Miles (All-Time)", f"{total_miles(u):.1f}")
    st.progress(min(total_walks(u)/10,1.0), text=f"First 10 Walks: {total_walks(u)}/10")
    if r.get("next_walk_at") and datetime.now()>=r["next_walk_at"]:
        st.warning("🚶 Time for a walk reminder!")
    if r.get("next_stand_at") and datetime.now()>=r["next_stand_at"]:
        st.info("🧍 Stand/Stretch reminder!")

with tab_log:
    st.subheader("Log a Walk")
    # Timer controls
    st.markdown("#### ⏱️ Timer")
    running = st.session_state.get("timer_running", False)
    started_at = st.session_state.get("timer_started_at", None)
    accum = int(st.session_state.get("timer_accum_sec", 0))
    now=time.time()
    elapsed = accum + (int(now - float(started_at)) if running and started_at else 0)
    st.info(f"Elapsed: **{elapsed//60:02d}:{elapsed%60:02d}** (mm:ss)")
    col_pt1, col_pt2 = st.columns(2)
    with col_pt1:
        spm = st.number_input("Steps/min (est.)", 20, 220, 100, 5, key="k_spm")
    with col_pt2:
        mpm = st.number_input("Miles/min (est.)", 0.01, 0.20, 0.05, 0.005, format="%.3f", key="k_mpm")
    cta1, cta2, cta3, cta4 = st.columns(4)
    with cta1:
        if st.button("Start", disabled=running):
            st.session_state.timer_running=True; st.session_state.timer_started_at=time.time(); st.session_state.timer_accum_sec=0; st.success("Timer started.")
    with cta2:
        if st.button("Pause", disabled=not running):
            if running and started_at: st.session_state.timer_accum_sec = accum + int(time.time()-float(started_at))
            st.session_state.timer_running=False; st.session_state.timer_started_at=None; st.info("Paused.")
    with cta3:
        if st.button("Resume", disabled=running or accum==0):
            st.session_state.timer_running=True; st.session_state.timer_started_at=time.time(); st.success("Resumed.")
    with cta4:
        if st.button("Stop & Save", disabled=(not running and accum==0)):
            total = accum + (int(time.time()-float(started_at)) if running and started_at else 0)
            minutes_auto=max(1, total//60)
            st.session_state["timer_prompt_open"]=True
            st.session_state["timer_save_minutes"]=minutes_auto
            st.session_state["timer_save_steps"]=int(minutes_auto*spm)
            st.session_state["timer_save_miles"]=round(minutes_auto*mpm,2)
            st.session_state.timer_running=False; st.session_state.timer_started_at=None; st.session_state.timer_accum_sec=0

    if st.session_state.get("timer_prompt_open"):
        st.warning("Save your timed walk:")
        tc1, tc2, tc3 = st.columns(3)
        with tc1: m_c = st.number_input("Minutes", 1, 300, int(st.session_state.get("timer_save_minutes", 10)))
        with tc2: s_c = st.number_input("Steps", 0, 200000, int(st.session_state.get("timer_save_steps", 1000)))
        with tc3: mi_c = st.number_input("Miles", 0.0, 100.0, float(st.session_state.get("timer_save_miles", 0.5)), step=0.01, format="%.2f")
        is_group_c = st.checkbox("Group walk", value=False, key="k_t_group")
        photo_c = st.checkbox("Shared a scenic photo", value=False, key="k_t_photo")
        mood_c = st.selectbox("How do you feel now?", ["😀 Energized","🙂 Good","😐 Meh","😕 Tired","😔 Low"], index=1, key="k_t_mood")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Save Walk"):
                g,t,streak = award_walk(user_id, int(m_c), int(s_c), float(mi_c), is_group_c, photo_c, mood_c)
                st.success(f"Saved timed walk: +{g} points! Total: {t} | Streak: {streak} day(s)."); st.session_state["timer_prompt_open"]=False
        with b2:
            if st.button("Cancel"):
                st.session_state["timer_prompt_open"]=False; st.info("Canceled.")

    st.divider()
    st.markdown("#### Manual Entry")
    colA,colB,colC=st.columns(3)
    with colA: minutes=st.number_input("Minutes",1,300,30, key="k_m_min")
    with colB: steps=st.number_input("Steps",0,100000,3500, key="k_m_steps")
    with colC: miles_in=st.number_input("Miles",0.0,100.0,1.5,format="%.2f", key="k_m_miles")
    is_group=st.checkbox("Group walk", key="k_m_group"); photo=st.checkbox("Shared a scenic photo", key="k_m_photo")
    mood=st.selectbox("How do you feel now?", ["😀 Energized","🙂 Good","😐 Meh","😕 Tired","😔 Low"], index=1, key="k_m_mood")
    if st.button("Submit Walk"):
        g,t,streak=award_walk(user_id, minutes, steps, miles_in, is_group, photo, mood); st.success(f"+{g} points! Total: {t} | Streak: {streak} day(s).")

with tab_leader:
    st.subheader("Leaderboards")
    users_df, teams_df, city_df, company_df = get_leaderboards()
    st.write("#### Individuals")
    st.dataframe(users_df if not users_df.empty else pd.DataFrame([], columns=["user","points","team","city","company"]), use_container_width=True)
    st.write("#### Teams")
    st.dataframe(teams_df if not teams_df.empty else pd.DataFrame([], columns=["team","points"]), use_container_width=True)
    st.write("#### City vs City (Weekly Steps)")
    st.dataframe(city_df if not city_df.empty else pd.DataFrame([], columns=["city","steps_week"]), use_container_width=True)
    st.write("#### Company Leagues (Points)")
    st.dataframe(company_df if not company_df.empty else pd.DataFrame([], columns=["company","points"]), use_container_width=True)

with tab_community:
    st.subheader("Community")
    st.write("### Photo Feed")
    if st.session_state.photos:
        for p in sorted(st.session_state.photos, key=lambda x: x["ts"], reverse=True)[:20]:
            poster = st.session_state.users.get(p["user_id"], {}).get("name", p["user_id"])
            st.write(f"**{poster}** [{p['ts']}]: {p['caption']}")
            if p["img_bytes"]:
                st.image(p["img_bytes"], width=480)
    else:
        st.info("No photos yet. Post one from the Log Walk tab!")

with tab_rewards:
    st.subheader("Rewards & Badges")
    u=ensure_user(user_id, display_name)
    st.metric("Points", int(u.get("points",0)))
    for item in st.session_state.reward_catalog:
        can=int(u.get("points",0))>=int(item["cost"])
        if st.button(f"Redeem {item['name']} ({item['cost']} pts)", disabled=not can, key=f"redeem_{item['id']}"):
            u["points"]-=int(item["cost"]); st.success(f"Redeemed {item['name']}!")

with tab_routes:
    st.subheader("Training Log & Routes")
    route_name=st.text_input("Route name")
    route_km=st.number_input("Distance (km)",0.1,200.0,3.0,format="%.2f")
    route_notes=st.text_area("Notes (optional)", height=80)
    if st.button("Add Route"):
        if route_name.strip():
            st.session_state.routes.append({"user_id": user_id, "name": route_name.strip(), "distance_km": float(route_km), "notes": route_notes.strip(), "created_at": datetime.now().isoformat(timespec="seconds")})
            st.success(f"Route '{route_name}' added.")
        else:
            st.error("Please provide a route name.")
    user_routes=[r for r in st.session_state.routes if r["user_id"]==user_id]
    if user_routes:
        df=pd.DataFrame(user_routes); st.dataframe(df[["name","distance_km","notes","created_at"]], use_container_width=True)
        del_name = st.selectbox("Delete a route", [""] + [r["name"] for r in user_routes])
        if st.button("Delete Selected Route"):
            if del_name: st.session_state.routes=[r for r in st.session_state.routes if not (r["user_id"]==user_id and r["name"]==del_name)]; st.success(f"Deleted route '{del_name}'.")
    else:
        st.info("No routes yet — add your first route above.")

st.caption("Offline demo. Add DB for persistence + auth in production.")
