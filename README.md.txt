# 🌾 APMC Market Information System

A full-stack ML-powered web application for tracking
and predicting agricultural commodity prices across
APMC markets.

## 🚀 Features
- 🔐 User Authentication (Register/Login)
- 📊 Market & Commodity Price Search
- 📈 Price Trend Analysis
- 🤖 ML Price Prediction (Auto-Select Model)
- 📅 Season Analysis (Buy/Sell Guide)
- 📥 Export Data (CSV & Excel)
- 👤 User Profile Page

## 🤖 ML Models Used
- Linear Regression (< 10 records)
- Polynomial Regression (10-30 records)
- Random Forest (30+ records)

## 🛠️ Tech Stack
- Backend: Python Flask
- Database: MySQL
- ML: Scikit-learn, Pandas, NumPy
- Frontend: Bootstrap 5, Chart.js, Jinja2

## ⚙️ Installation

1. Clone the repository
git clone https://github.com/YOUR_USERNAME/apmc-website.git
cd apmc-website

2. Install dependencies
pip install flask mysql-connector-python werkzeug pandas numpy scikit-learn openpyxl reportlab gunicorn

3. Import database
Open phpMyAdmin
Create database named: apmc
Import apmc.sql file

4. Run the app
python app.py

5. Open browser
http://localhost:5000

## 📁 Project Structure
apmc-website/
├── app.py
├── db.py
├── requirements.txt
├── apmc.sql
├── static/
│   └── style.css
└── templates/
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── results.html
    ├── trend.html
    ├── predict.html
    ├── season.html
    └── profile.html