import streamlit as st
import snowflake.connector
import pandas as pd
from datetime import datetime

# Streamlit setup
st.set_page_config(page_title="Founder Triage Dashboard", layout="wide")
st.title("🚨 Founder Assignment + Triage")

# Snowflake connection
@st.cache_resource
def get_conn():
    return snowflake.connector.connect(
        user=st.secrets["snowflake"]["user"],
        password=st.secrets["snowflake"]["password"],
        account=st.secrets["snowflake"]["account"],
        warehouse=st.secrets["snowflake"]["warehouse"],
        database=st.secrets["snowflake"]["database"],
        schema=st.secrets["snowflake"]["schema"],
        role=st.secrets["snowflake"]["role"]
    )

conn = get_conn()

# Load data from FOUNDERS_ALERT
@st.cache_data(ttl=0)
def load_data():
    df = pd.read_sql("SELECT * FROM AVIATO.ANALYTICS.FOUNDERS_ALERT", conn)
    df.columns = df.columns.str.lower()
    return df

df = load_data()

# Add stealth mode logic based on SQL-generated current_company_name
df["is_stealth"] = df["current_company_name"].str.strip().str.lower() == "stealth mode"

# Stealth mode filter
st.markdown("### 🔍 Filter by Company Type")
company_type = st.radio(
    "Show founders from:",
    options=["All", "Stealth Mode", "Non-Stealth Mode"],
    index=0,
    horizontal=True
)

if company_type == "Stealth Mode":
    df = df[df["is_stealth"]]
elif company_type == "Non-Stealth Mode":
    df = df[~df["is_stealth"]]

# Pagination setup
rows_per_page = st.selectbox("Rows per page:", [5, 10, 15], index=1)
total_rows = len(df)

if total_rows == 0:
    st.warning("⚠️ No results found for this filter.")
    st.stop()

total_pages = (total_rows + rows_per_page - 1) // rows_per_page

page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
start_idx = (page - 1) * rows_per_page
end_idx = min(start_idx + rows_per_page, total_rows)

paginated_df = df.iloc[start_idx:end_idx]

# Row-by-row UI
st.write("### Assign, Triage, and Take Notes:")
for i, row in paginated_df.iterrows():
    row_id = f"row_{i}"
    st.markdown(f"#### 👤 {row['fullname']} ({row['current_title']})")
    st.dataframe(pd.DataFrame([row]), use_container_width=True)

    triage_action = st.selectbox(
        "Triage Action", ["", "Yes", "No", "Tracking"], key=f"{row_id}_triage"
    )
    note = st.text_input("Note", key=f"{row_id}_note")
    assign_to = st.text_input("Assign To", key=f"{row_id}_assign")

    if st.button("Submit", key=f"{row_id}_submit"):
        if not triage_action:
            st.warning("Triage Action is required before submitting.")
        else:
            try:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO AVIATO.ANALYTICS.PEOPLE_ALERT_ASSIGNMENTS 
                    (fullname, linkedin_link, current_title, triage_action, note, assign_to, assigned_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    row["fullname"],
                    row["linkedin_link"],
                    row["current_title"],
                    triage_action,
                    note,
                    assign_to,
                    datetime.utcnow()
                ))
                conn.commit()
                st.success("✔️ Submission saved to Snowflake!")
            except Exception as e:
                st.error(f"❌ Submission failed: {e}")
                st.stop()
