import streamlit as st  # pip install streamlit=1.12.0
import pandas as pd
from st_aggrid import GridOptionsBuilder, AgGrid, GridUpdateMode, JsCode # pip install streamlit-aggrid==0.2.3

import time
import hashlib
import boto3
from datetime import datetime
import PyPDF2
import base64
import pymysql

st.session_state['key'] = 'blank'

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


cellstyle_jscode = JsCode("""
    function(params){
        if (params.value =='s') {
            return {
                'backgroundColor' : 'orange'
            }
        }
    }
""")

st. set_page_config(layout="wide")

endpoint = st.secrets.db_credentials.endpoint
user = st.secrets.db_credentials.user
password = st.secrets.db_credentials.password
db = st.secrets.db_credentials.db

myregion=st.secrets.s3_credentials.myregion
myaccesskey=st.secrets.s3_credentials.myaccesskey
mysecretkey=st.secrets.s3_credentials.mysecretkey

def data():
    connection = pymysql.connect(host=endpoint, user=user, password=password,db=db)
    cursor = connection.cursor()

    file_data = pd.read_sql_query("SELECT * FROM file", connection)
    cursor.close()
    connection.close()
    return file_data

def get_section(file_hashkey):
    connection = pymysql.connect(host=endpoint, user=user, password=password, db=db)
    cursor = connection.cursor()

    sql = '''SELECT * FROM section WHERE file_hashkey =%s ORDER by seq ASC'''
    val = (file_hashkey,)

    section_data = pd.read_sql_query("SELECT * FROM section WHERE file_hashkey =%s ORDER by seq ASC", connection, params=(file_hashkey,))
    cursor.close()
    connection.close()
    return section_data

def get_document(section_hashkey):
    connection = pymysql.connect(host=endpoint, user=user, password=password, db=db)
    cursor = connection.cursor()
    document_data = pd.read_sql_query("SELECT * FROM document WHERE section_hashkey =%s ORDER BY seq ASC", connection, params=(section_hashkey,))
    cursor.close()
    connection.close()
    return document_data


def create_file(file_no, client,handled_by):

    now = datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    
    x = file_no + dt_string

    file_hashkey = hashlib.md5(x.encode()).hexdigest()
    connection = pymysql.connect(host=endpoint, user=user, password=password, db=db)
    cursor = connection.cursor()

    sql = '''
    insert into file (file_hashkey, file_no, client, handled_by, date) values('%s', '%s', '%s', '%s', '%s')''' % (file_hashkey, file_no, client, handled_by, now)

    cursor.execute(sql)

    connection.commit()
    cursor.close()
    connection.close()


def create_section(file_hashkey,section_name,lseq):

    now = datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    section_hashkey = section_name+str(dt_string)
    section_hashkey = hashlib.md5(section_hashkey.encode()).hexdigest()

    connection = pymysql.connect(host=endpoint, user=user, password=password, db=db)
    cursor = connection.cursor()


    sql = '''insert into section (file_hashkey, section_hashkey, seq, section_name, date) values (%s, %s, %s, %s,%s)'''
    val = (file_hashkey, section_hashkey, lseq + 1, section_name, now)
    
    cursor.execute(sql,val)
    connection.commit()
    cursor.close()
    connection.close()


def delete_file(file_hashkey):
    connection = pymysql.connect(host=endpoint, user=user, password=password, db=db)
    cursor = connection.cursor()

    sql = '''DELETE FROM file WHERE file_hashkey=%s'''
    cursor.execute(sql, (file_hashkey,))
    connection.commit()
    
    #Delete all section linked to file
    try:
        sql = '''DELETE FROM section WHERE file_hashkey=%s'''
        cursor.execute(sql, (file_hashkey,))
        connection.commit()
    except:
        pass

    #Delete all document linked to file
    try:
        sql = '''DELETE FROM document WHERE file_hashkey=%s'''
        cursor.execute(sql, (file_hashkey,))
        connection.commit()
    except:
        pass

    cursor.close()
    connection.close()


def delete_section(section_hashkey):
    connection = pymysql.connect(host=endpoint, user=user, password=password, db=db)
    cursor = connection.cursor()

    sql = 'DELETE FROM section WHERE section_hashkey=?'
    cursor.execute(sql, (section_hashkey,))
    connection.commit()
    
    #Delete all document linked to file
    try:
        sql = '''DELETE FROM document WHERE section_hashkey=%s'''
        cursor.execute(sql, (section_hashkey,))
        connection.commit()
    except:
        pass

    cursor.close()
    connection.close()


def delete_document(document_hashkey):
    connection = pymysql.connect(host=endpoint, user=user, password=password, db=db)
    cursor = connection.cursor()

    sql = 'DELETE FROM document WHERE document_hashkey=?'

    cursor.execute(sql, (document_hashkey,))
    connection.commit()
    cursor.close()
    connection.close()
    
    s3 = boto3.client(
        service_name="s3",
        region_name=myregion,
        aws_access_key_id=myaccesskey,
        aws_secret_access_key=mysecretkey
    )
    s3.delete_object(Bucket='aws-bundlepdf', Key=document_hashkey+".pdf")


def edit_file(file_no, client, handled_by):
    connection = pymysql.connect(host=endpoint, user=user, password=password, db=db)
    cursor = connection.cursor()

    sql = 'UPDATE file SET client=%s, handled_by=%s WHERE file_hashkey=%s'
    val = (client, handled_by, file_hashkey,)
    cursor.execute(sql, val)
    connection.commit()
    cursor.close()
    connection.close()

def edit_section(section_hashkey,seq,section_name):
    connection = pymysql.connect(host=endpoint, user=user, password=password, db=db)
    cursor = connection.cursor()
    sql = 'UPDATE section SET seq=?, section_name=? WHERE section_hashkey=?'

    cursor.execute(sql, (seq, section_name, section_hashkey,))
    connection.commit()
    cursor.close()
    connection.close()


def edit_document(document_hashkey, seq, doc_name):
    connection = pymysql.connect(host=endpoint, user=user, password=password, db=db)
    cursor = connection.cursor()
    
    sql = 'UPDATE document SET doc_name=?, seq=? WHERE document_hashkey=?'

    cursor.execute(sql, (doc_name, seq, document_hashkey,))
    connection.commit()
    cursor.close()
    connection.close()

def move_document(to_section_hashkey, document_hashkey):
    connection = pymysql.connect(host=endpoint, user=user, password=password, db=db)
    cursor = connection.cursor()

    sql = 'UPDATE document SET section_hashkey=? WHERE document_hashkey=?'

    cursor.execute(sql, (to_section_hashkey, document_hashkey,))
    connection.commit()
    cursor.close()
    connection.close()


def upload_document(file_hashkey, section_hashkey, seq, doc_name, doc_page, pdf):

    now = datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    document_hashkey = doc_name+str(dt_string)
    document_hashkey = hashlib.md5(document_hashkey.encode()).hexdigest()

    connection = pymysql.connect(host=endpoint, user=user, password=password, db=db)
    cursor = connection.cursor()
    
    cursor.execute("insert into document(file_hashkey, document_hashkey, section_hashkey, seq, doc_name, doc_page, date) values (?, ?, ?, ?, ?, ?, ?)",
        (file_hashkey, document_hashkey, section_hashkey, seq, doc_name, doc_page,dt_string))

    connection.commit()
    cursor.close()
    connection.close()

    s3 = boto3.client(
        service_name="s3",
        region_name=myregion,
        aws_access_key_id=myaccesskey,
        aws_secret_access_key=mysecretkey
    )

    bucket_name = "aws-bundlepdf"

    s3.upload_fileobj(pdf, "aws-bundlepdf", document_hashkey + ".pdf", ExtraArgs={'ContentType': "application/pdf"})



col1, colbreak, col2, colbreak2, col3 = st.columns([7,1,7,1,7])

with col2:
    st.header('File Management')

    data = data()
    gd = GridOptionsBuilder.from_dataframe(data)
    gd.configure_pagination(enabled=True)
    gd.configure_default_column(editable=True, groupable=True, rowDrag = False, rowDragManaged = True, rowDragEntireRow = True, rowDragMultiRow=True, cellStyle=cellstyle_jscode)    
    gd.configure_selection(selection_mode="single", use_checkbox=True)
    gridoptions = gd.build()
    grid_table = AgGrid(
        data,
        gridOptions=gridoptions,
        allow_unsafe_jscode=True,
        update_mode=GridUpdateMode.MANUAL
    )

    sel_file = grid_table["selected_rows"]
    sel_file = pd.DataFrame(sel_file)
    #st.write(df_sel_row)

    for key,value in sel_file.iterrows():
        file_hashkey = value['file_hashkey']
        file_no = value['file_no']
        client = value['client']
        handled_by = value['handled_by']

#Create New File
    if len(sel_file) == 0:
        with st.expander("Create"):
            with st.form("create_form", clear_on_submit=True):
                st.write("Create a New File")
                file_no = st.text_input('File No')
                client = st.text_input('Client')
                handled_by = st.selectbox('Handled By',['Lester','Katerina','Mr Lee']) 
                            # Every form must have a submit button.
                submitted = st.form_submit_button("Submit")
                if submitted:
                    create_file(file_no, client, handled_by)
                    st.header('New Case Created')
                    time.sleep(2)
                    st.session_state['key'] == 'created'
                    st.experimental_rerun()


    if len(sel_file) == 1:
        with st.expander("Update File"):
            with st.form("update_file", clear_on_submit=True):
                st.write("Edit Case Record: " + file_no)

                client = st.text_input('Client',client)
                handled_by = st.text_input('Handled By',handled_by)

                update_case = st.form_submit_button("Update")
                
                if update_case:
                    edit_file(file_no, client, handled_by)
                    st.write('File Updated')
                    st.session_state['key'] == 'updated'
                    st.experimental_rerun()


        with st.expander("Delete File"):
            st.write('Confirm deletion of Case ' + file_no + " by " + handled_by)
            st.write('This will delete all section and documents linked to file number')
            st.write('You are unable to undo this action')
            if st.button('Confirm deletion'):
                delete_file(file_hashkey)
                st.write('Case Deleted')
                st.session_state['key'] == 'deleted'
                st.experimental_rerun()

        with st.expander("Create Section"):
            with st.form("create_section", clear_on_submit=True):
                st.write("Create Section in " + file_no)

                section_name = st.text_input('Section Name')

                btn_create_section = st.form_submit_button("Create Section")
                
                if btn_create_section:
                    lseq = get_section(file_hashkey)
                    lseq = len(lseq)


                    create_section(file_hashkey, section_name, lseq)
                    st.write('Section Created')
                    st.session_state['key'] == 'updated'
                    st.experimental_rerun()


