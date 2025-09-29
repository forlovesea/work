import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller
import matplotlib
from pmdarima import auto_arima

# 한글 폰트 설정 (Windows 예: 맑은 고딕)
matplotlib.rcParams['font.family'] = 'Malgun Gothic'
# 마이너스 기호 깨짐 방지
matplotlib.rcParams['axes.unicode_minus'] = False

# 날짜별 알람 발생 수 예시
np.random.seed(42)
dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
data = np.cumsum(np.random.randn(100)) + 50  # 누적 랜덤값

df = pd.DataFrame({'Date': dates, 'AlarmCount': data})
df.set_index('Date', inplace=True)

# Augmented Dickey-Fuller Test
result = adfuller(df['AlarmCount'])
print(f'ADF Statistic: {result[0]}')
print(f'p-value: {result[1]}')

if result[1] < 0.05:
    print("✅ 정상 시계열입니다.")
else:
    print("⚠️ 비정상 시계열입니다. 차분이 필요합니다.")
    df['diff'] = df['AlarmCount'].diff()
    #df['diff'].dropna().plot(title='1차 차분된 알람 발생 수')

# ARIMA(p=1, d=1, q=1) 예시
model = ARIMA(df['AlarmCount'], order=(1, 1, 1))  # (AR, 차분, MA)
model_fit = model.fit()

# 요약 출력
print(model_fit.summary())

# 10일 후까지 예측
forecast = model_fit.forecast(steps=10)

# 결과 시각화
df['AlarmCount'].plot(label='Observed', figsize=(10, 5))
forecast.index = pd.date_range(start=df.index[-1] + pd.Timedelta(days=1), periods=10)
forecast.plot(label='Forecast', style='--')

auto_model = auto_arima(df['AlarmCount'], seasonal=False, trace=True)
print(auto_model.summary())

# 10일 후까지 예측
forecast = model_fit.forecast(steps=10)

# 결과 시각화
df['AlarmCount'].plot(label='Observed', figsize=(10, 5))
forecast.index = pd.date_range(start=df.index[-1] + pd.Timedelta(days=1), periods=10)
forecast.plot(label='Forecast', style='--')

from pmdarima import auto_arima

auto_model = auto_arima(df['AlarmCount'], seasonal=False, trace=True)
print(auto_model.summary())

plt.legend()
plt.title("ARIMA 기반 알람 수 예측")
plt.show()
