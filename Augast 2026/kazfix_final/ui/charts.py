"""Plotly visualizations."""
import pandas as pd
import plotly.express as px
import streamlit as st

def _layout(fig,height=420):
    fig.update_layout(height=height,margin=dict(l=30,r=20,t=50,b=30),hovermode="x unified")
    return fig

def ndvi_time_series(df, key="ndvi_time_series"):

    if df.empty: st.info("No NDVI statistics available."); return
    fig=px.line(df,x="date",y="mean_ndvi",markers=True,title="Monthly Mean NDVI",
                labels={"mean_ndvi":"Mean NDVI","date":"Month"})
    st.plotly_chart(_layout(fig),use_container_width=True,key=key)

def ndvi_statistics_chart(df):
    if df.empty:return
    fig=px.line(df,x="date",y=["mean_ndvi","median_ndvi","min_ndvi","max_ndvi"],
                title="Monthly NDVI statistics",labels={"value":"NDVI","date":"Month","variable":"Statistic"})
    st.plotly_chart(_layout(fig),use_container_width=True,key="ndvi_statistics")

def annual_ndvi_chart(df):
    if df.empty:return
    annual=df.groupby("year",as_index=False).agg(
        annual_mean_ndvi=("mean_ndvi","mean"),annual_median_ndvi=("median_ndvi","mean"),
        annual_std_ndvi=("std_ndvi","mean"))
    fig=px.line(annual,x="year",y=["annual_mean_ndvi","annual_median_ndvi"],
                markers=True,title="Annual NDVI summary",labels={"value":"NDVI","year":"Year","variable":"Metric"})
    st.plotly_chart(_layout(fig),use_container_width=True,key="annual_ndvi")

def lulc_area_chart(df,title="LULC area by class"):
    if df.empty: st.info("No LULC statistics available."); return
    fig=px.bar(df,x="class_name",y="area_ha",color="class_name",title=title,
               labels={"class_name":"Class","area_ha":"Area (ha)"})
    st.plotly_chart(_layout(fig,460),use_container_width=True,key="lulc_area")

def lulc_area_over_time(df,title):
    if df.empty:return
    fig=px.area(df,x="year",y="area_ha",color="class_name",title=title,
                labels={"area_ha":"Area (ha)","year":"Year","class_name":"Class"})
    st.plotly_chart(_layout(fig,480),use_container_width=True,key="lulc_area_over_time")

def endpoint_bar(df):
    fig=px.bar(df,x="metric",y="value",color="metric",title="Endpoint NDVI comparison",
               labels={"metric":"","value":"NDVI"})
    st.plotly_chart(_layout(fig,380),use_container_width=True,key="endpoint_bar")
