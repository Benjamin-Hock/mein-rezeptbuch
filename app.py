import streamlit as st
from google import genai
import json
import requests

# Seiten-Konfiguration
st.set_page_config(page_title="Mein Rezeptbuch", page_icon="🍳")

# API-Clients initialisieren (Gemini)
try:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error("Fehler: API-Key konnte nicht gefunden werden.")
    client = None

# Supabase-Zugangsdaten laden und Header für direkte API-Anfragen vorbereiten
try:
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
    
    # Standard-Header für die Supabase REST-API
    supabase_headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
except Exception as e:
    st.error("Fehler: Supabase-Zugangsdaten nicht gefunden in secrets.toml.")
    supabase_url = None
    supabase_key = None

# Funktion zum Laden der Rezepte aus der Datenbank
def lade_rezepte():
    if supabase_url and supabase_key:
        try:
            # API-Aufruf an Supabase (Tabelle 'rezepte', sortiert nach Erstellungsdatum)
            url = f"{supabase_url}/rest/v1/rezepte?select=*&order=created_at.desc"
            response = requests.get(url, headers=supabase_headers)
            
            if response.status_code == 200:
                st.session_state.rezepte = response.json()
            else:
                st.error(f"Datenbank-Fehler beim Laden: {response.text}")
                st.session_state.rezepte = []
        except Exception as e:
            st.error(f"Verbindungsfehler zur Datenbank: {e}")
            st.session_state.rezepte = []
    else:
        st.session_state.rezepte = []

# Temporären Speicher initialisieren und Daten beim ersten Start laden
if 'rezepte' not in st.session_state:
    lade_rezepte()

# Eigenes CSS einbinden
st.markdown("""
    <style>
    .klassische-ueberschrift {
        font-family: 'Times New Roman', Times, serif;
        font-size: 3.5rem;
        font-weight: bold;
        color: #2e2e2e;
        margin-bottom: 0.5rem;
        text-align: center;
    }
    </style>
    <div class="klassische-ueberschrift">Mein Rezeptbuch</div>
""", unsafe_allow_html=True)

st.divider()

# Eingabebereich
neues_rezept = st.text_area("Neues Rezept eintragen:", height=150)

if st.button("Rezept formatieren & speichern", key="btn_text"):
    if neues_rezept and client:
        with st.spinner("KI formatiert und speichert das Rezept..."):
            try:
                prompt = f"""
                Du bist ein professioneller Koch-Assistent. 
                Nimm den folgenden Text und formatiere ihn in ein sauberes, vollständiges Rezept.

                Regeln:
                1. Titel: Finde einen SEHR KURZEN, prägnanten Titel (max. 2-4 Wörter, z.B. "Maultaschen Auflauf").
                2. Kompaktheit & Logik: Formatiere den Text zu einem logischen Rezept, aber halte die Zubereitungsschritte so KURZ UND KNAPP wie möglich. Ergänze fehlende logische Zwischenschritte nur, wenn absolut nötig, aber schreibe keine Romane und erfinde keine unnötigen Details.
                3. Floskeln: Lasse unwichtige End-Sätze wie "Servieren und genießen" oder "Guten Appetit" weg.
                4. Markdown-Struktur für den Text:
                   ## [Der kurze Titel]
                   ### Zutaten
                   ...
                   ### Zubereitung
                   ...
                
                Antworte AUSSCHLIESSLICH in folgendem JSON-Format (ohne Codeblöcke drumherum):
                {{
                  "titel": "Dein kurzer Titel",
                  "text": "Das komplette Rezept in Markdown"
                }}
                
                Text:
                {neues_rezept}
                """
                
                response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                
                # JSON Text bereinigen
                antwort_text = response.text.strip()
                if antwort_text.startswith("```json"):
                    antwort_text = antwort_text[7:]
                if antwort_text.endswith("```"):
                    antwort_text = antwort_text[:-3]
                    
                # Text in Dictionary umwandeln
                rezept_daten = json.loads(antwort_text.strip())
                
                # Direkt per API-Aufruf in der Supabase-Datenbank speichern
                if supabase_url:
                    url = f"{supabase_url}/rest/v1/rezepte"
                    db_response = requests.post(url, headers=supabase_headers, json=rezept_daten)
                    
                    if db_response.status_code in [200, 201]:
                        lade_rezepte() # Liste sofort aktualisieren
                        st.success("Rezept erfolgreich in der Datenbank gespeichert!")
                    else:
                        st.error(f"Fehler beim Speichern in der Datenbank: {db_response.text}")
                else:
                    st.error("Datenbankverbindung fehlt. Rezept nicht gespeichert.")
                    
            except Exception as e:
                st.error(f"Fehler bei der Anfrage: {e}")
    elif not client:
        st.warning("API-Key fehlt.")
    else:
        st.warning("Bitte gib einen Text ein.")

st.divider()

# Anzeigebereich
if st.session_state.rezepte:
    for i, rezept in enumerate(st.session_state.rezepte):
        # Datenbank-ID für Änderungen und Löschungen auslesen
        db_id = rezept.get('id')
        anzeige_titel = rezept.get('titel', f'Rezept {i+1}')
        anzeige_text = rezept.get('text', '')

        with st.expander(anzeige_titel, expanded=False):
            edit_key = f"edit_{i}"
            if edit_key not in st.session_state:
                st.session_state[edit_key] = False

            if st.session_state[edit_key]:
                # Bearbeitungsmodus
                neuer_titel = st.text_input("Titel bearbeiten:", value=anzeige_titel, key=f"title_input_{i}")
                neuer_text = st.text_area("Rezept bearbeiten:", value=anzeige_text, height=300, key=f"text_input_{i}")
                
                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("💾 Speichern", key=f"save_btn_{i}"):
                        # Änderungen per API an Supabase senden
                        if supabase_url and db_id:
                            url = f"{supabase_url}/rest/v1/rezepte?id=eq.{db_id}"
                            update_daten = {"titel": neuer_titel, "text": neuer_text}
                            requests.patch(url, headers=supabase_headers, json=update_daten)
                            lade_rezepte()
                        
                        st.session_state[edit_key] = False
                        st.rerun()
                with col2:
                    if st.button("❌ Abbrechen", key=f"cancel_btn_{i}"):
                        st.session_state[edit_key] = False
                        st.rerun()
            else:
                # Normaler Anzeigemodus
                st.markdown(anzeige_text)
                
                delete_key = f"delete_confirm_{i}"
                if delete_key not in st.session_state:
                    st.session_state[delete_key] = False

                if st.session_state[delete_key]:
                    st.warning("Dieses Rezept wirklich aus der Datenbank löschen?")
                    col_yes, col_no, _ = st.columns([1, 1, 4])
                    with col_yes:
                        if st.button("Ja, löschen", key=f"yes_del_{i}"):
                            # Status-Variablen bereinigen
                            for key in list(st.session_state.keys()):
                                if key.startswith("edit_") or key.startswith("delete_confirm_"):
                                    del st.session_state[key]
                            
                            # Rezept per API aus Supabase löschen
                            if supabase_url and db_id:
                                url = f"{supabase_url}/rest/v1/rezepte?id=eq.{db_id}"
                                requests.delete(url, headers=supabase_headers)
                                lade_rezepte()
                            
                            st.rerun()
                    with col_no:
                        if st.button("Abbrechen", key=f"no_del_{i}"):
                            st.session_state[delete_key] = False
                            st.rerun()
                else:
                    # Buttons
                    col_btn1, col_btn2, col_space = st.columns([1, 1, 10])
                    with col_btn1:
                        if st.button("✎", key=f"edit_btn_{i}"):
                            st.session_state[edit_key] = True
                            st.rerun()
                    with col_btn2:
                        if st.button("🗑\uFE0E", key=f"delete_btn_{i}"):
                            st.session_state[delete_key] = True
                            st.rerun()
else:
    st.info("Es sind noch keine Rezepte vorhanden.")