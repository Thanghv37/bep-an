import pandas as pd
from datetime import datetime, date

from .models import MealRegistration


def clean_value(value):
    if pd.isna(value):
        return ''
    return str(value).strip()


def normalize_columns(df):
    df.columns = [
        str(col).replace('*', '').strip()
        for col in df.columns
    ]
    return df


def parse_date(value):
    if pd.isna(value) or value == '':
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    value = str(value).strip()

    formats = [
        '%d/%m/%Y',
        '%Y-%m-%d',
        '%d-%m-%Y',
        '%Y-%m-%d %H:%M:%S',
        '%d/%m/%Y %H:%M:%S',
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    try:
        parsed = pd.to_datetime(value, dayfirst=True, errors='coerce')
        if pd.notna(parsed):
            return parsed.date()
    except Exception:
        pass

    return None


def parse_int(value, default=1):
    try:
        if pd.isna(value) or value == '':
            return default
        return int(float(value))
    except Exception:
        return default


def import_registrations_from_excel(file):
    df = pd.read_excel(file, header=2, dtype=str)
    df = normalize_columns(df)

    created = 0
    updated = 0
    errors = []

    for index, row in df.iterrows():
        excel_row_number = index + 4

        try:
            employee_code = clean_value(row.get('Mã nhân viên'))
            full_name = clean_value(row.get('Họ và tên'))
            date_obj = parse_date(row.get('Ngày đặt cơm'))

            meal_name = clean_value(row.get('Bữa ăn'))
            kitchen_name = clean_value(row.get('Tên bếp ăn'))
            quantity = parse_int(row.get('Số suất đặt'), 1)
            status = clean_value(row.get('Trạng thái đặt cơm')) or clean_value(row.get('Trạng thái'))

            if not employee_code:
                errors.append(f'Dòng {excel_row_number}: Thiếu mã nhân viên.')
                continue

            if not date_obj:
                errors.append(f'Dòng {excel_row_number}: Thiếu hoặc sai ngày đặt cơm.')
                continue

            obj, is_created = MealRegistration.objects.update_or_create(
                employee_code=employee_code,
                date=date_obj,
                meal_name=meal_name,
                kitchen_name=kitchen_name,
                defaults={
                    'full_name': full_name,
                    'quantity': quantity,
                    'status': status,
                    'source': 'excel',
                }
            )

            if is_created:
                created += 1
            else:
                updated += 1

        except Exception as e:
            errors.append(f'Dòng {excel_row_number}: {str(e)}')

    return created, updated, errors