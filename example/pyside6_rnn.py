import sys
import numpy as np
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget
)
from PySide6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import SimpleRNN, Dense
import matplotlib

# 한글 폰트 설정 (Windows 예: 맑은 고딕)
matplotlib.rcParams['font.family'] = 'Malgun Gothic'
# 마이너스 기호 깨짐 방지
matplotlib.rcParams['axes.unicode_minus'] = False

class RNNPredictor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RNN 알람 예측기")
        self.setGeometry(100, 100, 600, 400)

        self.scaler = MinMaxScaler()
        self.n_steps = 10
        self.model = None
        self.data = self.generate_data()
        self.X, self.y = self.preprocess(self.data)

        self.initUI()
        self.train_model()

    def initUI(self):
        self.label = QLabel("예측 결과: 미실행", self)
        self.label.setAlignment(Qt.AlignCenter)
        self.button = QPushButton("알람 수 예측", self)
        self.button.clicked.connect(self.predict_next)

        self.figure = Figure(figsize=(5, 3))
        self.canvas = FigureCanvas(self.figure)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.button)
        layout.addWidget(self.canvas)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def generate_data(self):
        np.random.seed(42)
        data = np.cumsum(np.random.randn(200)) + 100
        df = pd.DataFrame(data, columns=["Alarm"])
        return df

    def preprocess(self, df):
        scaled = self.scaler.fit_transform(df)
        X, y = [], []
        for i in range(len(scaled) - self.n_steps):
            X.append(scaled[i:i+self.n_steps])
            y.append(scaled[i+self.n_steps])
        return np.array(X), np.array(y)

    def train_model(self):
        self.model = Sequential([
            SimpleRNN(50, activation='tanh', input_shape=(self.n_steps, 1)),
            Dense(1)
        ])
        self.model.compile(optimizer='adam', loss='mse')
        self.model.fit(self.X, self.y, epochs=20, batch_size=16, verbose=0)

    def predict_next(self):
        last_seq = self.scaler.transform(self.data)[-self.n_steps:]
        last_seq = last_seq.reshape((1, self.n_steps, 1))
        predicted_scaled = self.model.predict(last_seq, verbose=0)
        predicted = self.scaler.inverse_transform(predicted_scaled)
        predicted_value = predicted[0][0]

        self.label.setText(f"예측된 다음 알람 수: {predicted_value:.2f}")
        self.update_plot(predicted_value)

    def update_plot(self, predicted_value):
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        true_vals = self.data["Alarm"].values[-20:]
        x_vals = np.arange(len(true_vals) + 1)
        y_vals = np.concatenate([true_vals, [predicted_value]])

        ax.plot(x_vals[:-1], true_vals, label="실제 알람 수")
        ax.plot(x_vals, y_vals, '--o', label="예측 포함", color='orange')
        ax.set_title("알람 수 예측 결과")
        ax.legend()
        self.canvas.draw()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RNNPredictor()
    window.show()
    sys.exit(app.exec())
