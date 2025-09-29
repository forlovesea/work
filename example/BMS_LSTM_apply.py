import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler

# (1) 데이터 로드
df = pd.read_csv("D:/proj/bms_log.xls", encoding='ISO-8859-1')
#df = pd.read_excel("D:/proj/bms_log.xls", engine='openpyxl')

# (2) 날짜+시간 합쳐서 datetime으로 변환
df['Timestamp'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])

# (3) 시간 기준 정렬
df.sort_values('Timestamp', inplace=True)

# (4) 셀 전압 열만 추출 (예시로 4개 셀 사용)
voltage_cols = ['Cell1_V', 'Cell2_V', 'Cell3_V', 'Cell4_V']
voltage_data = df[voltage_cols].copy()

# (5) 정규화
scaler = MinMaxScaler()
scaled_data = scaler.fit_transform(voltage_data)

# (6) 시계열 샘플 만들기
def create_sequences(data, window_size):
    X, y = [], []
    for i in range(len(data) - window_size):
        X.append(data[i:i+window_size])
        y.append(np.mean(data[i+window_size]))  # 다음 시점의 평균 전압 예측
    return np.array(X), np.array(y)

# 시계열 입력 길이
window_size = 10
X, y = create_sequences(scaled_data, window_size)

print("✅ X shape:", X.shape)  # (샘플 수, 시점 수, 셀 수)
print("✅ y shape:", y.shape)  # (샘플 수,)
