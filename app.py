from flask import Flask, render_template, request, redirect, url_for, session
from db import get_connection
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

app = Flask(__name__)
app.secret_key = 'apmc_secret_key'

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            return render_template('register.html', error='Passwords do not match!')

        hashed = generate_password_hash(password)
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, hashed))
            conn.commit()
            return redirect(url_for('login'))
        except:
            return render_template('register.html', error='Username already exists!')
        finally:
            cursor.close()
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid username or password!')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM markets")
    markets = cursor.fetchall()

    recent_searches = session.get('recent_searches', [])

    cursor.close()
    conn.close()
    return render_template('dashboard.html', markets=markets, recent_searches=recent_searches)

@app.route('/get_commodities/<int:market_id>')
def get_commodities(market_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT c.id, c.commodity_name 
        FROM commodities c 
        JOIN daily_rates dr ON c.id = dr.commodity_id 
        WHERE dr.market_id = %s
    """, (market_id,))
    commodities = cursor.fetchall()
    cursor.close()
    conn.close()
    return {'commodities': [{'id': c[0], 'name': c[1]} for c in commodities]}

@app.route('/results')
def results():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    market_id = request.args.get('market_id')
    commodity_id = request.args.get('commodity_id')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.market_name, c.commodity_name, dr.rate_date, dr.min_rate, dr.max_rate
        FROM daily_rates dr
        JOIN markets m ON dr.market_id = m.id
        JOIN commodities c ON dr.commodity_id = c.id
        WHERE dr.market_id = %s AND dr.commodity_id = %s 
        AND dr.rate_date BETWEEN %s AND %s
        ORDER BY dr.rate_date ASC
    """, (market_id, commodity_id, from_date, to_date))
    rates = cursor.fetchall()
    cursor.close()
    conn.close()

    dates = [str(r[2]) for r in rates]
    min_rates = [float(r[3]) for r in rates if r[3] and float(r[3]) > 0]
    max_rates = [float(r[4]) for r in rates if r[4] and float(r[4]) > 0]
    all_rates = min_rates + max_rates

    lowest_price = round(min(min_rates), 2) if min_rates else 0
    highest_price = round(max(max_rates), 2) if max_rates else 0
    avg_price = round(sum(all_rates) / len(all_rates), 2) if all_rates else 0

    min_rates_chart = [float(r[3]) if r[3] else 0 for r in rates]
    max_rates_chart = [float(r[4]) if r[4] else 0 for r in rates]

    recent_searches = session.get('recent_searches', [])
    market_name = rates[0][0] if rates else ''
    commodity_name = rates[0][1] if rates else ''
    if rates:
        new_search = {
            'market_name': market_name,
            'commodity_name': commodity_name,
            'from_date': from_date,
            'to_date': to_date,
            'market_id': market_id,
            'commodity_id': commodity_id
        }
        if new_search not in recent_searches:
            recent_searches.insert(0, new_search)
            recent_searches = recent_searches[:5]
        session['recent_searches'] = recent_searches

    return render_template('results.html',
        rates=rates,
        dates=dates,
        min_rates=min_rates_chart,
        max_rates=max_rates_chart,
        lowest_price=lowest_price,
        highest_price=highest_price,
        avg_price=avg_price
    )

@app.route('/download')
def download():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    import io
    import openpyxl
    from flask import send_file
    market_id = request.args.get('market_id')
    commodity_id = request.args.get('commodity_id')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    file_type = request.args.get('file_type')
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.market_name, c.commodity_name, dr.rate_date, dr.min_rate, dr.max_rate
        FROM daily_rates dr
        JOIN markets m ON dr.market_id = m.id
        JOIN commodities c ON dr.commodity_id = c.id
        WHERE dr.market_id = %s AND dr.commodity_id = %s 
        AND dr.rate_date BETWEEN %s AND %s
        ORDER BY dr.rate_date ASC
    """, (market_id, commodity_id, from_date, to_date))
    rates = cursor.fetchall()
    cursor.close()
    conn.close()

    if file_type == 'csv':
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Market', 'Commodity', 'Date', 'Min Rate', 'Max Rate'])
        for r in rates:
            writer.writerow([r[0], r[1], r[2], r[3], r[4]])
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name='apmc_rates.csv'
        )
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'APMC Rates'
        ws.append(['Market', 'Commodity', 'Date', 'Min Rate', 'Max Rate'])
        for r in rates:
            ws.append([r[0], r[1], str(r[2]), float(r[3]) if r[3] else 0, float(r[4]) if r[4] else 0])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='apmc_rates.xlsx'
        )

@app.route('/trend')
def trend():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    market_id = request.args.get('market_id')
    commodity_id = request.args.get('commodity_id')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.market_name, c.commodity_name, dr.rate_date, dr.min_rate, dr.max_rate
        FROM daily_rates dr
        JOIN markets m ON dr.market_id = m.id
        JOIN commodities c ON dr.commodity_id = c.id
        WHERE dr.market_id = %s AND dr.commodity_id = %s 
        AND dr.rate_date BETWEEN %s AND %s
        ORDER BY dr.rate_date ASC
    """, (market_id, commodity_id, from_date, to_date))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame(rows, columns=['market_name', 'commodity_name', 'rate_date', 'min_rate', 'max_rate'])
    df['rate_date'] = pd.to_datetime(df['rate_date'])
    df['min_rate'] = pd.to_numeric(df['min_rate'], errors='coerce').fillna(0)
    df['max_rate'] = pd.to_numeric(df['max_rate'], errors='coerce').fillna(0)
    df['avg_rate'] = (df['min_rate'] + df['max_rate']) / 2

    monthly = df.groupby(df['rate_date'].dt.to_period('M')).agg(
        avg_price=('avg_rate', 'mean')
    ).reset_index()
    monthly['rate_date'] = monthly['rate_date'].astype(str)
    monthly['avg_price'] = monthly['avg_price'].round(2)

    yearly = df.groupby(df['rate_date'].dt.year).agg(
        avg_price=('avg_rate', 'mean')
    ).reset_index()
    yearly['avg_price'] = yearly['avg_price'].round(2)

    # Fix: get best and worst month separately
    best_idx = monthly['avg_price'].idxmax()
    worst_idx = monthly['avg_price'].idxmin()

    best_month = monthly.loc[best_idx, 'rate_date']
    best_month_price = monthly.loc[best_idx, 'avg_price']
    worst_month = monthly.loc[worst_idx, 'rate_date']
    worst_month_price = monthly.loc[worst_idx, 'avg_price']

    # Make sure they are different
    if best_month == worst_month:
        sorted_monthly = monthly.sort_values('avg_price')
        worst_month = sorted_monthly.iloc[0]['rate_date']
        worst_month_price = sorted_monthly.iloc[0]['avg_price']
        best_month = sorted_monthly.iloc[-1]['rate_date']
        best_month_price = sorted_monthly.iloc[-1]['avg_price']

    valid_min = df['min_rate'][df['min_rate'] > 0]

    trend_data = {
        'market_name': rows[0][0] if rows else '',
        'commodity_name': rows[0][1] if rows else '',
        'total_records': len(df),
        'overall_avg': round(df['avg_rate'].mean(), 2),
        'overall_min': round(valid_min.min(), 2) if not valid_min.empty else 0,
        'overall_max': round(df['max_rate'].max(), 2),
        'best_month': str(best_month),
        'best_month_price': round(float(best_month_price), 2),
        'worst_month': str(worst_month),
        'worst_month_price': round(float(worst_month_price), 2),
        'monthly_labels': monthly['rate_date'].tolist(),
        'monthly_avg': monthly['avg_price'].tolist(),
        'yearly_labels': yearly['rate_date'].tolist(),
        'yearly_avg': yearly['avg_price'].round(2).tolist(),
    }

    return render_template('trend.html', data=trend_data,
        market_id=market_id, commodity_id=commodity_id,
        from_date=from_date, to_date=to_date)

@app.route('/predict')
def predict():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    market_id = request.args.get('market_id')
    commodity_id = request.args.get('commodity_id')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.market_name, c.commodity_name, dr.rate_date, dr.min_rate, dr.max_rate
        FROM daily_rates dr
        JOIN markets m ON dr.market_id = m.id
        JOIN commodities c ON dr.commodity_id = c.id
        WHERE dr.market_id = %s AND dr.commodity_id = %s
        AND dr.rate_date BETWEEN %s AND %s
        ORDER BY dr.rate_date ASC
    """, (market_id, commodity_id, from_date, to_date))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame(rows, columns=['market_name', 'commodity_name', 'rate_date', 'min_rate', 'max_rate'])
    df['rate_date'] = pd.to_datetime(df['rate_date'])
    df['min_rate'] = pd.to_numeric(df['min_rate'], errors='coerce').fillna(0)
    df['max_rate'] = pd.to_numeric(df['max_rate'], errors='coerce').fillna(0)
    df['avg_rate'] = (df['min_rate'] + df['max_rate']) / 2
    df = df[df['avg_rate'] > 0]
    df['day_num'] = (df['rate_date'] - df['rate_date'].min()).dt.days

    total_records = len(df)

    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import PolynomialFeatures
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.pipeline import Pipeline
    from sklearn.metrics import mean_absolute_error, r2_score
    from sklearn.model_selection import train_test_split

    # Smart Auto-Select Model
    if total_records < 10:
        model_name = 'Linear Regression'
        model_desc = 'Used for very small datasets (< 10 records)'
        model_icon = '📏'

        X = df['day_num'].values.reshape(-1, 1)
        y_avg = df['avg_rate'].values
        y_min = df['min_rate'].values
        y_max = df['max_rate'].values

        m_avg = LinearRegression().fit(X, y_avg)
        m_min = LinearRegression().fit(X, y_min)
        m_max = LinearRegression().fit(X, y_max)

        last_day = df['day_num'].max()
        last_date = df['rate_date'].max()
        future_days = np.array([last_day + i for i in range(1, 31)]).reshape(-1, 1)

        pred_avg = m_avg.predict(future_days).round(2).tolist()
        pred_min = m_min.predict(future_days).round(2).tolist()
        pred_max = m_max.predict(future_days).round(2).tolist()

        # Accuracy
        if total_records >= 4:
            X_train, X_test, y_train, y_test = train_test_split(X, y_avg, test_size=0.2, random_state=42)
            m_eval = LinearRegression().fit(X_train, y_train)
            mae = round(mean_absolute_error(y_test, m_eval.predict(X_test)), 2)
            r2 = round(r2_score(y_test, m_eval.predict(X_test)) * 100, 2)
        else:
            mae = 'N/A'
            r2 = 'N/A'

    elif total_records < 30:
        model_name = 'Polynomial Regression'
        model_desc = 'Used for small datasets (10–30 records)'
        model_icon = '📐'

        X = df['day_num'].values.reshape(-1, 1)
        y_avg = df['avg_rate'].values
        y_min = df['min_rate'].values
        y_max = df['max_rate'].values

        m_avg = Pipeline([('poly', PolynomialFeatures(degree=2)), ('lr', LinearRegression())]).fit(X, y_avg)
        m_min = Pipeline([('poly', PolynomialFeatures(degree=2)), ('lr', LinearRegression())]).fit(X, y_min)
        m_max = Pipeline([('poly', PolynomialFeatures(degree=2)), ('lr', LinearRegression())]).fit(X, y_max)

        last_day = df['day_num'].max()
        last_date = df['rate_date'].max()
        future_days = np.array([last_day + i for i in range(1, 31)]).reshape(-1, 1)

        pred_avg = m_avg.predict(future_days).round(2).tolist()
        pred_min = m_min.predict(future_days).round(2).tolist()
        pred_max = m_max.predict(future_days).round(2).tolist()

        X_train, X_test, y_train, y_test = train_test_split(X, y_avg, test_size=0.2, random_state=42)
        m_eval = Pipeline([('poly', PolynomialFeatures(degree=2)), ('lr', LinearRegression())]).fit(X_train, y_train)
        mae = round(mean_absolute_error(y_test, m_eval.predict(X_test)), 2)
        r2 = round(r2_score(y_test, m_eval.predict(X_test)) * 100, 2)

    else:
        model_name = 'Random Forest'
        model_desc = 'Used for large datasets (30+ records)'
        model_icon = '🌲'

        df['lag_1'] = df['avg_rate'].shift(1)
        df['lag_7'] = df['avg_rate'].shift(7)
        df['lag_30'] = df['avg_rate'].shift(30)
        df['rolling_mean_7'] = df['avg_rate'].rolling(7).mean()
        df['rolling_mean_30'] = df['avg_rate'].rolling(30).mean()
        df['rolling_std_7'] = df['avg_rate'].rolling(7).std()
        df = df.dropna()

        features = ['day_num', 'lag_1', 'lag_7', 'lag_30', 'rolling_mean_7', 'rolling_mean_30', 'rolling_std_7']
        X = df[features].values
        y_avg = df['avg_rate'].values
        y_min = df['min_rate'].values
        y_max = df['max_rate'].values

        m_avg = RandomForestRegressor(n_estimators=100, random_state=42, max_depth=10).fit(X, y_avg)
        m_min = RandomForestRegressor(n_estimators=100, random_state=42, max_depth=10).fit(X, y_min)
        m_max = RandomForestRegressor(n_estimators=100, random_state=42, max_depth=10).fit(X, y_max)

        X_train, X_test, y_train, y_test = train_test_split(X, y_avg, test_size=0.2, random_state=42)
        m_eval = RandomForestRegressor(n_estimators=100, random_state=42, max_depth=10).fit(X_train, y_train)
        mae = round(mean_absolute_error(y_test, m_eval.predict(X_test)), 2)
        r2 = round(r2_score(y_test, m_eval.predict(X_test)) * 100, 2)

        last_day = df['day_num'].max()
        last_date = df['rate_date'].max()
        recent_avg = list(df['avg_rate'].values[-30:])
        recent_min = list(df['min_rate'].values[-30:])
        recent_max = list(df['max_rate'].values[-30:])

        future_dates_list = []
        pred_avg = []
        pred_min = []
        pred_max = []

        for i in range(1, 31):
            future_date = last_date + pd.Timedelta(days=i)
            future_dates_list.append(future_date.strftime('%Y-%m-%d'))
            day_num = last_day + i
            lag_1 = recent_avg[-1]
            lag_7 = recent_avg[-7] if len(recent_avg) >= 7 else recent_avg[0]
            lag_30 = recent_avg[-30] if len(recent_avg) >= 30 else recent_avg[0]
            rolling_mean_7 = np.mean(recent_avg[-7:])
            rolling_mean_30 = np.mean(recent_avg[-30:])
            rolling_std_7 = np.std(recent_avg[-7:])
            X_pred = np.array([[day_num, lag_1, lag_7, lag_30, rolling_mean_7, rolling_mean_30, rolling_std_7]])
            p_avg = round(float(m_avg.predict(X_pred)[0]), 2)
            p_min = round(float(m_min.predict(X_pred)[0]), 2)
            p_max = round(float(m_max.predict(X_pred)[0]), 2)
            pred_avg.append(p_avg)
            pred_min.append(p_min)
            pred_max.append(p_max)
            recent_avg.append(p_avg)

    if model_name != 'Random Forest':
        last_date = df['rate_date'].max()
        future_dates_list = [(last_date + pd.Timedelta(days=i)).strftime('%Y-%m-%d') for i in range(1, 31)]

    historical_dates = df['rate_date'].dt.strftime('%Y-%m-%d').tolist()
    historical_avg = df['avg_rate'].round(2).tolist()
    price_change = round(pred_avg[-1] - historical_avg[-1], 2)
    trend_direction = 'UP 📈' if price_change > 0 else 'DOWN 📉'
    trend_color = '#34d399' if price_change > 0 else '#fb7185'

    return render_template('predict.html',
        error=None,
        market_name=rows[0][0],
        commodity_name=rows[0][1],
        future_dates=future_dates_list,
        pred_avg=pred_avg,
        pred_min=pred_min,
        pred_max=pred_max,
        historical_dates=historical_dates,
        historical_avg=historical_avg,
        trend_direction=trend_direction,
        trend_color=trend_color,
        price_change=price_change,
        current_price=round(historical_avg[-1], 2),
        predicted_price_30=pred_avg[-1],
        mae=mae,
        r2=r2,
        model_name=model_name,
        model_desc=model_desc,
        model_icon=model_icon,
        total_records=total_records,
        market_id=market_id,
        commodity_id=commodity_id,
        from_date=from_date,
        to_date=to_date
    )

@app.route('/season')
def season():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    market_id = request.args.get('market_id')
    commodity_id = request.args.get('commodity_id')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.market_name, c.commodity_name, dr.rate_date, dr.min_rate, dr.max_rate
        FROM daily_rates dr
        JOIN markets m ON dr.market_id = m.id
        JOIN commodities c ON dr.commodity_id = c.id
        WHERE dr.market_id = %s AND dr.commodity_id = %s
        AND dr.rate_date BETWEEN %s AND %s
        ORDER BY dr.rate_date ASC
    """, (market_id, commodity_id, from_date, to_date))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame(rows, columns=['market_name', 'commodity_name', 'rate_date', 'min_rate', 'max_rate'])
    df['rate_date'] = pd.to_datetime(df['rate_date'])
    df['min_rate'] = pd.to_numeric(df['min_rate'], errors='coerce').fillna(0)
    df['max_rate'] = pd.to_numeric(df['max_rate'], errors='coerce').fillna(0)
    df['avg_rate'] = (df['min_rate'] + df['max_rate']) / 2
    df = df[df['avg_rate'] > 0]
    df['month'] = df['rate_date'].dt.month

    def get_season(month):
        if month in [12, 1, 2]:
            return 'Winter ❄️'
        elif month in [3, 4, 5]:
            return 'Summer ☀️'
        elif month in [6, 7, 8, 9]:
            return 'Monsoon 🌧️'
        else:
            return 'Autumn 🍂'

    df['season'] = df['month'].apply(get_season)

    season_stats = df.groupby('season').agg(
        avg_price=('avg_rate', 'mean'),
        min_price=('min_rate', 'min'),
        max_price=('max_rate', 'max'),
        total_records=('avg_rate', 'count')
    ).reset_index()
    season_stats['avg_price'] = season_stats['avg_price'].round(2)
    season_stats['min_price'] = season_stats['min_price'].round(2)
    season_stats['max_price'] = season_stats['max_price'].round(2)

    # Best price season = highest avg price (good for sellers)
    best_price_season = season_stats.loc[season_stats['avg_price'].idxmax()]

    # Peak supply season = lowest avg price (most supply, good for buyers)
    peak_supply_season = season_stats.loc[season_stats['avg_price'].idxmin()]

    monthly_avg = df.groupby('month')['avg_rate'].mean().round(2)
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    monthly_labels = [month_names[m-1] for m in monthly_avg.index]
    monthly_values = monthly_avg.values.tolist()

    season_labels = season_stats['season'].tolist()
    season_values = season_stats['avg_price'].tolist()
    seasons_list = season_stats.to_dict('records')

    return render_template('season.html',
        market_name=rows[0][0],
        commodity_name=rows[0][1],
        best_price_season=best_price_season['season'],
        best_price_season_value=best_price_season['avg_price'],
        peak_supply_season=peak_supply_season['season'],
        peak_supply_season_value=peak_supply_season['avg_price'],
        season_labels=season_labels,
        season_values=season_values,
        seasons_list=seasons_list,
        monthly_labels=monthly_labels,
        monthly_values=monthly_values,
        market_id=market_id,
        commodity_id=commodity_id,
        from_date=from_date,
        to_date=to_date
    )

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, created_at FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    recent_searches = session.get('recent_searches', [])
    total_searches = len(recent_searches)

    # Most searched market
    if recent_searches:
        from collections import Counter
        market_counts = Counter(s['market_name'] for s in recent_searches)
        commodity_counts = Counter(s['commodity_name'] for s in recent_searches)
        most_market = market_counts.most_common(1)[0][0]
        most_commodity = commodity_counts.most_common(1)[0][0]
    else:
        most_market = 'No searches yet'
        most_commodity = 'No searches yet'

    return render_template('profile.html',
        username=user[0],
        joined=user[1],
        recent_searches=recent_searches,
        total_searches=total_searches,
        most_market=most_market,
        most_commodity=most_commodity
    )

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
