from flask import Flask, request, jsonify
import requests
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# --- НАЛАШТУВАННЯ ---
USER = "dudaryeva"
PATH_TO_JSON = f'/home/{USER}/credentials.json'
SHEET_URL = 'https://docs.google.com/spreadsheets/d/1UoxVucYufs-typw0HVARdKODY1XKtQHSPUPGNsY0cjE/edit?gid=0'

def get_usd_rate(date_obj):
    """Отримує курс USD від НБУ на певну дату"""
    date_str = date_obj.strftime('%Y%m%d')
    url = f"https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?valcode=USD&date={date_str}&json"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if data and isinstance(data, list) and len(data) > 0:
            return data[0]['rate']
        return None
    except Exception:
        return None

@app.route('/update_rates', methods=['GET'])
def update_rates():
    # 1. Отримуємо дати з параметрів URL. За замовчуванням — сьогодні.
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    u_from_str = request.args.get('update_from', today_str)
    u_to_str = request.args.get('update_to', today_str)

    try:
        # 2. Конвертуємо рядки у об'єкти дати
        start_dt = datetime.datetime.strptime(u_from_str, '%Y-%m-%d').date()
        end_dt = datetime.datetime.strptime(u_to_str, '%Y-%m-%d').date()

        # 3. Авторизація в Google Sheets
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(PATH_TO_JSON, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SHEET_URL).sheet1

        # 4. Збір даних про курси за вказаний період
        results = []
        current = start_dt
        while current <= end_dt:
            rate = get_usd_rate(current)
            if rate:
                # Додаємо дату як рядок та курс
                results.append([str(current), rate])
            current += datetime.timedelta(days=1)

        # 5. Оновлення Google Таблиці
        if results:
            # ОЧИЩЕННЯ: Видаляємо всі старі дані з листа
            sheet.clear()

            # ПІДГОТОВКА ДАНИХ: Додаємо заголовки першим рядком
            header = ["Date", "Rate"]
            data_to_upload = [header] + results

            # ЗАПИС: Оновлюємо таблицю пакетно, починаючи з клітинки A1
            sheet.update('A1', data_to_upload)

            return jsonify({
                "status": "success",
                "message": "Sheet cleared and rewritten with new data",
                "rows_added": len(results),
                "period": f"{u_from_str} to {u_to_str}"
            }), 200
        else:
            return jsonify({
                "status": "warning", 
                "message": "No rate data found for the given period"
            }), 200

    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500

if __name__ == '__main__':
    # Для локального тестування (на PythonAnywhere керується через WSGI)
    app.run(debug=True)