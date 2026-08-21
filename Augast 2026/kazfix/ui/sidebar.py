"""Sidebar controls."""
import calendar, streamlit as st
from datetime import date
import pandas as pd
from config import DEFAULT_START_YEAR, DEFAULT_END_YEAR, SEASONS

def render_sidebar():
    st.sidebar.header("⚙️ Analysis controls")
    start_year=st.sidebar.number_input("Analysis start",2006,DEFAULT_END_YEAR,DEFAULT_START_YEAR,1)
    end_year=st.sidebar.number_input("Analysis end",start_year,DEFAULT_END_YEAR,DEFAULT_END_YEAR,1)
    selected_year=st.sidebar.selectbox("Change-detection year",range(int(start_year),int(end_year)+1),index=len(range(int(start_year),int(end_year)+1))-1)
    st.sidebar.markdown("**Change-detection date range**")
    latest_complete = date.today().replace(day=1)
    latest_complete = (pd.Timestamp(latest_complete) - pd.offsets.Day(1)).date()
    range_start=st.sidebar.date_input(
        "Range start", date(int(start_year),1,1),
        min_value=date(int(start_year),1,1), max_value=latest_complete)
    range_end=st.sidebar.date_input(
        "Range end", latest_complete,
        min_value=range_start, max_value=latest_complete)
    start_month=range_start.month
    end_month=range_end.month
    dataset=st.sidebar.selectbox("NDVI dataset",["Landsat NDVI (30 m)"])
    confidence=st.sidebar.slider("Dynamic World confidence",0.0,1.0,0.6,0.05)
    scale=st.sidebar.selectbox("Analysis scale (m)",[10,30,60,120],index=1)
    show_all=st.sidebar.checkbox("Show all monthly NDVI map layers",True)
    return dict(start_year=int(start_year),end_year=int(end_year),selected_year=int(selected_year),
                start_month=int(start_month),end_month=int(end_month),dataset=dataset,
                confidence=float(confidence),scale=int(scale),show_all_monthly=show_all)
