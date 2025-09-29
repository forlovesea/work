import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense

# 1️⃣ 데이터 준비 (예제: 1000개 샘플, 20개 타임스텝, 3개 센서 값)
n_samples = 1000
timesteps = 20
n_features = 3  # 전압, 전류, 온도

# 랜덤 데이터 (실제로는 BMS에서 수집한 데이터로 교체)
X = np.random.rand(n_samples, timesteps, n_features)
y = np.random.randint(0, 2, n_samples)  # 0=정상, 1=장애

# 2️⃣ LSTM 모델 구성
model = Sequential()
model.add(LSTM(64, input_shape=(timesteps, n_features)))
model.add(Dense(1, activation='sigmoid'))  # 이진 분류

# 3️⃣ 컴파일
model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])

# 4️⃣ 학습
history = model.fit(X, y, epochs=10, batch_size=32, validation_split=0.2)

# 5️⃣ 예측
predictions = model.predict(X[:5])
print("예측 결과 (앞 5개 샘플):", predictions)

# 6️⃣ 모델 저장
model.save('bms_lstm_model.h5')

