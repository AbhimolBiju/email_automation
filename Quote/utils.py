from datetime import timedelta
from django.utils.timezone import now

def get_date_filter(period):
    today = now()

    if period == "7days":
        return today - timedelta(days=7)
    elif period == "30days":
        return today - timedelta(days=30)
    elif period == "90days":
        return today - timedelta(days=90)
    elif period == "this_year":
        return today.replace(month=1, day=1)
    
    return None