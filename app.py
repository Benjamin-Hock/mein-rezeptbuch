import streamlit as st
from google import genai
import json
import requests

# Seiten-Konfiguration
st.set_page_config(page_title="Mein Rezeptbuch", page_icon="🍳")

# Einfache Passwort-Abfrage
def check_password():
    """Gibt True zurück, wenn der Benutzer das korrekte Passwort eingegeben hat."""
    if "password_correct" not in st.session_state:
        # Initialisierung
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    # Login-Formular anzeigen
    st.markdown("""
        <style>
        .klassische-ueberschrift {
            font-family: 'Times New Roman', Times, serif;
            font-size: 3rem;
            font-weight: bold;
            color: #2e2e2e;
            text-align: center;
            margin-top: 50px;
        }
        </style>
        <div class="klassische-ueberschrift">Privates Rezeptbuch</div>
    """, unsafe_allow_html=True)
    
    password = st.text_input("Bitte Passwort eingeben:", type="password")
    if st.button("Anmelden"):
        if password == st.secrets.get("APP_PASSWORD", "admin"):
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Falsches Passwort")
    return False

# Nur fortfahren, wenn das Passwort korrekt ist
if check_password():
    # API-Clients initialisieren (Gemini)
    try:
        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    except Exception as e:
        st.error("Fehler: API-Key konnte nicht gefunden werden.")
        client = None

    # Supabase-Zugangsdaten laden
    try:
        supabase_url = st.secrets["SUPABASE_URL"]
        supabase_key = st.secrets["SUPABASE_KEY"]
        
        # Header für die Supabase REST-API
        supabase_headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
    except Exception as e:
        st.error("Fehler: Supabase-Zugangsdaten nicht gefunden.")
        supabase_url = None
        supabase_key = None

    # Funktion zum Laden der Rezepte
    def lade_rezepte():
        if supabase_url and supabase_key:
            try:
                url = f"{supabase_url}/rest/v1/rezepte?select=*&order=created_at.desc"
                response = requests.get(url, headers=supabase_headers)
                if response.status_code == 200:
                    st.session_state.rezepte = response.json()
                else:
                    st.session_state.rezepte = []
            except Exception as e:
                st.session_state.rezepte = []
        else:
            st.session_state.rezepte = []

    # Initialisierung
    if 'rezepte' not in st.session_state:
        lade_rezepte()

    # Titel Design
    st.markdown("""
        <style>
        .klassische-ueberschrift {
            font-family: 'Times New Roman', Times, serif;
            font-size: 3.5rem;
            font-weight: bold;
            color: #2e2e2e;
            text-align: center;
            margin-bottom: 20px;
        }
        .stButton > button {
            width: 100%;
            border-radius: 5px;
        }
        </style>
        <div class="klassische-ueberschrift">Mein Rezeptbuch</div>
    """, unsafe_allow_html=True)

    # Eingabe
    neues_rezept = st.text_area("Neues Rezept eintragen:", height=150)

    if st.button("Rezept formatieren & speichern"):
        if neues_rezept and client:
            with st.spinner("KI arbeitet..."):
                try:
                    prompt = f"""
                    Du bist ein professioneller Koch-Assistent. 
                    Formatiere diesen Text zu einem kompakten Rezept.
                    Regeln: Kurzer Titel (max 4 Wörter), keine Floskeln am Ende, Markdown Struktur.
                    JSON Format: {{"titel": "...", "text": "..."}}
                    Text: {neues_rezept}
                    """
                    # Umstellung auf gemini-1.5-flash für höhere Quoten-Limits
                    response = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
                    
                    antwort_text = response.text.strip()
                    if antwort_text.startswith("```json"):
                        antwort_text = antwort_text.replace("```json", "").replace("```", "").strip()
                    
                    rezept_daten = json.loads(antwort_text)
                    
                    if supabase_url:
                        url = f"{supabase_url}/rest/v1/rezepte"
                        db_res = requests.post(url, headers=supabase_headers, json=rezept_daten)
                        if db_res.status_code in [200, 201]:
                            lade_rezepte()
                            st.success("Gespeichert!")
                        else:
                            st.error(f"Datenbank-Fehler: {db_res.text}")
                except Exception as e:
                    if "429" in str(e):
                        st.error("Das tägliche Limit der KI ist erreicht. Bitte versuche es morgen wieder oder wechsle den API-Plan.")
                    else:
                        st.error(f"Fehler: {e}")
        else:
            st.warning("Bitte Text eingeben.")

    st.divider()

    # Anzeige
    if st.session_state.rezepte:
        for i, rezept in enumerate(st.session_state.rezepte):
            db_id = rezept.get('id')
            titel = rezept.get('titel', 'Unbekannt')
            inhalt = rezept.get('text', '')

            with st.expander(titel):
                edit_key = f"edit_{i}"
                if edit_key not in st.session_state: st.session_state[edit_key] = False

                if st.session_state[edit_key]:
                    n_titel = st.text_input("Titel:", value=titel, key=f"ti_{i}")
                    n_text = st.text_area("Inhalt:", value=inhalt, height=250, key=f"te_{i}")
                    c1, c2 = st.columns([1, 1])
                    with c1:
                        if st.button("💾 Speichern", key=f"s_{i}"):
                            url = f"{supabase_url}/rest/v1/rezepte?id=eq.{db_id}"
                            requests.patch(url, headers=supabase_headers, json={"titel": n_titel, "text": n_text})
                            lade_rezepte()
                            st.session_state[edit_key] = False
                            st.rerun()
                    with c2:
                        if st.button("Abbrechen", key=f"c_{i}"):
                            st.session_state[edit_key] = False
                            st.rerun()
                else:
                    st.markdown(inhalt)
                    
                    del_key = f"del_{i}"
                    if del_key not in st.session_state: st.session_state[del_key] = False

                    if st.session_state[del_key]:
                        st.warning("Löschen?")
                        dc1, dc2 = st.columns([1, 1])
                        with dc1:
                            if st.button("Ja", key=f"y_{i}"):
                                url = f"{supabase_url}/rest/v1/rezepte?id=eq.{db_id}"
                                requests.delete(url, headers=supabase_headers)
                                lade_rezepte()
                                st.rerun()
                        with dc2:
                            if st.button("Nein", key=f"n_{i}"):
                                st.session_state[del_key] = False
                                st.rerun()
                    else:
                        b1, b2, _ = st.columns([1, 1, 2])
                        with b1:
                            if st.button("✎", key=f"eb_{i}"):
                                st.session_state[edit_key] = True
                                st.rerun()
                        with b2:
                            if st.button("🗑\uFE0E", key=f"db_{i}"):
                                st.session_state[del_key] = True
                                st.rerun()
    else:
        st.info("Noch keine Rezepte da.")
