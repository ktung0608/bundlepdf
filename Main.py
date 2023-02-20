import streamlit as st  # pip install streamlit=1.12.0
import pandas as pd
from st_aggrid import GridOptionsBuilder, AgGrid, GridUpdateMode, JsCode # pip install streamlit-aggrid==0.2.3
import streamlit_authenticator as stauth
import yaml
from yaml import SafeLoader
import time
import boto3

st.set_page_config(
    page_title="Multipage App",
    page_icon="👋")


st.write("Login Page - Non Functioning")

with st.form('Login', clear_on_submit=True):
    st.text_input('Login / Username')
    st.text_input('Password')
    login_submit = st.form_submit_button("Login")

    if login_submit:
        st.write("logged in")
        time.sleep(1)
        st.experimental_rerun()

