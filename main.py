# -*- coding: utf-8 -*-
import time, random
from datetime import datetime, timedelta, date
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Walking Buddies", page_icon="👟", layout="wide")

# minimal state init
if "users" not in st.session_state: st.session_state.users = {}
if "timer_running" not in st.session_state: st.session_state.timer_running=False
if "timer_started_at" not in st.session_state: st.session_state.timer_started_at=None
if "timer_accum_sec" not in st.session_state: st.session_state.timer_accum_sec=0
if "timer_prompt_open" not in st.session_state: st.session_state.timer_prompt_open=False

POINT_RULES={"base_per_minute":1}

def ensure_user(uid):
    return st.session_state.users.setdefault(uid,{"points":0,"walk_dates":[]})

def award_walk(uid, minutes):
    u=ensure_user(uid)
    pts=minutes*POINT_RULES["base_per_minute"]
    u["points"]+=pts
    u["walk_dates"].append(datetime.now())
    return pts, u["points"], len(u["walk_dates"])

def _period_key(period:str)->str:
    today=date.today()
    if period=="daily":
        return today.isoformat()
    if period=="weekly":
        y,w,_=today.isocalendar()
        return f"{y}-W{w:02d}"
    if period=="monthly":
        return f"{today.year}-{today.month:02d}"
    return "alltime"

st.title("👟 Walking Buddies - Fixed Build")

tab1, tab2 = st.tabs(["Dashboard","Log Walk"])

with tab1:
    st.write("User stats dashboard (placeholder)")

with tab2:
    st.subheader("Log a Walk with Timer")
    running=st.session_state.timer_running
    started=st.session_state.timer_started_at
    accum=int(st.session_state.timer_accum_sec)
    now=time.time()
    elapsed=accum+(int(now-float(started)) if running and started else 0)
    st.info(f"Elapsed: {elapsed//60:02d}:{elapsed%60:02d} (mm:ss)")

    c1,c2,c3,c4=st.columns(4)
    if c1.button("Start", disabled=running):
        st.session_state.timer_running=True
        st.session_state.timer_started_at=time.time()
        st.session_state.timer_accum_sec=0
        st.success("Timer started")
    if c2.button("Pause", disabled=not running):
        if running and started:
            st.session_state.timer_accum_sec=accum+int(time.time()-float(started))
        st.session_state.timer_running=False
        st.session_state.timer_started_at=None
        st.info("Paused")
    if c3.button("Resume", disabled=running or accum==0):
        st.session_state.timer_running=True
        st.session_state.timer_started_at=time.time()
        st.success("Resumed")
    if c4.button("Stop & Save", disabled=(not running and accum==0)):
        total=accum+(int(time.time()-float(started)) if running and started else 0)
        minutes=max(1,total//60)
        pts, total_pts, streak=award_walk("user", minutes)
        st.session_state.timer_running=False
        st.session_state.timer_started_at=None
        st.session_state.timer_accum_sec=0
        st.success(f"Saved walk: +{pts} pts (total {total_pts}) streak {streak}")
