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
# Intentamos obtener las claves desde los 'Secrets' de Streamlit
try:
    # Configuración de Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Creamos el diccionario de credenciales desde los secrets
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # Abrimos la hoja de cálculo (Asegúrate de compartirla con el email del bot)
    SHEET_NAME = st.secrets["sheets"]["sheet_name"]
    sheet = client.open(SHEET_NAME).sheet1

    # Configuración de Gemini AI
    GENAI_API_KEY = st.secrets["general"]["gemini_api_key"]
    genai.configure(api_key=GENAI_API_KEY)
    
except Exception as e:
    st.error("⚠️ Error de configuración. Verifica tus 'Secrets' en Streamlit.")
    st.error(f"Detalle: {e}")
    st.stop()

# --- 2. INTERFAZ DE CAPTURA ---
# Pestañas para elegir entre cámara o subir archivo
tab1, tab2 = st.tabs(["📸 Cámara", "📂 Subir Archivo"])

img_file_buffer = None

with tab1:
    camera_image = st.camera_input("Tomar foto del ticket")
    if camera_image:
        img_file_buffer = camera_image

with tab2:
    uploaded_file = st.file_uploader("Cargar imagen del ticket", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        img_file_buffer = uploaded_file

# --- 3. PROCESAMIENTO CON IA ---
if img_file_buffer is not None:
    # Mostrar la imagen
    image = Image.open(img_file_buffer)
    st.image(image, caption="Ticket Capturado", width=300)

    if st.button("🔍 Analizar y Guardar Gasto", type="primary"):
        with st.spinner("La IA está leyendo el ticket..."):
            try:
                # Preparamos el modelo Gemini 2.5 Flash (rápido y económico)
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                # Prompt para la IA: Le pedimos JSON puro
                prompt = """
                Analiza esta imagen de un recibo de compra.
                Extrae la siguiente información y entrégala EXCLUSIVAMENTE en formato JSON:
                {
                    "fecha": "YYYY-MM-DD", (si no hay año, usa el actual)
                    "comercio": "Nombre del lugar",
                    "total": 00.00 (número decimal),
                    "moneda": "MXN" o la que aparezca,
                    "categoria": "Alimentos, Transporte, Salud, Otros" (infiere la categoría según los items)
                }
                Si no encuentras algún dato, usa null. No escribas nada más que el JSON.
                """
                
                response = model.generate_content([prompt, image])
                
                # Limpiamos la respuesta para obtener solo el JSON
                text_response = response.text.strip()
                # A veces la IA pone ```json ... ```, lo quitamos
                if text_response.startswith("```json"):
                    text_response = text_response[7:-3]
                elif text_response.startswith("```"):
                    text_response = text_response[3:-3]
                
                data = json.loads(text_response)
                
                # Mostrar datos detectados para confirmar
                st.success("✅ Datos extraídos:")
                st.json(data)
                
                # --- 4. GUARDAR EN GOOGLE SHEETS ---
                # Preparamos la fila: Fecha Registro, Fecha Ticket, Comercio, Categoría, Total, Moneda
                row = [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), # Fecha de carga
                    data.get("fecha", ""),
                    data.get("comercio", ""),
                    data.get("categoria", ""),
                    data.get("total", 0),
                    data.get("moneda", "MXN")
                ]
                
                sheet.append_row(row)
                st.balloons()
                st.success(f"¡Gasto de ${data.get('total')} guardado en Google Sheets!")
                
            except Exception as e:
                st.error("Ocurrió un error al procesar el ticket.")
                st.error(f"Error: {e}")

# --- 5. MOSTRAR ÚLTIMOS GASTOS ---
st.divider()
st.subheader("📊 Últimos 5 gastos registrados")
try:
    # Obtenemos todos los registros y mostramos los últimos 5
    all_records = sheet.get_all_records()
    if all_records:
        st.dataframe(all_records[-5:])
    else:
        st.info("Aún no hay gastos registrados.")
except:
    st.info("Conecta tu Google Sheet para ver los registros.")
