import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
from PIL import Image

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Mis Gastos Personales", page_icon="🧾")
st.title("🧾 Escáner de Gastos")

# --- 1. AUTENTICACIÓN Y CONEXIÓN ---
# ID del Google Sheet (Extraído de tu link anterior)
SPREADSHEET_ID = "1_xAPWCdhLmUoEh9kZwcV60ldzZhvTmkSWOMEaTo0jjA"

try:
    # 1.1 Configurar Credenciales de Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Cargamos los secretos
    if "gcp_service_account" not in st.secrets:
        st.error("❌ No encuentro 'gcp_service_account' en los Secrets.")
        st.stop()
        
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    # --- CORRECCIÓN CRÍTICA DE LA LLAVE ---
    # A veces la llave privada pierde los saltos de línea al pegarse. Esto lo arregla.
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # 1.2 Abrir la hoja usando el ID (Más seguro que el nombre)
    sh = client.open_by_key(SPREADSHEET_ID)
    
    # Seleccionamos la PRIMERA pestaña, se llame como se llame
    sheet = sh.get_worksheet(0)

    # 1.3 Configurar Gemini AI
    if "general" in st.secrets and "gemini_api_key" in st.secrets["general"]:
        api_key = st.secrets["general"]["gemini_api_key"]
        genai.configure(api_key=api_key)
    else:
        st.error("❌ No encuentro la 'gemini_api_key' en los Secrets.")
        st.stop()
        
except Exception as e:
    st.error("⚠️ Error Crítico de Conexión.")
    st.write("Por favor, revisa lo siguiente:")
    st.markdown("- ¿Compartiste la hoja con el email del bot? (`client_email` en secrets)")
    st.markdown("- ¿El ID de la hoja es correcto?")
    st.code(f"Error detallado: {type(e).__name__}: {e}")
    st.stop()

# --- 2. INTERFAZ ---
st.success("✅ Conexión con Hoja de Cálculo exitosa") # Confirmación visual

tab1, tab2 = st.tabs(["📸 Cámara", "📂 Subir Archivo"])
img_file_buffer = None

with tab1:
    camera_image = st.camera_input("Tomar foto")
    if camera_image: img_file_buffer = camera_image

with tab2:
    uploaded_file = st.file_uploader("Cargar imagen", type=["jpg", "png", "jpeg"])
    if uploaded_file: img_file_buffer = uploaded_file

# --- 3. PROCESAMIENTO ---
if img_file_buffer:
    image = Image.open(img_file_buffer)
    st.image(image, caption="Ticket", width=300)
    
    if st.button("🔍 Procesar Gasto", type="primary"):
        with st.spinner("Leyendo ticket..."):
            try:
                model = genai.GenerativeModel('gemini-2.5-flash')
                prompt = """
                Analiza este recibo y extrae los datos en JSON puro:
                {
                    "fecha": "YYYY-MM-DD",
                    "comercio": "Nombre Comercio",
                    "total": 0.00,
                    "moneda": "MXN",
                    "categoria": "Alimentos/Transporte/Salud/Otros"
                }
                Si no hay fecha usa hoy. Total 0 si no se ve.
                """
                response = model.generate_content([prompt, image])
                text = response.text.replace("```json", "").replace("```", "").strip()
                data = json.loads(text)
                
                # Fila a guardar
                row = [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    data.get("fecha"),
                    data.get("comercio"),
                    data.get("categoria"),
                    data.get("total"),
                    data.get("moneda")
                ]
                
                sheet.append_row(row)
                st.balloons()
                st.success(f"¡Guardado! ${data.get('total')} en {data.get('comercio')}")
                
            except Exception as e:
                st.error("Error al procesar.")
                st.write(e)

# --- 4. VERIFICACIÓN DE DATOS ---
st.divider()
try:
    records = sheet.get_all_records()
    if records:
        st.write(f"📊 Últimos gastos (Total registros: {len(records)})")
        st.dataframe(records[-5:])
    else:
        st.info("La hoja está conectada pero vacía.")
except Exception as e:
    st.warning("No se pudieron leer los registros (¿Fila 1 tiene encabezados?)")
