import streamlit as st
import pandas as pd
import datetime
from fpdf import FPDF
import io  # Zum Zwischenspeichern der PDF-Datei im Speicher
import matplotlib.pyplot as plt  # Für die Diagramme
from io import BytesIO  # Um das Bild in den Speicher zu speichern
import tempfile  # Für das Erstellen einer temporären Datei



# Funktion zur PDF-Erstellung mit Grafik, Zusammenfassung und Fußzeile
def generate_pdf_with_graph(protocol_df, fig, summary_text):
    pdf = FPDF()

    # Setze Seitenränder auf 15 mm
    pdf.set_margins(15, 15, 15)

    pdf.add_page()

    # Füge den Titel hinzu
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(200, 10, txt="Dosissteigerungsprotokoll", ln=True, align='L')

    # Füge die Fußzeile mit Datum und Uhrzeit hinzu
    current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pdf.ln(2)
    pdf.set_font('Arial', 'I', 8)
    pdf.cell(200, 10,
             txt=f"Dieses Dosissteigerungsprotokoll wurde automatisch mit dem Treprostinil Dosisrechner (Beta Version 1.0) am {current_datetime} erstellt.",
             ln=True, align='L')

    # Füge die Tabelle hinzu (angepasste Spaltenbreiten und kleinere Schriftgröße)
    pdf.set_font('Arial', '', 8)  # Kleinere Schriftgröße für die Tabelle
    col_widths = [20, 25, 20, 32, 73]  # Anpassung der Spaltenbreiten
    columns = ["Datum", "Dosis (ng/kg/min)", "Laufrate (µl/h)", "Noch im Reservoir (ml)", "Hinweis"]

    # Angepasste Zeilenhöhe (z.B. 12 Einheiten)
    row_height = 8

    for i, col in enumerate(columns):
        pdf.cell(col_widths[i % len(col_widths)], row_height, col, 1)
    pdf.ln()

    for row in protocol_df.itertuples():
        pdf.cell(col_widths[0], row_height, str(row[1]), 1)
        pdf.cell(col_widths[1], row_height, str(row[2]), 1)
        pdf.cell(col_widths[2], row_height, str(row[3]), 1)
        pdf.cell(col_widths[3], row_height, str(row[4]), 1)

        # Umbruch für die "Hinweis"-Spalte, wenn der Text zu lang ist
        hint_text = str(row[5])
        pdf.multi_cell(col_widths[4], row_height, hint_text, 1)

    # Füge die Zusammenfassung hinzu
    pdf.ln(5)
    pdf.set_font('Arial', '', 10)
    for line in summary_text.split('\n'):
        pdf.cell(200, 10, txt=line, ln=True)



    # Speichere die Grafik in eine temporäre Datei
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
        fig.savefig(tmpfile.name, format='PNG')
        pdf.image(tmpfile.name, x=10, y=None, w=180)



    # Schreibe die PDF in einen Byte-Stream anstelle einer Datei
    pdf_output = pdf.output(dest='S').encode('latin1')
    return pdf_output


# Funktion zur Ermittlung der nächsthöheren Konzentration
def get_next_higher_concentration(current_concentration):
    concentrations = [1, 2.5, 5, 10, 20]  # Liste der verfügbaren Konzentrationen in mg/ml
    for conc in concentrations:
        if conc > current_concentration:
            return conc
    return current_concentration  # Rückgabe der aktuellen Konzentration, wenn keine höhere gefunden wird


# Funktion zur Berechnung der Laufrate in µl/h
def calculate_infusion_rate(weight, dose, concentration):
    dose_mcg_per_min = dose * weight / 1000  # ng/kg/min in µg/min umrechnen
    dose_mg_per_h = dose_mcg_per_min * 60 / 1000  # µg/min in mg/h umrechnen
    infusion_rate = dose_mg_per_h / concentration * 1000  # mg/h in µl/h umrechnen
    return infusion_rate


# Funktion zur Berechnung der Haltbarkeit des Reservoirs in Tagen
def calculate_reservoir_duration(infusion_rate, reservoir_volume=3):
    reservoir_duration_hours = (
                                           reservoir_volume * 1000) / infusion_rate  # Reservoirvolumen in µl, Infusionsrate in µl/h
    reservoir_duration_days = reservoir_duration_hours / 24  # in Tagen umrechnen
    return reservoir_duration_days


# Funktion zur Berechnung der Dosis in ng/kg/min basierend auf der Laufrate
def calculate_dose_from_infusion_rate(weight, infusion_rate, concentration):
    dose_mg_per_h = infusion_rate * concentration / 1000  # µl/h in mg/h umrechnen
    dose_mcg_per_min = dose_mg_per_h * 1000 / 60  # mg/h in µg/min umrechnen
    dose_ng_per_kg_min = dose_mcg_per_min / weight * 1000  # µg/min in ng/kg/min umrechnen
    return dose_ng_per_kg_min


# Funktion zur Berechnung der Perfusor-Laufrate in ml/h
def calculate_perfusor_rate(weight, dose, concentration):
    diluted_concentration = concentration / 50  # Konzentration des verdünnten Medikaments
    dose_mcg_per_min = dose * weight / 1000  # ng/kg/min in µg/min umrechnen
    dose_mg_per_h = dose_mcg_per_min * 60 / 1000  # µg/min in mg/h umrechnen
    perfusor_rate = dose_mg_per_h / diluted_concentration  # mg/h in ml/h umrechnen
    return perfusor_rate


# Dosissteigerungsprotokoll Funktion
def generate_dose_increase_protocol(current_dose, target_dose, weeks, increases_per_week, weight, concentration,
                                    pump_capacity=3, vial_capacity=10):
    total_increases = weeks * increases_per_week
    dose_step = (target_dose - current_dose) / total_increases
    protocol = []
    current_dose = current_dose
    current_date = datetime.date.today()

    current_reservoir_volume = pump_capacity  # 3 ml für die Reservoirkapazität
    vial_refills_left = vial_capacity / pump_capacity  # Ein Vial kann 3 Mal das Reservoir füllen
    reservoir_days_used = 0  # Zählt die Tage, die das aktuelle Reservoir in der Pumpe verbleibt

    vial_usage = {}  # Um den Vial-Verbrauch pro Konzentration zu zählen
    reservoir_changes = 0  # Anzahl der Reservoirwechsel
    reservoir_intervals = []  # Liste der Intervalle für Reservoirwechsel

    last_reservoir_change_date = None  # Um die Zeit zwischen den Reservoirwechseln zu messen

    for i in range(total_increases):
        current_date += datetime.timedelta(days=7 / increases_per_week)  # Berechnung des Datums für jede Steigerung
        current_dose += dose_step  # Steigere die Dosis
        infusion_rate = calculate_infusion_rate(weight, current_dose, concentration)
        rounded_infusion_rate = round(infusion_rate)

        # Verbrauch pro Tag in ml
        daily_consumption_ml = rounded_infusion_rate * 24 / 1000  # µl in ml umrechnen
        reservoir_days_left = current_reservoir_volume / daily_consumption_ml
        reservoir_days_used += 7 / increases_per_week  # Zählt die Tage, die das aktuelle Reservoir verwendet wird

        # Reservoirwechsel erzwingen, wenn 14 Tage erreicht sind, unabhängig vom Restvolumen
        if reservoir_days_used >= 14 or reservoir_days_left < 1:
            current_reservoir_volume = pump_capacity
            vial_refills_left -= 1  # Eine Reservoirfüllung verbraucht
            reservoir_days_used = 0  # Setze die Zähler zurück, da das Reservoir gewechselt wurde
            reservoir_changes += 1

            # Berechne das Intervall zwischen Reservoirwechseln
            if last_reservoir_change_date:
                interval = (current_date - last_reservoir_change_date).days
                reservoir_intervals.append(interval)
            last_reservoir_change_date = current_date  # Setze das Datum des letzten Reservoirwechsels

            # Wenn das Vial aufgebraucht ist, ein neues Vial anfangen
            if vial_refills_left <= 0:
                if concentration in vial_usage:
                    vial_usage[concentration] += 1
                else:
                    vial_usage[concentration] = 1
                concentration = get_next_higher_concentration(concentration)
                vial_refills_left = vial_capacity / pump_capacity  # Neues Vial anfangen
                protocol.append({
                    "Datum": current_date,
                    "Dosis (ng/kg/min)": round(current_dose, 2),
                    "Laufrate (µl/h)": rounded_infusion_rate,
                    "Restvolumen im Reservoir (ml)": round(current_reservoir_volume, 2),
                    "Hinweis": f"Vialwechsel erforderlich. Neue Konzentration: {concentration} mg/ml"
                })
            else:
                protocol.append({
                    "Datum": current_date,
                    "Dosis (ng/kg/min)": round(current_dose, 2),
                    "Laufrate (µl/h)": rounded_infusion_rate,
                    "Restvolumen im Reservoir (ml)": round(current_reservoir_volume, 2),
                    "Hinweis": "Reservoir neu gefüllt"
                })
        else:
            current_reservoir_volume -= daily_consumption_ml  # Reduziere das Restvolumen im Reservoir
            protocol.append({
                "Datum": current_date,
                "Dosis (ng/kg/min)": round(current_dose, 2),
                "Laufrate (µl/h)": rounded_infusion_rate,
                "Restvolumen im Reservoir (ml)": round(current_reservoir_volume, 2),
                "Hinweis": ""
            })

    # Füge das letzte Vial zur Liste hinzu, falls es nicht bereits registriert wurde
    if concentration in vial_usage:
        vial_usage[concentration] += 1
    else:
        vial_usage[concentration] = 1

    return protocol, vial_usage, reservoir_changes, reservoir_intervals


# Funktion zur Erstellung der Grafik mit Reservoir-Inhalt als Balken
def plot_dose_infusion_rate_reservoir(protocol):
    dates = [entry["Datum"] for entry in protocol]
    doses = [entry["Dosis (ng/kg/min)"] for entry in protocol]
    infusion_rates = [entry["Laufrate (µl/h)"] for entry in protocol]
    reservoir_volumes = [entry["Restvolumen im Reservoir (ml)"] for entry in protocol]
    vial_changes = [i for i, entry in enumerate(protocol) if "Vialwechsel" in entry["Hinweis"]]

    fig, ax1 = plt.subplots(figsize=(10, 5))

    # Dosis darstellen
    ax1.plot(dates, doses, marker='o', color='b', label='Dosis (ng/kg/min)')
    ax1.set_xlabel('Datum')
    ax1.set_ylabel('Dosis (ng/kg/min)', color='b')
    ax1.tick_params(axis='y', labelcolor='b')

    # Pumpenlaufrate darstellen (zweite y-Achse)
    ax2 = ax1.twinx()
    ax2.plot(dates, infusion_rates, marker='s', color='g', label='Laufrate (µl/h)')
    ax2.set_ylabel('Laufrate (µl/h)', color='g')
    ax2.tick_params(axis='y', labelcolor='g')

    # Reservoir-Inhalt als Balken hinzufügen (separate Achse für den Bar-Plot)
    ax3 = ax1.twinx()
    ax3.bar(dates, reservoir_volumes, alpha=0.3, color='orange', width=1.0, label='Reservoir Inhalt (ml)')
    ax3.set_ylabel('Reservoir Inhalt (ml)', color='orange')
    ax3.tick_params(axis='y', labelcolor='orange')
    ax3.spines['right'].set_position(('outward', 60))  # Verschiebe die dritte Achse nach außen

    # Markiere Vialwechsel
    for idx in vial_changes:
        ax1.axvline(dates[idx], color='r', linestyle='--', label=f'Vialwechsel am {dates[idx]}')

    plt.title('Dosissteigerungsprotokoll mit Laufrate und Reservoir-Inhalt')
    fig.tight_layout()
    return fig


# Funktion zur Erstellung der Zusammenfassung
def generate_summary(vial_usage, reservoir_changes, reservoir_intervals, total_weeks):
    summary = f"Zusammenfassung des Dosissteigerungsprotokolls:\n"
    summary += f"- Gesamtdauer des Protokolls: {total_weeks} Wochen\n"
    summary += f"- Anzahl der Reservoirwechsel: {reservoir_changes}\n"

    if reservoir_intervals:
        shortest_interval = min(reservoir_intervals)
        longest_interval = max(reservoir_intervals)
        summary += f"- Kürzestes Intervall zwischen Reservoirwechseln: {shortest_interval} Tage\n"
        summary += f"- Längstes Intervall zwischen Reservoirwechseln: {longest_interval} Tage\n"
    else:
        summary += f"- Keine Reservoirwechsel während des Protokolls\n"

    summary += f"- Vialverbrauch:\n"

    for concentration, count in vial_usage.items():
        summary += f"  - {count} Vials mit {concentration} mg/ml\n"

    return summary


# Streamlit App
st.title("Treprostinil Dosisrechner")

# Tabs für die unterschiedlichen Berechnungen
tab1, tab2, tab3, tab4 = st.tabs(["Infusionsrate", "Dosisberechnung", "Perfusor Laufrate", "Dosissteigerungsprotokoll"])

# Infusionsrate berechnen
with tab1:
    st.markdown("### Infusionsrate berechnen (ng/kg/min -> µl/h)")
    st.write(
        "Berechnen Sie die Infusionsrate basierend auf dem Körpergewicht, der gewünschten Dosis (in ng/kg/min) und der Medikamentenkonzentration. Diese Berechnung ist gültig für die Apex Micro sc Infusionspumpe!")

    weight_infusionsrate = st.number_input(
        "Körpergewicht (kg):",
        min_value=0.0, value=70.0, step=0.1,
        help="Geben Sie das Gewicht der Person ein.",
        key="weight_infusionsrate"
    )
    dose_infusionsrate = st.number_input(
        "Gewünschte Dosis (ng/kg/min):",
        min_value=0.0, value=10.0, step=0.1,
        help="Geben Sie hier die gewünschte Dosis in ng/kg/min ein.",
        key="dose_infusionsrate"
    )
    concentration_infusionsrate = st.selectbox(
        "Konzentration des Medikaments (mg/ml):",
        [1, 2.5, 5, 10, 20],
        key="concentration_infusionsrate"
    )

    if st.button("Berechne Infusionsrate", key="infusionsrate"):
        if weight_infusionsrate > 0 and dose_infusionsrate > 0:
            infusion_rate = calculate_infusion_rate(weight_infusionsrate, dose_infusionsrate,
                                                    concentration_infusionsrate)
            st.success(f"Die berechnete Infusionsrate beträgt {infusion_rate:.2f} µl/h.")

            # Berechnung der Haltbarkeit des Reservoirs in Tagen
            reservoir_duration = calculate_reservoir_duration(infusion_rate)
            st.info(f"Das Reservoir hält bei dieser Infusionsrate ungefähr {reservoir_duration:.2f} Tage.")

            # Warnung, falls die Haltbarkeit die 14 Tage überschreitet
            if reservoir_duration > 14:
                st.warning(
                    "ACHTUNG: Die Haltbarkeit des Medikaments im Reservoir beträgt maximal 14 Tage. Wechseln Sie das Reservoir früher!")
        else:
            st.error("Gewicht und Dosis müssen größer als 0 sein.")

# Dosis berechnen
with tab2:
    st.markdown("### Dosis berechnen (µl/h -> ng/kg/min)")
    st.write("Berechnen Sie die Dosis in ng/kg/min basierend auf der Pumpenlaufrate und der Medikamentenkonzentration. Diese Berechnung ist gültig für die Apex Micro sc Infusionspumpe!")

    weight_dosisberechnung = st.number_input(
        "Körpergewicht (kg):",
        min_value=0.0, value=70.0, step=0.1,
        help="Geben Sie das Gewicht der Person ein.",
        key="weight_dosisberechnung"
    )
    infusion_rate_dosisberechnung = st.number_input(
        "Pumpenlaufrate (µl/h):",
        min_value=0.0, value=50.0, step=1.0,
        help="Geben Sie hier die aktuelle Pumpenlaufrate in µl/h ein.",
        key="infusion_rate_dosisberechnung"
    )
    concentration_dosisberechnung = st.selectbox(
        "Konzentration des Medikaments (mg/ml):",
        [1, 2.5, 5, 10, 20],
        key="concentration_dosisberechnung"
    )

    if st.button("Berechne Dosis", key="dosis"):
        if weight_dosisberechnung > 0 and infusion_rate_dosisberechnung > 0:
            dose = calculate_dose_from_infusion_rate(weight_dosisberechnung, infusion_rate_dosisberechnung,
                                                     concentration_dosisberechnung)
            st.success(f"Die berechnete Dosis beträgt {dose:.2f} ng/kg/min.")
        else:
            st.error("Gewicht und Laufrate müssen größer als 0 sein.")

# Perfusor-Laufrate berechnen
with tab3:
    st.markdown("### Perfusor Laufrate berechnen (ng/kg/min -> ml/h)")
    st.write(
        "Bestimmen Sie die Laufrate eines Perfusors (ml/h) basierend auf dem Gewicht, der gewünschten Dosis (ng/kg/min) und der verdünnten Medikamentenkonzentration. Die Berechnung erfolgt für einen Perfusor (50ml Perfusorspritze), der mit 1ml des Medikamentes und 49ml NaCl 0,9% aufgezogen ist! ")

    weight_perfusor = st.number_input(
        "Körpergewicht (kg):",
        min_value=0.0, value=70.0, step=0.1,
        help="Geben Sie das Gewicht der Person ein.",
        key="weight_perfusor"
    )
    dose_perfusor = st.number_input(
        "Gewünschte Dosis (ng/kg/min):",
        min_value=0.0, value=10.0, step=0.1,
        help="Geben Sie hier die gewünschte Dosis ein.",
        key="dose_perfusor"
    )
    concentration_perfusor = st.selectbox(
        "Konzentration des Medikaments (mg/ml):",
        [1, 2.5, 5, 10, 20],
        key="concentration_perfusor"
    )

    if st.button("Berechne Perfusor-Laufrate", key="perfusion"):
        if weight_perfusor > 0 and dose_perfusor > 0:
            perfusor_rate = calculate_perfusor_rate(weight_perfusor, dose_perfusor, concentration_perfusor)
            st.success(f"Die berechnete Perfusor-Laufrate beträgt {perfusor_rate:.2f} ml/h.")
        else:
            st.error("Gewicht und Dosis müssen größer als 0 sein.")

# Dosissteigerungsprotokoll erstellen und PDF exportieren
with tab4:
    st.markdown("### Dosissteigerungsprotokoll erstellen")
    st.write(
        "Erstellen Sie einen Plan zur schrittweisen Steigerung der Dosis bis zur Zieldosis unter Berücksichtigung der Reservoirkapazität und Vialwechsel.")

    weight_protokoll = st.number_input(
        "Körpergewicht (kg):",
        min_value=0.0, value=70.0, step=0.1,
        help="Geben Sie das Gewicht der Person ein.",
        key="weight_protokoll"
    )

    current_dose_protokoll = st.number_input(
        "Aktuelle Dosis (ng/kg/min):",
        min_value=0.0, value=5.0, step=0.1,
        help="Geben Sie hier die aktuelle Dosis des Patienten ein.",
        key="current_dose_protokoll"
    )

    target_dose_protokoll = st.number_input(
        "Zieldosis (ng/kg/min):",
        min_value=0.0, value=10.0, step=0.1,
        help="Geben Sie hier die Zieldosis des Patienten ein.",
        key="target_dose_protokoll"
    )

    weeks_protokoll = st.number_input(
        "Dauer der Steigerung (in Wochen):",
        min_value=1, value=4, step=1,
        help="Geben Sie hier die Anzahl der Wochen ein, über die die Dosis gesteigert werden soll.",
        key="weeks_protokoll"
    )

    increases_per_week_protokoll = st.number_input(
        "Anzahl der Steigerungen pro Woche:",
        min_value=1, value=2, step=1,
        help="Wie oft pro Woche soll die Dosis gesteigert werden?",
        key="increases_per_week_protokoll"
    )

    concentration_protokoll = st.selectbox(
        "Konzentration des Medikaments (mg/ml):",
        [1, 2.5, 5, 10, 20],
        key="concentration_protokoll"
    )

    if st.button("Dosissteigerungsprotokoll erstellen", key="steigerungsprotokoll"):
        protocol, vial_usage, reservoir_changes, reservoir_intervals = generate_dose_increase_protocol(
            current_dose_protokoll, target_dose_protokoll, weeks_protokoll, increases_per_week_protokoll,
            weight_protokoll, concentration_protokoll)

        # Ausgabe als Tabelle
        df = pd.DataFrame(protocol)
        st.write("### Dosissteigerungsprotokoll")
        st.dataframe(df)

        # Visualisierung des Protokolls in der App
        st.write("### Dosissteigerungsdiagramm mit Pumpenlaufrate und Reservoir-Inhalt")
        fig = plot_dose_infusion_rate_reservoir(protocol)
        st.pyplot(fig)  # Zeige das Diagramm in der App

        # Zusammenfassung des Protokolls
        summary = generate_summary(vial_usage, reservoir_changes, reservoir_intervals, weeks_protokoll)
        st.markdown(summary)

        # Button, um das PDF zu erstellen und herunterzuladen
        pdf_data = generate_pdf_with_graph(df, fig, summary)
        st.download_button(
            label="PDF herunterladen",
            data=pdf_data,
            file_name="dosissteigerungsprotokoll.pdf",
            mime="application/pdf"

        )
# Versionsinformation
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    '<p style="font-size:12px; color:red;">'
    'Treprostinil Dosisrechner (Beta Testversion für internen Gebrauch 1.01). Erstellt von Dr. Nils Kremer. Diese App dient ausschließlich zu Informationszwecken und ersetzt nicht die ärztliche Beratung, Diagnose oder Behandlung durch qualifizierte medizinische Fachkräfte. Alle Berechnungen sollten vor der Anwendung von einem Arzt überprüft werden!'
    '</p>',
    unsafe_allow_html=True
)