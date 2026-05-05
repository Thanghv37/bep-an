import pandas as pd
from django.contrib.auth.models import User
from accounts.models import UserProfile

from django.db import transaction
ROLE_MAP = {
    'ADMIN': UserProfile.ROLE_ADMIN,
    'KITCHEN': UserProfile.ROLE_KITCHEN,
    'DINER': UserProfile.ROLE_DINER,
    'BẾP': UserProfile.ROLE_KITCHEN,
    'NHÂN VIÊN BẾP': UserProfile.ROLE_KITCHEN,
    'NGƯỜI ĂN': UserProfile.ROLE_DINER,
}


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


@transaction.atomic
def import_users_from_excel(file):
    df = pd.read_excel(file, dtype=str)
    df = normalize_columns(df)

    created = 0
    updated = 0
    errors = []

    for index, row in df.iterrows():
        try:
            employee_code = clean_value(row.get('Mã nhân viên'))
            full_name = clean_value(row.get('Họ và tên'))
            email = clean_value(row.get('Email'))
            gender = clean_value(row.get('Giới tính'))
            unit = clean_value(row.get('Đơn vị'))
            department = clean_value(row.get('Phòng ban'))
            position = clean_value(row.get('Chức vụ'))
            phone = clean_value(row.get('Số điện thoại'))

            role_raw = clean_value(row.get('Role')).upper()
            role = ROLE_MAP.get(role_raw, UserProfile.ROLE_DINER)

            if not employee_code:
                employee_code = phone

            if not employee_code:
                errors.append(f"Dòng {index + 2}: Không có mã NV hoặc số điện thoại.")
                continue

            user, created_flag = User.objects.get_or_create(username=employee_code)

            user.first_name = full_name
            user.email = email
            user.is_staff = role in [UserProfile.ROLE_ADMIN, UserProfile.ROLE_KITCHEN]

            if created_flag:
                user.set_password(employee_code)

            user.save()

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.employee_code = employee_code
            profile.full_name = full_name
            profile.email = email
            profile.gender = gender
            profile.unit = unit
            profile.department = department
            profile.position = position
            profile.phone = phone
            profile.role = role
            profile.save()

            if created_flag:
                created += 1
            else:
                updated += 1

        except Exception as e:
            errors.append(f"Dòng {index + 2}: {str(e)}")

    return created, updated, errors