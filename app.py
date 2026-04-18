import streamlit as st
from streamlit_gsheets import GSheetsConnection
from google import genai
import json
import pandas as pd
from datetime import datetime
import uuid

# Seiten-Konfiguration
st.set_page_config(page_title="Mein Rezeptbuch", page_icon="🍳")

# Passwort-Abfrage
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True

    st.markdown('<div style="text-align:center; margin-top:50px; font-family:serif; font-size:3rem; font-weight:bold;">Privates Rezeptbuch</div>', unsafe_allow_html=True)
    password = st.text_input("Bitte Passwort eingeben:", type="password")
    if st.button("Anmelden"):
        if password == st.secrets.get("APP_PASSWORD", "admin"):
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Falsches Passwort")
    return False

if check_password():
    # Verbindung zu Google Sheets aufbauen
    conn = st.connection("gsheets", type=GSheetsConnection)

    # Gemini Client initialisieren
    try:
        client = genai.Client(api_key=st.secrets.get("GEMINI_API_KEY", ""))
    except:
        client = None

    def lade_daten():
        # Liest das Tabellenblatt 'rezepte' ein
        # ttl="0" verhindert das Caching, damit immer die neuesten Daten geladen werden
        try:
            return conn.read(worksheet="rezepte", ttl="0")
        except Exception as e:
            st.error("Fehler beim Laden der Tabelle. Bitte Freigabe und Namen des Tabellenblatts prüfen.")
            return pd.DataFrame()

    def speichere_daten(df):
        # Aktualisiert die gesamte Tabelle
        conn.update(worksheet="rezepte", data=df)

    # Daten initial laden
    data = lade_daten()

    st.markdown('<div style="text-align:center; margin-bottom:20px; font-family:serif; font-size:3.5rem; font-weight:bold;">Mein Rezeptbuch</div>', unsafe_allow_html=True)

    neues_rezept = st.text_area("Neues Rezept eintragen:", height=150, placeholder="Zutaten und Schritte hier rein kopieren...")

    col_actions1, col_actions2 = st.columns([1, 1])
    
    # Hilfsfunktion zum Hinzufügen einer neuen Zeile
    def rezept_hinzufuegen(titel, text, kategorie="Allgemein"):
        neu = pd.DataFrame([{
            "id": str(uuid.uuid4()),
            "titel": titel,
            "text": text,
            "kategorie": kategorie,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }])
        
        # Neue Daten oben anfügen (sofern 'data' nicht leer ist)
        if not data.empty:
            # Spaltenreihenfolge an die bestehende Tabelle anpassen
            neu = neu.reindex(columns=data.columns)
            updated_df = pd.concat([neu, data], ignore_index=True)
        else:
            updated_df = neu
            
        speichere_daten(updated_df)
        st.rerun()

    with col_actions1:
        if st.button("KI-Formatierung & Speichern"):
            if neues_rezept and client:
                with st.spinner("Rezept wird formatiert..."):
                    try:
                        prompt = f"""
                        Du bist ein präziser Koch-Assistent. Formatiere diesen Text zu einem kompakten Rezept. 
                        Antworte NUR mit validem JSON:
                        {{
                          "titel": "Kurzer Titel", 
                          "text": "## Titel\\n\\n**Zutaten:**\\n* ...\\n\\n**Zubereitung:**\\n1. ..."
                        }}
                        INPUT: {neues_rezept}
                        """
                        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                        raw_text = response.text.strip()
                        
                        # JSON Extraktion
                        if "```json" in raw_text: 
                            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in raw_text:
                            raw_text = raw_text.split("```")[1].split("```")[0].strip()
                            
                        res_json = json.loads(raw_text)
                        rezept_hinzufuegen(res_json["titel"], res_json["text"])
                        st.success("KI hat das Rezept gespeichert!")
                    except Exception as e:
                        st.error(f"Fehler bei der KI-Generierung: {e}")
            else:
                st.warning("Bitte erst einen Text eingeben.")

    with col_actions2:
        if st.button("Direkt speichern"):
            if neues_rezept:
                titel = neues_rezept.split('\n')[0][:30]
                rezept_hinzufuegen(titel, neues_rezept)
                st.success("Manuell gespeichert!")
            else:
                st.warning("Kein Text vorhanden.")

    st.divider()

    # Rezepte anzeigen
    if not data.empty:
        # Fehlende Kategorien auffangen, falls durch CSV-Import Lücken entstanden sind
        if "kategorie" not in data.columns:
            data["kategorie"] = "Allgemein"
        data["kategorie"] = data["kategorie"].fillna("Allgemein")

        # Filter für Ordner-Logik
        rezepte_allgemein = data[data["kategorie"] != "Backen"]
        rezepte_backen = data[data["kategorie"] == "Backen"]

        def render_liste(df_subset, is_backen_folder=False):
            for _, row in df_subset.iterrows():
                rid = str(row["id"])
                titel = str(row["titel"])
                text = str(row["text"])
                
                with st.expander(titel):
                    # Bearbeitungs-Status pro ID
                    edit_key = f"edit_{rid}"
                    if edit_key not in st.session_state: 
                        st.session_state[edit_key] = False

                    if st.session_state[edit_key]:
                        n_titel = st.text_input("Titel:", value=titel, key=f"ti_{rid}")
                        n_text = st.text_area("Inhalt:", value=text, height=250, key=f"te_{rid}")
                        
                        c1, c2 = st.columns([1, 1])
                        with c1:
                            if st.button("Übernehmen", key=f"save_{rid}"):
                                data.loc[data["id"] == rid, ["titel", "text"]] = [n_titel, n_text]
                                speichere_daten(data)
                                st.session_state[edit_key] = False
                                st.rerun()
                        with c2:
                            if st.button("Abbrechen", key=f"cancel_{rid}"):
                                st.session_state[edit_key] = False
                                st.rerun()
                    else:
                        st.markdown(text)
                        b1, b2, b3 = st.columns([1, 1, 2])
                        with b1:
                            if st.button("✎", key=f"eb_{rid}"):
                                st.session_state[edit_key] = True
                                st.rerun()
                        with b2:
                            if st.button("🗑", key=f"db_{rid}"):
                                data_neu = data[data["id"] != rid]
                                speichere_daten(data_neu)
                                st.rerun()
                        with b3:
                            ziel = "Allgemein" if is_backen_folder else "Backen"
                            label = "↑ Kochen" if is_backen_folder else "↓ Backen"
                            if st.button(label, key=f"mv_{rid}"):
                                data.loc[data["id"] == rid, "kategorie"] = ziel
                                speichere_daten(data)
                                st.rerun()

        # Erst die normalen Rezepte rendern
        render_liste(rezepte_allgemein)
        
        # Dann den Backen-Ordner rendern
        st.write("")
        with st.expander("🍰 Backen-Ordner", expanded=False):
            if rezepte_backen.empty:
                st.info("Noch keine Backrezepte vorhanden.")
            else:
                render_liste(rezepte_backen, is_backen_folder=True)
    else:
        st.info("Keine Rezepte gefunden.")
