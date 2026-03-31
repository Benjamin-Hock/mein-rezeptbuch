import streamlit as st
from google import genai
import json
import requests
import time

# Seiten-Konfiguration
st.set_page_config(page_title="Mein Rezeptbuch", page_icon="🍳")

# Einfache Passwort-Abfrage für den privaten Zugriff
def check_password():
    """Prüft, ob das korrekte Passwort eingegeben wurde."""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

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

# Hauptprogramm nach Login
if check_password():
    # Client mit dem API-Key initialisieren
    try:
        client = genai.Client(api_key=st.secrets.get("GEMINI_API_KEY", ""))
    except Exception as e:
        st.error("Fehler: API-Key konnte nicht gefunden werden.")
        client = None

    # Supabase-Zugangsdaten laden
    try:
        supabase_url = st.secrets["SUPABASE_URL"]
        supabase_key = st.secrets["SUPABASE_KEY"]
        supabase_headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
    except Exception as e:
        st.error("Fehler: Supabase-Zugangsdaten fehlen.")
        supabase_url = None
        supabase_key = None

    # Rezepte aus der Datenbank abrufen
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

    if 'rezepte' not in st.session_state:
        lade_rezepte()

    # Optische Gestaltung
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

    neues_rezept = st.text_area("Neues Rezept eintragen:", height=150, placeholder="Zutaten und Schritte hier rein kopieren...")

    col_actions1, col_actions2 = st.columns([1, 1])
    
    with col_actions1:
        if st.button("KI-Formatierung & Speichern"):
            if neues_rezept and client:
                with st.spinner("Rezept wird formatiert..."):
                    try:
                        # Prompt mit dem exakten Wunschformat
                        prompt = f"""
                        Du bist ein präziser Koch-Assistent. Formatiere diesen Text zu einem kompakten Rezept. Formatiere den Input nach diesem Schema:
                        
                        {{
                          "titel": "Kurzer Titel (max 4 Wörter)",
                          "text": "## Titel\\n\\n**Zutaten:**\\n* Zutat 1\\n* Zutat 2\\n\\n**Zubereitung:**\\n1. Schritt 1\\n2. Schritt 2"
                        }}

                        REGELN:
                        - Antworte NUR mit validem JSON.
                        - Nutze EXAKT die Überschriften '**Zutaten:**' und '**Zubereitung:**' (fett mit Doppelpunkt).
                        - Kurzer Titel (max 4 Wörter), keine Floskeln am Ende, Markdown Struktur.
                        - Nutze '*' für die Zutatenliste und Zahlen '1.', '2.' für die Zubereitungsschritte.
                        - Keine Floskeln wie 'Guten Appetit' oder Einleitungssätze.

                        INPUT:
                        {neues_rezept}
                        """
                        
                        response = client.models.generate_content(
                            model='gemini-2.5-flash', 
                            contents=prompt
                        )
                        
                        raw_text = response.text.strip()
                        if "```json" in raw_text:
                            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in raw_text:
                            raw_text = raw_text.split("```")[1].split("```")[0].strip()
                        
                        rezept_daten = json.loads(raw_text)
                        
                        if supabase_url:
                            url = f"{supabase_url}/rest/v1/rezepte"
                            db_res = requests.post(url, headers=supabase_headers, json=rezept_daten)
                            if db_res.status_code in [200, 201]:
                                lade_rezepte()
                                st.success("KI hat das Rezept perfekt serviert!")
                                st.rerun()
                    except Exception as e:
                        if "429" in str(e):
                            st.error("Tageslimit erreicht. Bitte 'Direkt speichern' nutzen.")
                        else:
                            st.error(f"Fehler: {e}")
            else:
                st.warning("Bitte erst Text eingeben.")

    with col_actions2:
        if st.button("Direkt speichern"):
            if neues_rezept:
                zeilen = neues_rezept.split('\n')
                titel_manuell = zeilen[0][:30] if zeilen else "Neues Rezept"
                rezept_daten = {"titel": titel_manuell, "text": neues_rezept}
                
                if supabase_url:
                    url = f"{supabase_url}/rest/v1/rezepte"
                    db_res = requests.post(url, headers=supabase_headers, json=rezept_daten)
                    if db_res.status_code in [200, 201]:
                        lade_rezepte()
                        st.success("Manuell gespeichert!")
                        st.rerun()
            else:
                st.warning("Kein Text vorhanden.")

    st.divider()

    # Anzeige der Rezepte
    if st.session_state.rezepte:
        for i, rezept in enumerate(st.session_state.rezepte):
            db_id = rezept.get('id')
            titel = rezept.get('titel', 'Unbekannt')
            inhalt = rezept.get('text', '')

            # Eindeutige Keys basierend auf der DB-ID statt dem Listen-Index
            edit_key = f"edit_state_{db_id}"
            del_key = f"del_state_{db_id}"

            with st.expander(titel):
                if edit_key not in st.session_state: st.session_state[edit_key] = False
                if del_key not in st.session_state: st.session_state[del_key] = False

                if st.session_state[edit_key]:
                    n_titel = st.text_input("Titel bearbeiten:", value=titel, key=f"ti_{db_id}")
                    n_text = st.text_area("Inhalt bearbeiten:", value=inhalt, height=250, key=f"te_{db_id}")
                    c1, c2 = st.columns([1, 1])
                    with c1:
                        if st.button("💾 Speichern", key=f"s_{db_id}"):
                            if supabase_url and db_id:
                                url = f"{supabase_url}/rest/v1/rezepte?id=eq.{db_id}"
                                requests.patch(url, headers=supabase_headers, json={"titel": n_titel, "text": n_text})
                                lade_rezepte()
                                st.session_state[edit_key] = False
                                st.rerun()
                    with c2:
                        if st.button("Abbrechen", key=f"c_{db_id}"):
                            st.session_state[edit_key] = False
                            st.rerun()
                else:
                    st.markdown(inhalt)
                    
                    if st.session_state[del_key]:
                        st.warning("Wirklich löschen?")
                        dc1, dc2 = st.columns([1, 1])
                        with dc1:
                            if st.button("Ja, löschen", key=f"y_{db_id}"):
                                if supabase_url and db_id:
                                    url = f"{supabase_url}/rest/v1/rezepte?id=eq.{db_id}"
                                    requests.delete(url, headers=supabase_headers)
                                    # Status-Keys aufräumen
                                    if edit_key in st.session_state: del st.session_state[edit_key]
                                    if del_key in st.session_state: del st.session_state[del_key]
                                    lade_rezepte()
                                    st.rerun()
                        with dc2:
                            if st.button("Nein", key=f"n_{db_id}"):
                                st.session_state[del_key] = False
                                st.rerun()
                    else:
                        b1, b2, _ = st.columns([1, 1, 3])
                        with b1:
                            if st.button("✎", key=f"eb_{db_id}"):
                                st.session_state[edit_key] = True
                                st.rerun()
                        with b2:
                            if st.button("🗑\uFE0E", key=f"db_{db_id}"):
                                st.session_state[del_key] = True
                                st.rerun()
    else:
        st.info("Noch keine Rezepte vorhanden.")
