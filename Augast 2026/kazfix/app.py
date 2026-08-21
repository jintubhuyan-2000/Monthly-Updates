"""Kaziranga 20-Year Ecological Change Explorer."""
from datetime import date
import math
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import ee

from config import *
from gee_init import initialize_ee
from datasets.ndvi import monthly_landsat_collection, monthly_ndvi_feature_collection, monthly_ndvi
from datasets.dynamic_world import annual_label as dw_annual
from datasets.esri_lulc import annual_label as esri_annual
from datasets.modis_lulc import annual_label as modis_annual
from analysis.change_detection import image_difference, percent_change, endpoint_stats
from analysis.trend import trend_slope
from ui.sidebar import render_sidebar
from ui.charts import ndvi_time_series, ndvi_statistics_chart, annual_ndvi_chart, lulc_area_chart, lulc_area_over_time
from ui.map import create_map, add_ndvi_layer, add_change_layer, add_lulc_layer

st.set_page_config(page_title=APP_TITLE,page_icon="🌿",layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
.block-container{padding-top:1.2rem;padding-bottom:2rem}
.metric-card{border:1px solid rgba(128,128,128,.25);border-radius:16px;padding:12px}
.hero{padding:18px 22px;border-radius:20px;background:linear-gradient(120deg,#0b3d2e,#1b6b50);color:white;margin-bottom:16px}
.small-note{opacity:.75;font-size:.9rem}
</style>
""",unsafe_allow_html=True)

st.markdown('<div class="hero"><h1>🌿 Kaziranga Ecological Change Explorer</h1><div>Monthly NDVI • endpoint change detection • statistical trends • multi-source LULC</div></div>',unsafe_allow_html=True)

initialize_ee()

@st.cache_resource
def load_roi():
    """Load the fixed Kaziranga project asset; all analysis is constrained to this ROI."""
    return ee.FeatureCollection("projects/webapp-385310/assets/Kaziranga")
roi=load_roi()
controls=render_sidebar()
start_year,end_year=controls["start_year"],controls["end_year"]

if end_year>date.today().year: st.error("Analysis end cannot be in the future."); st.stop()

@st.cache_resource(show_spinner=False)
def get_ndvi_collection(start_year,end_year):
    return monthly_landsat_collection(start_year,end_year,roi)

with st.status("🛰️ Preparing Earth Engine monthly NDVI collection…",expanded=False) as status:
    ndvi_collection=get_ndvi_collection(start_year,end_year)
    status.update(label="NDVI collection ready",state="complete")

@st.cache_data(ttl=3600,show_spinner=False)
def get_monthly_stats(start_year,end_year,scale):
    fc=monthly_ndvi_feature_collection(get_ndvi_collection(start_year,end_year),roi,scale)
    return pd.DataFrame([x["properties"] for x in fc.getInfo()["features"]])

with st.spinner("Computing ROI statistics…"):
    df=get_monthly_stats(start_year,end_year,controls["scale"])
if not df.empty:
    df["date"]=pd.to_datetime(df["date"]); df=df.sort_values("date")
    for c in ["mean_ndvi","median_ndvi","min_ndvi","max_ndvi","std_ndvi"]:
        df[c]=pd.to_numeric(df[c],errors="coerce")
    df=df.dropna(subset=["mean_ndvi"])

# ---------- statistical helpers ----------
def kendall_test(values):
    x=np.asarray(values,dtype=float); n=len(x)
    if n<3:return {"tau":np.nan,"p":np.nan,"direction":"Insufficient data"}
    s=0
    for i in range(n-1):
        s += np.sign(x[i+1:]-x[i]).sum()
    # tie-corrected variance
    _,counts=np.unique(x,return_counts=True)
    tie_term=sum(t*(t-1)*(2*t+5) for t in counts if t>1)
    var=(n*(n-1)*(2*n+5)-tie_term)/18
    if var<=0:return {"tau":0.0,"p":1.0,"direction":"No trend"}
    z=(s-1)/math.sqrt(var) if s>0 else (s+1)/math.sqrt(var) if s<0 else 0
    p=math.erfc(abs(z)/math.sqrt(2))
    tau=s/(0.5*n*(n-1))
    return {"tau":tau,"p":p,"direction":"Increasing" if tau>0 else "Decreasing" if tau<0 else "No trend"}

def sen_slope(values,years):
    y=np.asarray(values,float); x=np.asarray(years,float)
    slopes=[]
    for i in range(len(y)-1):
        dx=x[i+1:]-x[i]
        slopes.extend(((y[i+1:]-y[i])/dx).tolist())
    return float(np.median(slopes)) if slopes else np.nan

trend_result=kendall_test(df["mean_ndvi"].values) if not df.empty else {"tau":np.nan,"p":np.nan,"direction":"N/A"}
sen=sen_slope(df["mean_ndvi"].values,df["date"].dt.year.values+df["date"].dt.month.values/12) if not df.empty else np.nan
if not df.empty and len(df)>=2:
    x=(df["date"]-df["date"].min()).dt.days/365.25
    coef=np.polyfit(x,df["mean_ndvi"],1)
    linear_slope=float(coef[0])
    pred=np.polyval(coef,x)
    ssres=float(((df["mean_ndvi"]-pred)**2).sum())
    sstot=float(((df["mean_ndvi"]-df["mean_ndvi"].mean())**2).sum())
    r2=1-ssres/sstot if sstot else np.nan
else: linear_slope=r2=np.nan

# ---------- tabs ----------
tab1,tab2,tab3,tab4=st.tabs(["🏞️ Overview","🛰️ NDVI Explorer","🔎 Change Detection","🗺️ LULC"])

with tab1:
    st.subheader("Kaziranga Overview")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Analysis start",start_year)
    c2.metric("Analysis end",end_year)
    c3.metric("Months",len(df))
    mean_ndvi=float(df["mean_ndvi"].mean()) if not df.empty else np.nan
    c4.metric("Long-term mean NDVI",f"{mean_ndvi:.3f}" if np.isfinite(mean_ndvi) else "N/A")
    st.caption("Only complete months are counted; the current incomplete month is excluded.")
    a,b,c,d=st.columns(4)
    a.metric("NDVI trend",trend_result["direction"])
    b.metric("Kendall τ",f'{trend_result["tau"]:.3f}' if np.isfinite(trend_result["tau"]) else "N/A")
    c.metric("Mann–Kendall p",f'{trend_result["p"]:.4f}' if np.isfinite(trend_result["p"]) else "N/A")
    d.metric("Sen slope / year",f"{sen:.5f}" if np.isfinite(sen) else "N/A")
    st.markdown("### Monthly NDVI overview")
    ndvi_time_series(df)
    annual_ndvi_chart(df)
    st.markdown("### Latest NDVI map")
    m=create_map(roi)
    latest=ndvi_collection.sort("system:time_start",False).first()
    add_ndvi_layer(m,latest,"Latest monthly NDVI")
    m.to_streamlit(height=560)

with tab2:
    st.subheader("NDVI Explorer")
    st.caption("Every complete monthly NDVI composite in the selected period is available as an interactive map layer.")
    if controls["show_all_monthly"]:
        with st.status(f"🗺️ Adding {len(df)} monthly NDVI layers…",expanded=False) as s:
            m=create_map(roi)
            for _,row in df.iterrows():
                # get image from deterministic year/month rather than client-side collection lookup
                img=monthly_ndvi(int(row.year),int(row.month),roi)
                add_ndvi_layer(m,img,f'{row["date"].strftime("%Y-%m")} | NDVI')
            s.update(label=f"✓ {len(df)} monthly NDVI layers loaded",state="complete")
        m.to_streamlit(height=700)
    else:
        st.info("Enable 'Show all monthly NDVI map layers' in the sidebar.")
    st.markdown("### NDVI statistics")
    ndvi_time_series(df)
    ndvi_statistics_chart(df)
    annual_ndvi_chart(df)
    st.dataframe(df[["date","year","month","mean_ndvi","median_ndvi","min_ndvi","max_ndvi","std_ndvi"]],use_container_width=True,hide_index=True)

with tab3:
    st.subheader("NDVI Change Detection")
    st.info("The start image is always the **first month (January) of the selected year**. The end image is the **last month in the selected date range**. The dashboard maps both endpoints and their pixel-wise difference.")
    selected_year=controls["selected_year"]
    start_img=monthly_ndvi(selected_year,1,roi)
    end_date=pd.Timestamp(controls.get("end_date",date.today()))
    end_month=end_date.month
    end_year_for_endpoint=end_date.year
    if end_date < pd.Timestamp(f"{selected_year}-01-01"):
        st.error("The change-detection range end must be on or after January of the selected year.")
        st.stop()
    # End endpoint is the last month contained in the selected date range.
    end_img=monthly_ndvi(end_year_for_endpoint,end_month,roi)
    change=image_difference(start_img,end_img,roi=roi)
    pct=percent_change(start_img,end_img,roi=roi)
    with st.status("🔎 Calculating endpoint and change statistics…",expanded=False) as s:
        stats=endpoint_stats(start_img,end_img,roi,controls["scale"]).getInfo()
        ch_stats=change.reduceRegion(
            ee.Reducer.mean().combine(ee.Reducer.median(),"",True)
            .combine(ee.Reducer.minMax(),"",True).combine(ee.Reducer.stdDev(),"",True),
            roi.geometry(),controls["scale"],maxPixels=1e13,bestEffort=True).getInfo()
        area_ha=ee.Image.pixelArea().divide(10000)
        gain_area=area_ha.updateMask(change.gt(0)).reduceRegion(
            ee.Reducer.sum(),roi.geometry(),controls["scale"],maxPixels=1e13,bestEffort=True).getInfo().get("area",0)
        loss_area=area_ha.updateMask(change.lt(0)).reduceRegion(
            ee.Reducer.sum(),roi.geometry(),controls["scale"],maxPixels=1e13,bestEffort=True).getInfo().get("area",0)
        s.update(label="Endpoint and change statistics ready",state="complete")
    start_mean=stats.get("start_ndvi_mean"); end_mean=stats.get("end_ndvi_mean")
    change_mean=(end_mean-start_mean) if start_mean is not None and end_mean is not None else None
    k1,k2,k3,k4=st.columns(4)
    k1.metric(f"Jan {selected_year}",f"{start_mean:.3f}" if start_mean is not None else "N/A")
    k2.metric(f"{end_month:02d}/{end_year_for_endpoint}",f"{end_mean:.3f}" if end_mean is not None else "N/A")
    k3.metric("Mean NDVI difference",f"{change_mean:+.3f}" if change_mean is not None else "N/A")
    k4.metric("Mean % change",f"{(change_mean/start_mean*100):+.2f}%" if start_mean not in (None,0) else "N/A")
    st.markdown("### Start • End • Difference")
    m=create_map(roi)
    add_ndvi_layer(m,start_img,f"START | Jan {selected_year}")
    add_ndvi_layer(m,end_img,f"END | {end_month:02d}/{selected_year}")
    add_change_layer(m,change,"DIFFERENCE | End − Start")
    m.addLayer(pct,{"min":-100,"max":100,"palette":["b2182b","f7f7f7","1b7837"]},"PERCENT CHANGE (%)")
    m.to_streamlit(height=700)
    st.markdown("### Endpoint values")
    ep=pd.DataFrame({"metric":[f"Jan {selected_year}",f"{end_month:02d}/{end_year_for_endpoint}"],"value":[start_mean,end_mean]})
    fig=px.bar(ep,x="metric",y="value",title="ROI mean NDVI at endpoints",labels={"value":"Mean NDVI","metric":""})
    st.plotly_chart(fig,use_container_width=True,key="change_endpoint_values")
    st.markdown("### Change statistics")
    change_table=pd.DataFrame({
        "Statistic":["Mean","Median","Minimum","Maximum","Std. deviation","Area increasing (ha)","Area decreasing (ha)"],
        "Value":[ch_stats.get("NDVI_change_mean"),ch_stats.get("NDVI_change_median"),
                 ch_stats.get("NDVI_change_min"),ch_stats.get("NDVI_change_max"),
                 ch_stats.get("NDVI_change_stdDev"),gain_area,loss_area]
    })
    st.dataframe(change_table,use_container_width=True,hide_index=True)
    st.markdown("### Long-term trend")
    st.caption("Trend statistics use the monthly ROI mean NDVI series. Mann–Kendall gives direction/significance; Sen's slope is a robust rate of change.")
    tc1,tc2,tc3,tc4=st.columns(4)
    tc1.metric("Direction",trend_result["direction"])
    tc2.metric("Kendall τ",f'{trend_result["tau"]:.3f}')
    tc3.metric("p-value",f'{trend_result["p"]:.4f}')
    tc4.metric("Sen slope",f'{sen:.5f} NDVI/year')
    trend_df=df[["date","mean_ndvi"]].copy()
    trend_df["linear_fit"]=np.polyval(coef,(trend_df["date"]-df["date"].min()).dt.days/365.25) if not np.isnan(linear_slope) else np.nan
    fig=px.scatter(trend_df,x="date",y="mean_ndvi",title=f"Monthly NDVI trend (R²={r2:.3f})",labels={"mean_ndvi":"Mean NDVI","date":"Date"})
    fig.add_scatter(x=trend_df["date"],y=trend_df["linear_fit"],mode="lines",name="Linear trend")
    st.plotly_chart(fig,use_container_width=True,key="change_trend_plot")

with tab4:
    st.subheader("LULC Explorer")
    st.caption("Dynamic World and ESRI are enabled by default. MODIS MCD12Q1 is also included for long-term context. Availability differs by product.")
    lulc_start=max(start_year,2006); lulc_end=end_year
    sources=[("Dynamic World",2015,dw_annual,DW_CLASSES,0,8),
             ("ESRI Global LULC",2017,esri_annual,ESRI_CLASSES,1,10),
             ("MODIS MCD12Q1",2006,modis_annual,MODIS_IGBP_CLASSES,1,17)]
    all_tables=[]
    progress=st.progress(0,"Preparing LULC statistics…")
    total=sum(max(0,lulc_end-max(lulc_start,s[1])+1) for s in sources)
    done=0
    for source,min_year,fn,names,vmin,vmax in sources:
        sy=max(lulc_start,min_year)
        if sy>lulc_end: continue
        rows=[]
        with st.expander(f"📊 {source} — annual area statistics",expanded=(source!="MODIS MCD12Q1")):
            for y in range(sy,lulc_end+1):
                try:
                    img=fn(y,roi,controls["confidence"]) if source=="Dynamic World" else fn(y,roi)
                    hist=ee.Image.pixelArea().divide(10000).addBands(img.rename("class")).reduceRegion(
                        ee.Reducer.sum().group(groupField=1,groupName="class"),
                        roi.geometry(),controls["scale"],maxPixels=1e13,bestEffort=True).get("groups").getInfo()
                    for g in (hist or []):
                        cl=int(g["class"]); area=float(g["sum"])
                        rows.append({"source":source,"year":y,"class":cl,"class_name":names.get(cl,f"Class {cl}"),"area_ha":area})
                except Exception as exc:
                    st.warning(f"{source} {y}: no usable image/statistics ({str(exc)[:120]})")
                done+=1
                progress.progress(min(done/max(total,1),1),f"Processed {source}: {y}")
            sdf=pd.DataFrame(rows)
            if not sdf.empty:
                lulc_area_over_time(sdf,f"{source}: annual class area")
                st.dataframe(sdf.pivot_table(index="year",columns="class_name",values="area_ha",aggfunc="sum").reset_index(),use_container_width=True,hide_index=True)
                all_tables.append(sdf)
                latest_year=int(sdf["year"].max())
                latest=sdf[sdf.year==latest_year].copy()
                lulc_area_chart(latest,f"{source}: {latest_year} total area by class")
                lm=create_map(roi)
                try:
                    img=fn(latest_year,roi,controls["confidence"]) if source=="Dynamic World" else fn(latest_year,roi)
                    add_lulc_layer(lm,img,f"{source} {latest_year}",vmax)
                    lm.to_streamlit(height=520)
                except Exception as exc: st.warning(f"Could not render {source} map: {exc}")
            else: st.info("No annual LULC statistics were returned for this source.")
    progress.empty()
    if all_tables:
        combined=pd.concat(all_tables,ignore_index=True)
        st.download_button("⬇️ Download combined LULC area table (CSV)",
                           combined.to_csv(index=False).encode("utf-8"),"kaziranga_lulc_area_statistics.csv","text/csv")
