import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.preprocessing import MinMaxScaler
import matplotlib
from tensorflow.keras.layers import LSTM

# 한글 폰트 설정 (Windows 예: 맑은 고딕)
matplotlib.rcParams['font.family'] = 'Malgun Gothic'
# 마이너스 기호 깨짐 방지
matplotlib.rcParams['axes.unicode_minus'] = False

np.random.seed(42)
data = np.cumsum(np.random.randn(200)) + 100
df = pd.DataFrame(data, columns=['Alarm'])

df.plot(title='Alarm Count Time Series')

scaler = MinMaxScaler()
scaled_data = scaler.fit_transform(df)

def create_sequences(data, n_steps=10):
    x, y = [], []
    for i in range(len(data) - n_steps):
        x.append(data[i:i+n_steps])
        y.append(data[i+n_steps])
    return np.array(x), np.array(y)

n_steps = 10
x, y = create_sequences(scaled_data, n_steps)
print(f"입력 shape: {x.shape}, 출력 shape: {y.shape}")

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import SimpleRNN, Dense

#model = Sequential([
#    SimpleRNN(50, activation='tanh', input_shape=(n_steps, 1)),
#    Dense(1)
#])
model = Sequential([
    LSTM(50, activation='tanh', input_shape=(n_steps, 1)),
    Dense(1)
])

model.compile(optimizer='adam', loss='mse')
model.summary()

# 모델 학습
model.fit(x, y, epochs=30, batch_size=16, verbose=1)

# 마지막 시퀀스를 기반으로 미래 값 예측
last_seq = scaled_data[-n_steps:]
last_seq = last_seq.reshape((1, n_steps, 1))
predicted = model.predict(last_seq)

# 역변환
predicted_value = scaler.inverse_transform(predicted)
print(f"예측된 다음 알람 수: {predicted_value[0][0]:.2f}")

last_seq = scaled_data[-n_steps:]
last_seq = last_seq.reshape((1, n_steps, 1))
predicted = model.predict(last_seq)

predicted_value = scaler.inverse_transform(predicted)
print(f"예측된 다음 알람 수: {predicted_value[0][0]:.2f}")

preds = model.predict(x)
preds_inv = scaler.inverse_transform(preds)
y_inv = scaler.inverse_transform(y)

plt.plot(y_inv, label='True')
plt.plot(preds_inv, label='Predicted')
plt.title("RNN 시계열 예측 결과")
plt.legend()
plt.show()
