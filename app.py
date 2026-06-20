from __future__ import annotations

from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st


REQUIRED_COLUMNS = {
    "страна": "country",
    "канал выплаты": "payment_channel",
    "сумма": "amount",
    "поставщик": "provider",
}


def normalize_column_name(value: object) -> str:
    """Normalize Excel headers so minor spelling whitespace does not break imports."""
    return " ".join(str(value).strip().lower().split())


def normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).strip().split())


def normalize_amount(value: object) -> float | None:
    if pd.isna(value):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    text = text.replace("\u00a0", " ").replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def format_amount(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value)}"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def prepare_dataframe(uploaded_file: BytesIO) -> pd.DataFrame:
    source = pd.read_excel(uploaded_file)
    normalized_columns = {column: normalize_column_name(column) for column in source.columns}
    source = source.rename(columns=normalized_columns)

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in source.columns]
    if missing_columns:
        missing = ", ".join(f"`{column}`" for column in missing_columns)
        raise ValueError(f"В Excel-файле не найдены обязательные столбцы: {missing}.")

    report_data = pd.DataFrame(
        {
            "country": source["страна"].map(normalize_text),
            "payment_channel": source["канал выплаты"].map(normalize_text),
            "provider": source["поставщик"].map(normalize_text),
            "amount": source["сумма"].map(normalize_amount),
        }
    )

    report_data = report_data.dropna(subset=["amount"])
    report_data = report_data[
        (report_data["country"] != "")
        & (report_data["payment_channel"] != "")
        & (report_data["provider"] != "")
    ]

    return report_data


def build_report(data: pd.DataFrame, report_date: date, report_period: str) -> str:
    grouped = (
        data.groupby(["country", "payment_channel", "provider"], sort=True)
        .agg(total_amount=("amount", "sum"), row_count=("amount", "size"))
        .reset_index()
    )

    lines = [
        f"Отчет по закрытым заявкам на выплаты за {report_date:%d.%m.%Y} {report_period}",
        "",
    ]

    for row in grouped.itertuples(index=False):
        lines.append(
            f"{row.country} ({row.payment_channel}): "
            f"{row.provider} - {format_amount(row.total_amount)} \\ {row.row_count} шт"
        )

    return "\n".join(lines)


def main() -> None:
    st.set_page_config(page_title="Отчет по выплатам")

    st.title("Отчет по закрытым заявкам на выплаты")
    st.write(
        "Загрузите Excel-файл, выберите дату отчёта и получите готовый текст "
        "с группировкой по стране, каналу выплаты и поставщику."
    )

    uploaded_file = st.file_uploader("Excel-файл", type=["xlsx", "xls"])
    report_date = st.date_input("Дата отчёта", value=date.today(), format="DD.MM.YYYY")
    report_period = st.text_input("Интервал в заголовке", value="с 9 до 15:00")

    if st.button("Сформировать отчёт", type="primary"):
        if uploaded_file is None:
            st.error("Загрузите Excel-файл перед формированием отчёта.")
            return

        try:
            data = prepare_dataframe(uploaded_file)
        except ValueError as error:
            st.error(str(error))
            return
        except Exception as error:
            st.error(f"Не удалось прочитать Excel-файл: {error}")
            return

        if data.empty:
            st.warning("После очистки данных не осталось строк для отчёта.")
            return

        report_text = build_report(data, report_date, report_period.strip())
        st.text_area("Готовый отчёт", value=report_text, height=300)
        st.download_button(
            "Скачать TXT",
            data=report_text.encode("utf-8"),
            file_name=f"report_{report_date:%Y-%m-%d}.txt",
            mime="text/plain",
        )


if __name__ == "__main__":
    main()
