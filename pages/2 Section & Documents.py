import streamlit as st  # pip install streamlit=1.12.0
import pandas as pd
from st_aggrid import GridOptionsBuilder, AgGrid, GridUpdateMode, JsCode # pip install streamlit-aggrid==0.2.3

import sqlite3
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
    connection = pymysql.connect(host=endpoint, user=user, password=password, db=db)
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

    sql = '''DELETE FROM section WHERE section_hashkey=%s'''
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

    sql = 'DELETE FROM document WHERE document_hashkey=%s'

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
    
    sql = 'UPDATE section SET seq=%s, section_name=%s WHERE section_hashkey=%s'

    cursor.execute(sql, (seq, section_name, section_hashkey,))
    connection.commit()
    cursor.close()
    connection.close()


def edit_document(document_hashkey, seq, doc_name):
    connection = pymysql.connect(host=endpoint, user=user, password=password, db=db)
    cursor = connection.cursor()
    
    sql = 'UPDATE document SET doc_name=%s, seq=? WHERE document_hashkey=%s'

    cursor.execute(sql, (doc_name, seq, document_hashkey,))
    connection.commit()
    cursor.close()
    connection.close()

def move_document(to_section_hashkey, document_hashkey):
    connection = pymysql.connect(host=endpoint, user=user, password=password, db=db)
    cursor = connection.cursor()
    
    sql = 'UPDATE document SET section_hashkey=%s WHERE document_hashkey=%s'

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

    sql = '''insert into document(file_hashkey, document_hashkey, section_hashkey, seq, doc_name, doc_page, date) values (%s,%s,%s,%s,%s,%s,%s)'''
    val = (file_hashkey, document_hashkey, section_hashkey, seq, doc_name, doc_page, now)

    cursor.execute(sql,val)

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


#Set default section_hashkey
section_hashkey = None

file_df = data()[['file_no','file_hashkey',]]

values = file_df['file_no'].tolist()
options = file_df['file_hashkey'].tolist()
dic = dict(zip(options, values))

file_hashkey = st.selectbox("Select File",options, format_func=lambda x: dic[x])


col1, colbreak, col2, colbreak2, col3 = st.columns([7,1,7,1,7])



with col1:

    section_manageTab, section_guideTab= st.tabs(["Manage", "Guide"])

    with section_manageTab:
        st.header('Section Management')
        section_data = get_section(file_hashkey)
        exposed_table = section_data[['seq','section_name','date']]
        lseq = len(section_data)

        gd = GridOptionsBuilder.from_dataframe(exposed_table)
        gd.configure_default_column(rowDrag = False, rowDragManaged = True, rowDragEntireRow = True, rowDragMultiRow=True, cellStyle= cellstyle_jscode)
        gd.configure_default_column(editable=False)
        gd.configure_selection(selection_mode="single", use_checkbox=True)
        gridOptions = gd.build()

        grid_section = AgGrid(section_data,
                gridOptions=gridOptions,
                allow_unsafe_jscode=True,
                update_mode=GridUpdateMode.MANUAL
        )


        sel_section = grid_section["selected_rows"]
        sel_section = pd.DataFrame(sel_section)

        for key,value in sel_section.iterrows():
            section_hashkey = value['section_hashkey']
            section_name = value['section_name']
            seq = value['seq']


        if len(sel_section) == 1:
            with st.expander("Update Section"):
                with st.form("update_section", clear_on_submit=True):
                    st.caption("Selected Section: " + section_name)

                    section_seq = st.text_input('Sequence', seq)
                    section_name = st.text_input('Section Name',section_name)
                    update_section = st.form_submit_button("Update Section")
                    
                    if update_section:
                        edit_section(section_hashkey,section_seq,section_name)
                        st.write('Section Updated')
                        st.session_state['key'] == 'updated'
                        st.experimental_rerun()


            with st.expander("Delete Section"):
                st.caption('Confirm deletion of Section ' + section_name)
                st.caption('This will delete all documents linked to this section')
                st.caption('You are unable to undo this action')
                if st.button('Delete selected section'):
                    delete_section(section_hashkey)
                    st.write('Case Deleted')
                    st.session_state['key'] == 'deleted'
                    st.experimental_rerun()

            with st.expander("Upload document"):
                with st.form("Upload_document",clear_on_submit=True):
                    upload_file = st.file_uploader('Select PDF files to upload', accept_multiple_files=True, type="pdf")
                    upload_submit = st.form_submit_button("Upload")

                    document_data = get_document(section_hashkey)

                    lseq = len(document_data) +1

                    if upload_submit and upload_file is not None:
                        for pdf in upload_file:
                            doc_page = PyPDF2.PdfReader(pdf)
                            doc_page = len(doc_page.pages)
                            pdf.seek(0)
                            upload_document(file_hashkey, section_hashkey, lseq, pdf.name, doc_page, pdf)
                            lseq = lseq + 1




with col2:

    doc_manageTab, doc_arrangeTab= st.tabs(["Manage", "Arrange"])

    with doc_manageTab:
        st.header('Document Management - Manage')
        document_data = get_document(section_hashkey)
        exposed_table = document_data[['seq','doc_name', 'doc_page','date']]
        lseq = len(section_data)

        gd = GridOptionsBuilder.from_dataframe(exposed_table)
        gd.configure_default_column(rowDrag = False, rowDragManaged = True, rowDragEntireRow = True, rowDragMultiRow=True, cellStyle= cellstyle_jscode)
        gd.configure_default_column(editable=False)
        gd.configure_selection(selection_mode="single", use_checkbox=True)
        gridOptions = gd.build()

        grid_document = AgGrid(document_data,
                gridOptions=gridOptions,
                allow_unsafe_jscode=True,
                update_mode=GridUpdateMode.MANUAL
        )

        sel_document = grid_document["selected_rows"]
        sel_document = pd.DataFrame(sel_document)

        for key,value in sel_document.iterrows():
            document_hashkey = value['document_hashkey']
            #st.caption(document_hashkey)
        
        if len(sel_document) == 1 :

            with st.expander("Move Document"):
                with st.form("move_doucment", clear_on_submit=True):
                    st.caption("From Section: " + section_name)

                    available_section = get_section(file_hashkey)[['section_hashkey','section_name']]
                    section_list = available_section['section_name'].to_list()
                    #st.write(section_list)

                    #from_section = st.text_input('From Section' ,section_name)
                    to_section = st.selectbox('To section',section_list)
                    btn_move_document = st.form_submit_button("Move Document")
                    
                    to_section_hashkey = available_section[available_section['section_name'] == to_section]['section_hashkey'].iloc[0]

                    if btn_move_document:
                        move_document(to_section_hashkey, document_hashkey)
                        st.write('Document Moved ')
                        st.session_state['key'] == 'updated'
                        st.experimental_rerun()

                #pending development
            with st.expander("Delete Document"):
                if st.button('Delete Document'):
                    delete_document(document_hashkey)
                    time.sleep(1)
                    st.experimental_rerun()

    
    with doc_arrangeTab:

        st.header('Document Management - Arrange')
        document_data = get_document(section_hashkey)
        exposed_table = document_data[['seq','doc_name','doc_page']]

        gb = GridOptionsBuilder.from_dataframe(exposed_table)
        gb.configure_default_column(rowDrag = False, rowDragManaged = True, rowDragEntireRow = True, rowDragMultiRow=True, cellStyle= cellstyle_jscode)
        gb.configure_default_column(editable=False)
        gb.configure_column('seq',rowDrag = True, rowDragEntireRow = True)
        gb.configure_grid_options(rowDragManaged = True, onRowDragEnd = onRowDragEnd, deltaRowDataMode = True, getRowNodeId = getRowNodeId, onGridReady = onGridReady, animateRows = True, onRowDragMove = onRowDragMove)
        gridOptions = gb.build()

        grid_document2 = AgGrid(document_data,
                    gridOptions=gridOptions,
                    allow_unsafe_jscode=True,
                    update_mode=GridUpdateMode.MANUAL
        )


        update_doc_table = grid_document2['data']
        update_doc_table.seq = range(1, 1 + len(update_doc_table))

        if st.button('Commit Changes'):

            for key,value in update_doc_table.iterrows():
                document_hashkey = (value['document_hashkey'])
                seq = int(value['seq'])
                doc_name = value['doc_name']

                edit_document(document_hashkey,seq,doc_name)
            st.header('Database Updated')
            time.sleep(2)
            st.experimental_rerun()


with col3:

    doc_previewTab, doc_actionTab= st.tabs(["Preview", "Action"])

    with doc_previewTab:

        st.header("Display Document PDF")

        if len(sel_document) == 1 :
            
            s3 = boto3.client(
                service_name="s3",
                region_name=myregion,
                aws_access_key_id=myaccesskey,
                aws_secret_access_key=mysecretkey
            )
            fileobj = s3.get_object(
                Bucket='aws-bundlepdf',
                Key=document_hashkey+'.pdf'
                ) 
            filedata = fileobj['Body'].read()
                
            base64_pdf = base64.b64encode(filedata).decode('utf-8')
            pdf_display = F'<embed src="data:application/pdf;base64,{base64_pdf}" width="650" height="800" type="application/pdf"></embed>'
            st.markdown(pdf_display, unsafe_allow_html=True)