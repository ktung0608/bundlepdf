import streamlit as st  # pip install streamlit=1.12.0
import pandas as pd
from st_aggrid import GridOptionsBuilder, AgGrid, GridUpdateMode, JsCode # pip install streamlit-aggrid==0.2.3
import streamlit_authenticator as stauth
import yaml
from yaml import SafeLoader
import sqlite3

st.set_page_config(
    page_title="Multipage App",
    page_icon="👋",
)

onRowDragEnd = JsCode("""
function onRowDragEnd(e) {
    console.log('onRowDragEnd', e);
}
""")

getRowNodeId = JsCode("""
function getRowNodeId(data) {
    return data.id
}
""")

onGridReady = JsCode("""
function onGridReady() {
    immutableStore.forEach(
        function(data, index) {
            data.id = index;
            });
    gridOptions.api.setRowData(immutableStore);
    }
""")

onRowDragMove = JsCode("""
function onRowDragMove(event) {
    var movingNode = event.node;
    var overNode = event.overNode;

    var rowNeedsToMove = movingNode !== overNode;

    if (rowNeedsToMove) {
        var movingData = movingNode.data;
        var overData = overNode.data;

        immutableStore = newStore;

        var fromIndex = immutableStore.indexOf(movingData);
        var toIndex = immutableStore.indexOf(overData);

        var newStore = immutableStore.slice();
        moveInArray(newStore, fromIndex, toIndex);

        immutableStore = newStore;
        gridOptions.api.setRowData(newStore);

        gridOptions.api.clearFocusedCell();
    }

    function moveInArray(arr, fromIndex, toIndex) {
        var element = arr[fromIndex];
        arr.splice(fromIndex, 1);
        arr.splice(toIndex, 0, element);
    }
}
""")

def get_caselist():
    connection = sqlite3.connect("/Users/kenny/Desktop/streamlit_bundle/data/file.db")
    cursor = connection.cursor()
    df1 = pd.read_sql_query("SELECT DISTINCT(case_no) FROM file",connection )
    df1 = df1['case_no'].values.tolist()
    cursor.close()
    connection.close()

    return df1

def get_sectionlist(case_no):
    connection = sqlite3.connect("/Users/kenny/Desktop/streamlit_bundle/data/file.db")
    cursor = connection.cursor()

    df1 = pd.read_sql_query("SELECT * from sections where case_no =?", connection, params=(case_no,))
    cursor.close()
    connection.close()
    return df1


def get_documents(section):
    connection = sqlite3.connect("/Users/kenny/Desktop/streamlit_bundle/data/file.db")
    cursor = connection.cursor()
    df1 = pd.read_sql_query("SELECT * FROM documents WHERE section_hashkey =? ORDER BY seq ASC", connection, params=(section,))
    cursor.close()
    connection.close()
    return df1

def get_all_documents(case_no):
    connection = sqlite3.connect("/Users/kenny/Desktop/streamlit_bundle/data/file.db")
    cursor = connection.cursor()

    sql = "WITH tbl1 as (SELECT * FROM sections where case_no = ? order by seq ASC),  tbl2 as (SELECT * from documents) select tbl1.seq as seq1, tbl1.section_name, tbl2.doc_name, tbl2.doc_pages from tbl2 inner join tbl1 on tbl1.pk_hashkey = tbl2.section_hashkey"

    df1 = pd.read_sql_query(sql, connection, params=(case_no,))
    cursor.close()
    connection.close()
    return df1


case_no = st.selectbox('Select Case', get_caselist())

st.write('Assume page 1 is cover, page 2 is content page')

section_tbl  = get_sectionlist(case_no)

document_tbl = get_all_documents(case_no)

document_tbl['end'] = document_tbl['doc_pages'].cumsum() + 2

document_tbl['start'] = document_tbl['end'] - document_tbl['doc_pages'] + 1

document_tbl['pages'] = document_tbl['start'].astype(str) + " - " + document_tbl['end'].astype(str)

st.write(document_tbl[['section_name', 'doc_name', 'doc_pages', 'pages']])