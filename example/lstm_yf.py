import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
import yfinance as yf 
import os

# 옵션 1: CSV 파일에서 주가 데이터 로드

data = pd.read_csv('D:\proj\GIT_HUB\work\AAPL.csv')
data['Date'] = pd.to_datetime(data['Date'])
data.set_index('Date', inplace=True)
data = data[['Close']] 

# 옵션 2: 외부 소스에서 주가 데이터 가져오기
# ticker = 'AAPL'
# data = yf.download(ticker, start='2020-01-01', end='2023-01-01')
# data = data[['Close']] 


# 데이터 플롯
plt.figure(figsize=(14, 5))
plt.plot(data)
plt.title('시간에 따른 주가')
plt.xlabel('날짜')
plt.ylabel('가격')
plt.show() 

# 데이터 정규화
scaler = MinMaxScaler(feature_range=(0, 1))
scaled_data = scaler.fit_transform(data)

"""
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import os

# 티커와 기간 설정
ticker = 'AAPL'
start_date = '2022-01-01'
end_date = '2025-01-01'

# 데이터 다운로드
data = yf.download(ticker, start=start_date, end=end_date)

# Close 가격만 선택
close_data = data[['Close']]
print(close_data)

# 현재 폴더 경로 확인
current_folder = os.getcwd()

# CSV 파일로 저장 (현재 폴더에 저장)
csv_filename = os.path.join(current_folder, f'{ticker}_close_data.csv')
close_data.to_csv(csv_filename)
print(f'데이터가 CSV 파일로 저장되었습니다: {csv_filename}')

# 그래프 그리기
close_data.plot(title=f'{ticker} Closing Price')
plt.xlabel('Date')
plt.ylabel('Price')
plt.show()_summary_
"""