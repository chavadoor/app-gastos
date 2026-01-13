import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from PIL import Image

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Mis Gastos", page_icon="🧾")
st.title("🧾 Escáner de Gastos")

# --- 1. CONEXIÓN (ID FIJO) ---
SPREADSHEET_ID = "1_xAPWCdhLmUoEh9kZwcV60ldzZhvTmkSWOMEaTo0jjA"

try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    if "gcp_service_account" not in st.secrets:
        st.error("❌ Error: Faltan los Secrets de gcp_service_account")
        st.stop()
        
    creds_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # Abrimos por ID para no fallar
    sh = client.open_by_key(SPREADSHEET_ID)
    sheet = sh.get_worksheet(0) # Primera hoja

    if "general" in st.secrets:
        genai.configure(api_key=st.secrets["general"]["gemini_api_key"])
        
except Exception as e:
    st.error("⚠️ Error de Conexión.")
    st.write(e)
    st.stop()

# --- 2. INTERFAZ ---
tab1, tab2 = st.tabs(["📸 Cámara", "📂 Subir Archivo"])
img_file_buffer = None

with tab1:
    cam = st.camera_input("Tomar foto")
    if cam: img_file_buffer = cam

with tab2:
    upl = st.file_uploader("Subir imagen", type=["jpg", "png", "jpeg"])
    if upl: img_file_buffer = upl

# --- 3. PROCESAMIENTO ---
if img_file_buffer:
    image = Image.open(img_file_buffer)
    st.image(image, width=200)
    
    if st.button("Procesar Ticket", type="primary"):
        with st.spinner("Leyendo datos..."):
            try:
                model = genai.GenerativeModel('gemini-2.5-flash')
                prompt = """
                Extrae datos de este ticket en JSON puro:
                {
                    "fecha": "YYYY-MM-DD",
                    "comercio": "Nombre del negocio",
                    "total": 0.00,
                    "moneda": "MXN",
                    "categoria": "Alimentos/Transporte/Salud/Otros"
                }
                """
                response = model.generate_content([prompt, image])
                text = response.text.replace("```json", "").replace("```", "").strip()
                data = json.loads(text)
                
                # --- MAPEO DE COLUMNAS (AQUÍ ESTABA EL ERROR) ---
                # Ajusta este orden según tus columnas en Excel (A, B, C, D, E)
                
                row = [
                    data.get("fecha"),        # Columna A: Fecha del Ticket
                    data.get("comercio"),     # Columna B: Comercio
                    data.get("categoria"),    # Columna C: Categoría
                    data.get("total"),        # Columna D: Total
                    data.get("moneda")        # Columna E: Moneda
                ]
                
                sheet.append_row(row)
                st.balloons()
                st.success("✅ Guardado correctamente")
                
                # Mostrar lo que se guardó
                st.write(f"**Fecha:** {data.get('fecha')}")
                st.write(f"**Comercio:** {data.get('comercio')}")
                st.write(f"**Total:** ${data.get('total')}")
                
            except Exception as e:
                st.error("Error al leer el ticket.")
                st.write(e)
