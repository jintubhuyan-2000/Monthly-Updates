"""Earth Engine initialization helpers."""

import ee
import streamlit as st
from config import GEE_PROJECT


def initialize_ee() -> None:
    """Initialize Earth Engine for the configured Google Cloud project."""
    try:
        ee.Initialize(project=GEE_PROJECT)
    except Exception:
        st.warning(
            "Earth Engine is not authenticated in this environment. "
            "Run `earthengine authenticate` once, or provide a service-account "
            "credential in your deployment environment."
        )
        ee.Authenticate()
        ee.Initialize(project=GEE_PROJECT)
