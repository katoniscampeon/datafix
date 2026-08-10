import io
import re
import numpy as np
import pandas as pd
import streamlit as st

# Ρύθμιση σελίδας
st.set_page_config(page_title="Excel Parsing & Value Calculator", layout="wide")


# Συνάρτηση για τον καθαρισμό των τιμών ευρώ (π.χ. "€ 2.535.998" -> 2535998.0)
def clean_value(val):
    if pd.isna(val):
        return None

    val_str = str(val).strip()

    # Αφαίρεση του € και άλλων συμβόλων νομίσματος/κενών
    val_str = re.sub(r"[^\d.,-]", "", val_str)

    if not val_str:
        return None

    # Διαχείριση μορφοποίησης αριθμών
    # Αν υπάρχει κόμμα και τελεία, υποθέτουμε Ευρωπαϊκή μορφή (π.χ. 2.535,99 -> 2535.99)
    if "." in val_str and "," in val_str:
        val_str = val_str.replace(".", "").replace(",", ".")
    elif "." in val_str:
        # Αν έχει μόνο τελείες, ελέγχουμε αν χρησιμοποιείται ως διαχωριστικό χιλιάδων
        # Αν η τελευταία τελεία έχει ακριβώς 3 ψηφία μετά, θεωρείται διαχωριστικό χιλιάδων (π.χ. 2.535.998)
        parts = val_str.split(".")
        if all(len(p) == 3 for p in parts[1:]):
            val_str = val_str.replace(".", "")
        else:
            # Αλλιώς θεωρείται αμερικανικό δεκαδικό (π.χ. 2535.99)
            pass
    elif "," in val_str:
        # Αν έχει μόνο κόμμα, το μετατρέπουμε σε τελεία για δεκαδικό
        val_str = val_str.replace(",", ".")

    try:
        return float(val_str)
    except ValueError:
        return None


# Τίτλος Εφαρμογής
st.title("📊 Excel String Parsing & Value Calculator")
st.write(
    "Ανέβασε τα δύο αρχεία Excel για να υπολογιστούν οι τιμές των keywords."
)

# Sidebar / Main Page για Upload των Αρχείων
col1, col2 = st.columns(2)

with col1:
    uploaded_keywords = st.file_uploader(
        "1. Αρχείο Keywords (Excel)", type=["xlsx"]
    )

with col2:
    uploaded_data = st.file_uploader("2. Αρχείο Data (Excel)", type=["xlsx"])

if uploaded_keywords and uploaded_data:
    try:
        # Διάβασμα των Excel
        df_keywords = pd.read_excel(uploaded_keywords)
        df_data = pd.read_excel(uploaded_data)

        st.success("Τα αρχεία ανέβηκαν με επιτυχία!")

        # Επιλογή Στηλών από τον χρήστη
        st.subheader("⚙️ Ρυθμίσεις Στηλών")
        col_sel1, col_sel2, col_sel3 = st.columns(3)

        with col_sel1:
            kw_col = st.selectbox(
                "Επίλεξε τη στήλη με τα Keywords:", df_keywords.columns
            )
        with col_sel2:
            text_col = st.selectbox(
                "Επίλεξε τη στήλη με τα Texts:", df_data.columns, index=0
            )
        with col_sel3:
            val_col = st.selectbox(
                "Επίλεξε τη στήλη με τα Values:",
                df_data.columns,
                index=1 if len(df_data.columns) > 1 else 0,
            )

        if st.button("🚀 Υπολογισμός"):
            # 1. Καθαρισμός Keywords
            df_keywords_clean = df_keywords.dropna(subset=[kw_col])
            keywords = [
                str(kw).strip()
                for kw in df_keywords_clean[kw_col].tolist()
                if str(kw).strip()
            ]

            if not keywords:
                st.error("Δεν βρέθηκαν έγκυρα keywords στο αρχείο.")
                st.stop()

            # Ταξινόμηση keywords κατά μήκος (φθίνουσα)
            keywords.sort(key=len, reverse=True)
            pattern = "|".join([re.escape(kw) for kw in keywords])

            A = []
            B = []

            # 2. Parsing των εγγραφών
            df_data_clean = df_data.dropna(subset=[text_col, val_col])

            for index, row in df_data_clean.iterrows():
                text = str(row[text_col])
                raw_val = row[val_col]

                # Καθαρισμός της τιμής
                total_val = clean_value(raw_val)

                if total_val is None:
                    continue  # Προσπέρασε γραμμές που δεν έχουν έγκυρο αριθμό

                matches = re.findall(pattern, text)
                counts = [matches.count(kw) for kw in keywords]

                A.append(counts)
                B.append(total_val)

            if not A:
                st.error(
                    "Δεν βρέθηκαν έγκυρα δεδομένα για επεξεργασία. Ελέγξτε αν οι τιμές στη στήλη Values είναι αριθμητικές."
                )
            else:
                A = np.array(A)
                B = np.array(B)

                # Επίλυση συστήματος (Least Squares)
                unit_values, residuals, rank, s = np.linalg.lstsq(
                    A, B, rcond=None
                )

                # Συνολικά αποτελέσματα
                total_occurrences = A.sum(axis=0)
                total_values = total_occurrences * unit_values

                # Δημιουργία DataFrame Αποτελεσμάτων
                df_results = pd.DataFrame(
                    {
                        "Keyword": keywords,
                        "Unit_Value": np.round(unit_values, 2),
                        "Total_Occurrences": total_occurrences,
                        "Total_Value": np.round(total_values, 2),
                    }
                )

                # Εμφάνιση Πίνακα στο Streamlit
                st.subheader("📈 Αποτελέσματα")
                st.dataframe(df_results, use_container_width=True)

                # Προετοιμασία για Download (Export σε Excel)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df_results.to_excel(
                        writer, index=False, sheet_name="Results"
                    )
                processed_data = output.getvalue()

                st.download_button(
                    label="📥 Λήψη Τελικού Excel",
                    data=processed_data,
                    file_name="parsed_results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

    except Exception as e:
        st.error(f"Προέκυψε σφάλμα κατά την επεξεργασία: {e}")
