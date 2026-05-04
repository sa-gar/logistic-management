import streamlit as st
import pandas as pd

st.set_page_config(page_title="Material Price Comparison", layout="wide")

st.title("Material Price Comparison Software")

uploaded_file = st.file_uploader("Upload Excel or CSV file", type=["xlsx", "xls", "csv"])

if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    df.columns = df.columns.astype(str).str.strip()

    st.subheader("Uploaded Data")
    st.dataframe(df, use_container_width=True)

    search_text = st.text_input("Search Project / Dealer / Item / Material")

    if search_text:
        mask = df.apply(
            lambda row: row.astype(str).str.contains(search_text, case=False, na=False).any(),
            axis=1
        )
        filtered_df = df[mask]
    else:
        filtered_df = df

    st.subheader("Filtered Data")
    st.dataframe(filtered_df, use_container_width=True)

    price_column = st.selectbox("Select price column", df.columns)

    item_column = st.selectbox("Select material/item column", df.columns)

    selected_items = st.multiselect(
        "Select materials/items to compare",
        filtered_df[item_column].dropna().astype(str).unique()
    )

    if selected_items:
        compare_df = filtered_df[
            filtered_df[item_column].astype(str).isin(selected_items)
        ]

        st.subheader("Price Comparison")
        st.dataframe(compare_df, use_container_width=True)

        chart_df = compare_df.copy()
        chart_df[price_column] = pd.to_numeric(chart_df[price_column], errors="coerce")

        chart_df = chart_df.dropna(subset=[price_column])

        if not chart_df.empty:
            st.bar_chart(
                chart_df.set_index(item_column)[price_column]
            )
        else:
            st.warning("Selected price column does not contain numeric values.")
else:
    st.info("Please upload your Excel or CSV file.")