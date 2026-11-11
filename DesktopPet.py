
import sys
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QPoint
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QWidget, QMenu
from pynput import keyboard, mouse


# ==============================
# 遊戲設定
# ==============================

PET_WIDTH = 300
PET_HEIGHT = 300

# 幾秒沒有操作後開始打瞌睡
SLEEP_AFTER = 15

# 睡眠動畫每張圖片間隔（毫秒）
SLEEP_FRAME_MS = 250

# 鍵盤動畫持續時間（秒）
KEYBOARD_ACTION_TIME = 0.18

# 滑鼠移動動畫持續時間（秒）
MOUSE_MOVE_TIME = 0.15

# 滑鼠移動判定門檻（像素）
MOUSE_MOVE_THRESHOLD = 4

ASSETS = Path(__file__).resolve().parent / "assets"


class DesktopPet(QWidget):

    # 將監聽事件安全地傳送到 Qt 主執行緒
    input_event = Signal(str)

    def __init__(self):
        super().__init__()

        # ==============================
        # 視窗設定
        # ==============================

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        self.setFixedSize(PET_WIDTH, PET_HEIGHT)

        screen = QApplication.primaryScreen().availableGeometry()

        self.move(
            screen.right() - PET_WIDTH - 30,
            screen.bottom() - PET_HEIGHT - 30
        )

        # ==============================
        # 角色狀態
        # ==============================

        self.state = "idle"

        self.last_activity = time.monotonic()
        self.action_until = 0

        self.keyboard_frame = 0
        self.sleep_frame = 0

        self.drag_offset = None
        self.dragging = False

        self.left_pressed = False
        self.right_pressed = False

        self.last_mouse_x = None

        # ==============================
        # 圖片載入
        # ==============================

        self.images = {}

        image_paths = {
            "idle": "idle/idle.png",

            "mouse_left": "mouse/mouse_move_left.png",
            "mouse_right": "mouse/mouse_move_right.png",

            "click_left": "mouse/mouse_click_left.png",
            "click_right": "mouse/mouse_click_right.png",
        }

        for name, relative_path in image_paths.items():
            self.load_image(name, relative_path)

        for i in range(1, 4):
            self.load_image(
                f"keyboard_{i}",
                f"keyboard/keyboard_press_{i}.png"
            )

        for i in range(1, 9):
            self.load_image(
                f"sleep_{i}",
                f"sleep/sleep_{i}.png"
            )

        # ==============================
        # 事件接收
        # ==============================

        self.input_event.connect(self.handle_input)

        # ==============================
        # 主更新計時器
        # ==============================

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_game)
        self.timer.start(30)

        # ==============================
        # 睡眠動畫計時器
        # ==============================

        self.sleep_timer = QTimer(self)
        self.sleep_timer.timeout.connect(
            self.next_sleep_frame
        )
        self.sleep_timer.setInterval(SLEEP_FRAME_MS)

        # ==============================
        # 全域鍵盤與滑鼠監聽
        # ==============================

        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_key_press
        )

        self.mouse_listener = mouse.Listener(
            on_move=self.on_mouse_move,
            on_click=self.on_mouse_click
        )

        self.keyboard_listener.start()
        self.mouse_listener.start()

    # ==============================
    # 載入圖片
    # ==============================

    def load_image(self, name, relative_path):

        path = ASSETS / relative_path
        image = QPixmap(str(path))

        if image.isNull():
            print(f"找不到圖片：{path}")

        self.images[name] = image

    # ==============================
    # 鍵盤監聽
    # ==============================

    def on_key_press(self, key):

        # 不讀取或儲存實際輸入內容
        self.input_event.emit("keyboard")

    # ==============================
    # 滑鼠移動監聽
    # ==============================

    def on_mouse_move(self, x, y):

        if self.last_mouse_x is None:
            self.last_mouse_x = x
            return

        dx = x - self.last_mouse_x
        self.last_mouse_x = x

        if abs(dx) < MOUSE_MOVE_THRESHOLD:
            return

        if dx > 0:
            self.input_event.emit("mouse_right")
        else:
            self.input_event.emit("mouse_left")

    # ==============================
    # 滑鼠點擊監聽
    # ==============================

    def on_mouse_click(self, x, y, button, pressed):

        if button == mouse.Button.left:

            if pressed:
                self.input_event.emit("left_down")
            else:
                self.input_event.emit("left_up")

        elif button == mouse.Button.right:

            if pressed:
                self.input_event.emit("right_down")
            else:
                self.input_event.emit("right_up")

    # ==============================
    # 統一處理事件
    # ==============================

    def handle_input(self, event):

        now = time.monotonic()

        self.last_activity = now

        # 任何操作都可以喚醒角色
        if self.sleep_timer.isActive():
            self.sleep_timer.stop()
            self.sleep_frame = 0
            self.state = "idle"

        # 滑鼠左鍵按下
        if event == "left_down":

            self.left_pressed = True
            self.state = "click_left"
            self.update()
            return

        # 滑鼠左鍵放開
        if event == "left_up":

            self.left_pressed = False

            if self.right_pressed:
                self.state = "click_right"
            else:
                self.state = "idle"

            self.update()
            return

        # 滑鼠右鍵按下
        if event == "right_down":

            self.right_pressed = True
            self.state = "click_right"
            self.update()
            return

        # 滑鼠右鍵放開
        if event == "right_up":

            self.right_pressed = False

            if self.left_pressed:
                self.state = "click_left"
            else:
                self.state = "idle"

            self.update()
            return

        # 按住滑鼠按鍵時，優先顯示點擊動畫
        if self.left_pressed or self.right_pressed:
            return

        # 鍵盤輸入
        if event == "keyboard":

            self.keyboard_frame = (
                self.keyboard_frame % 3
            ) + 1

            self.state = f"keyboard_{self.keyboard_frame}"

            self.action_until = (
                now + KEYBOARD_ACTION_TIME
            )

        # 滑鼠移動
        elif event == "mouse_left":

            self.state = "mouse_left"

            self.action_until = (
                now + MOUSE_MOVE_TIME
            )

        elif event == "mouse_right":

            self.state = "mouse_right"

            self.action_until = (
                now + MOUSE_MOVE_TIME
            )

        self.update()

    # ==============================
    # 遊戲狀態更新
    # ==============================

    def update_game(self):

        now = time.monotonic()

        # 已經進入睡眠動畫
        if self.sleep_timer.isActive():
            return

        # 判斷是否閒置太久
        if now - self.last_activity >= SLEEP_AFTER:

            self.state = "sleep_1"
            self.sleep_frame = 1

            self.sleep_timer.start()
            self.update()
            return

        # 滑鼠按住時不重設動畫
        if self.left_pressed or self.right_pressed:
            return

        # 動作時間結束後恢復待機
        if self.state != "idle" and now >= self.action_until:

            self.state = "idle"
            self.update()

    # ==============================
    # 睡眠動畫播放
    # ==============================

    def next_sleep_frame(self):

        self.sleep_frame += 1

        if self.sleep_frame > 8:
            self.sleep_frame = 1

        self.state = f"sleep_{self.sleep_frame}"

        self.update()

    # ==============================
    # 繪製角色
    # ==============================

    def paintEvent(self, event):

        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform
        )

        image = self.images.get(self.state)

        if image is None or image.isNull():
            image = self.images.get("idle")

        if image is not None and not image.isNull():

            scaled = image.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2

            painter.drawPixmap(x, y, scaled)

        painter.end()

    # ==============================
    # 拖曳角色
    # ==============================

    def mousePressEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:

            self.drag_offset = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )

            self.dragging = True

    def mouseMoveEvent(self, event):

        if self.dragging and self.drag_offset is not None:

            self.move(
                event.globalPosition().toPoint()
                - self.drag_offset
            )

    def mouseReleaseEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.drag_offset = None

    # ==============================
    # 右鍵選單
    # ==============================

    def contextMenuEvent(self, event):

        menu = QMenu(self)

        quit_action = menu.addAction("退出桌面寵物")

        selected = menu.exec(event.globalPos())

        if selected == quit_action:
            self.close()

    # ==============================
    # 關閉程式
    # ==============================

    def closeEvent(self, event):

        self.keyboard_listener.stop()
        self.mouse_listener.stop()

        self.timer.stop()
        self.sleep_timer.stop()

        super().closeEvent(event)


# ==============================
# 啟動遊戲
# ==============================

if __name__ == "__main__":

    app = QApplication(sys.argv)

    pet = DesktopPet()
    pet.show()

    sys.exit(app.exec())
