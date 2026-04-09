from datetime import date
    
def calculate_tax_year(date_obj : date):
    """
    Calculate the UK tax year from a date
    
    Returns tax year string (e.g. 2025/2026)
    """
    year = date_obj.year
    # Tax year starts on April 6th
    if date_obj >= date(year, 4, 6):
        return f"{year}/{year + 1}"
    else:
        return f"{year - 1}/{year}"