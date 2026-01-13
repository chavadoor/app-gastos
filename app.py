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
st.write("Sube una foto o toma una captura de tu ticket.")

# --- 1. CONFIGURACIÓN DE CREDENCIALES (SECRETS) ---
# Usamos gspread porque es compatible con los secrets que ya configuraste
try:
    # Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    SHEET_NAME = st.secrets["sheets"]["sheet_name"]
    sheet = client.open(SHEET_NAME).sheet1

    # Gemini AI
    GENAI_API_KEY = st.secrets["general"]["gemini_api_key"]
    genai.configure(api_key=GENAI_API_KEY)
    
except Exception as e:
    st.error("⚠️ Error de configuración. Verifica que el nombre de la hoja en 'secrets' coincida con tu Google Sheet.")
    st.error(f"Detalle técnico: {e}")
    st.stop()

# --- 2. INTERFAZ DE CAPTURA ---
tab1, tab2 = st.tabs(["📸 Cámara", "📂 Subir Archivo"])
img_file_buffer = None

with tab1:
    camera_image = st.camera_input("Tomar foto del ticket")
    if camera_image:
        img_file_buffer = camera_image

with tab2:
    uploaded_file = st.file_uploader("Cargar imagen", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        img_file_buffer = uploaded_file

# --- 3. PROCESAMIENTO ---
if img_file_buffer is not None:
    image = Image.open(img_file_buffer)
    st.image(image, caption="Ticket Capturado", width=300)

    if st.button("🔍 Analizar y Guardar", type="primary"):
        with st.spinner("Auditando ticket con IA..."):
            try:
                # Usamos Gemini Flash por rapidez
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                prompt = """
                Analiza este recibo. Extrae información y responde SOLAMENTE con un JSON:
                {
                    "fecha": "YYYY-MM-DD",
                    "comercio": "Nombre del lugar",
                    "total": 0.00,
                    "moneda": "MXN",
                    "categoria": "Alimentos" (Opciones: Alimentos, Transporte, Salud, Otros)
                }
                Si no encuentras fecha usa la de hoy. Si no encuentras total pon 0.
                """
                
                response = model.generate_content([prompt, image])
                text = response.text.strip()
                
                # Limpieza de formato Markdown
                if text.startswith("```json"):
                    text = text[7:]
                if text.endswith("```"):
                    text = text[:-3]
                
                data = json.loads(text)
                
                # --- GUARDAR EN SHEETS ---
                nueva_fila = [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), # A: Fecha Registro
                    data.get("fecha", datetime.now().strftime("%Y-%m-%d")), # B: Fecha Ticket
                    data.get("comercio", "Desconocido"), # C: Comercio
                    data.get("categoria", "Otros"), # D: Categoría
                    data.get("total", 0.0), # E: Total
                    data.get("moneda", "MXN") # F: Moneda
                ]
                
                sheet.append_row(nueva_fila)
                
                st.balloons()
                st.success("✅ ¡Gasto registrado correctamente!")
                st.json(data)
                
            except Exception as e:
                st.error("Error al procesar. Intenta tomar la foto más clara.")
                st.error(f"Error técnico: {e}")

# --- 4. VISUALIZACIÓN ---
st.divider()
st.subheader("📊 Últimos movimientos")
try:
    registros = sheet.get_all_records()
    if registros:
        # Mostramos los últimos 5 registros
        st.dataframe(registros[-5:])
    else:
        st.info("La hoja está vacía por ahora.")
except:
    st.warning("No se pudieron leer los registros anteriores (¿La hoja tiene encabezados en la fila 1?)")
