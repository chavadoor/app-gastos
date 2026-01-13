import streamlit as st
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
import pandas as pd
import json
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Mi Escáner de Gastos", page_icon="🧾")
st.title("🧾 Escáner de Recibos IA")

# --- 1. CONEXIÓN CON SERVICIOS ---
# Intentamos conectar con Google Sheets y Gemini usando los "Secretos" de Streamlit
try:
    # Conexión a Google Sheets
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Conexión a Gemini AI
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets)
    else:
        st.error("⚠️ Falta la clave API de Gemini en los secretos.")
        st.stop()
except Exception as e:
    st.error(f"Error de configuración: {e}")
    st.stop()

# --- 2. FUNCIÓN PARA ANALIZAR LA IMAGEN ---
def analizar_recibo(imagen):
    """Envía la imagen a Gemini Flash y recibe los datos en JSON."""
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = """
    Actúa como un asistente contable. Analiza esta imagen de un recibo y extrae los siguientes datos.
    Devuelve SOLAMENTE un objeto JSON con esta estructura exacta, sin texto adicional ni bloques de código markdown:
    {
        "fecha": "YYYY-MM-DD",
        "comercio": "Nombre del establecimiento",
        "total": 0.00,
        "moneda": "MXN",
        "categoria": "Elige una: Alimentos, Transporte, Servicios, Salud, Ocio, Otros",
        "descripcion": "Resumen muy breve de lo comprado (max 5 palabras)"
    }
    Si la fecha no tiene año, asume el año actual. Si no encuentras un dato, usa null.
    """
    
    try:
        response = model.generate_content([prompt, imagen])
        # Limpiamos la respuesta por si la IA incluye ```json... ```
        texto_limpio = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(texto_limpio)
    except Exception as e:
        st.error(f"Error al analizar con IA: {e}")
        return None

# --- 3. INTERFAZ DE USUARIO (FRONTEND) ---

# Opción A: Cámara del celular
imagen_camara = st.camera_input("📸 Tomar foto del recibo")

# Opción B: Subir archivo (por si tienes la foto guardada)
imagen_subida = st.file_uploader("📂 O subir imagen desde galería", type=["jpg", "png", "jpeg"])

imagen_final = imagen_camara if imagen_camara else imagen_subida

if imagen_final:
    # Mostrar vista previa
    st.image(imagen_final, caption="Recibo capturado", width=300)
    
    if st.button("🤖 Analizar Recibo"):
        with st.spinner("La IA está leyendo tu recibo..."):
            # Convertir imagen a formato que Gemini entienda
            bytes_data = imagen_final.getvalue()
            from PIL import Image
            import io
            img_pil = Image.open(io.BytesIO(bytes_data))
            
            # Llamar a la IA
            datos = analizar_recibo(img_pil)
            
            if datos:
                st.success("¡Datos extraídos!")
                
                # --- 4. FORMULARIO DE VERIFICACIÓN ---
                # Mostramos los datos para que tú los corrijas si la IA se equivocó
                with st.form("form_guardar"):
                    col1, col2 = st.columns(2)
                    fecha = col1.text_input("Fecha", value=datos.get("fecha") or datetime.today().strftime('%Y-%m-%d'))
                    comercio = col2.text_input("Comercio", value=datos.get("comercio") or "")
                    
                    col3, col4 = st.columns(2)
                    total = col3.number_input("Total", value=float(datos.get("total") or 0.0))
                    moneda = col4.text_input("Moneda", value=datos.get("moneda") or "MXN")
                    
                    categoria = st.selectbox("Categoría", 
                                          ,
                                           index=0 if not datos.get("categoria") else.index(datos.get("categoria")) if datos.get("categoria") in else 5)
                    
                    descripcion = st.text_input("Descripción", value=datos.get("descripcion") or "")
                    
                    submitted = st.form_submit_button("💾 Guardar en Google Sheets")
                    
                    if submitted:
                        # --- 5. GUARDAR EN GOOGLE SHEETS ---
                        try:
                            # 1. Leemos los datos actuales
                            df_existente = conn.read(worksheet="Transacciones", usecols=list(range(6)), ttl=0)
                            
                            # 2. Creamos una fila nueva
                            nueva_fila = pd.DataFrame()
                            
                            # 3. Unimos y actualizamos
                            # Nota: streamlit-gsheets actualiza todo el dataset, así que unimos lo viejo con lo nuevo
                            df_actualizado = pd.concat([df_existente, nueva_fila], ignore_index=True)
                            
                            conn.update(worksheet="Transacciones", data=df_actualizado)
                            
                            st.toast("✅ ¡Gasto guardado exitosamente!", icon="🎉")
                            st.balloons()
                            
                        except Exception as e:
                            st.error(f"Error al guardar en Sheets: {e}")
                            st.info("Asegúrate de que tu hoja de cálculo tenga una pestaña llamada 'Transacciones' y las columnas correctas.")
