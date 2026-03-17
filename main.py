import math
import random
import time

import M5
from M5 import *


FRAME_DIR_CANDIDATES = (
    "res/dice",
    "/flash/res/dice",
    "/res/dice",
)
FRAME_COUNT = 36

SCREEN_W = 320
SCREEN_H = 240
BG_COLOR = 0x10151C
TEXT_COLOR = 0xF5F7FA
ACCENT_COLOR = 0x56C7FF
SUBTEXT_COLOR = 0xA8B3C2

DICE_SIZE = 168
BASE_X = (SCREEN_W - DICE_SIZE) // 2
BASE_Y = 36
TOP_BAR_H = 42
BOTTOM_BAR_Y = 210
BOTTOM_BAR_H = 30

FOLLOW_GAIN = 14
MAX_OFFSET = 18
LPF = 0.84
SHAKE_DELTA_THRESHOLD = 0.32
SHAKE_SCORE_TRIGGER = 1.15
SHAKE_SCORE_DECAY = 0.08
ROLL_COOLDOWN_MS = 1200
STAGE_X = BASE_X - MAX_OFFSET - 6
STAGE_Y = BASE_Y - MAX_OFFSET - 6
STAGE_W = DICE_SIZE + MAX_OFFSET * 2 + 12
STAGE_H = DICE_SIZE + MAX_OFFSET * 2 + 12

ROLL_MIN_STEPS = 56
ROLL_MAX_STEPS = 88
FRAME_DELAY_MIN_MS = 18
FRAME_DELAY_MAX_MS = 54

DEBUG_STATE_PATH = "dice_debug_state.txt"
DEBUG_LOG_PATH = "dice_debug_log.txt"

frame_dir = FRAME_DIR_CANDIDATES[0]
cur_frame = 0
result_value = 1
result_visible = False
status_text = "SHAKE or TOUCH"
rolling = False

ax_f = 0.0
ay_f = 0.0
last_mag = 1.0
shake_score = 0.0
last_roll_ms = 0
touch_is_down = False
touch_count = 0
loop_count = 0
last_jerk = 0.0
last_touch_seen = 0
last_debug_flush_ms = 0


def debug_log(message):
    try:
        f = open(DEBUG_LOG_PATH, "a")
        f.write("%s\n" % message)
        f.close()
    except Exception:
        pass


def write_debug_state(extra=""):
    try:
        f = open(DEBUG_STATE_PATH, "w")
        f.write("frame_dir=%s\n" % frame_dir)
        f.write("loop_count=%d\n" % loop_count)
        f.write("touch_count=%d\n" % touch_count)
        f.write("rolling=%s\n" % rolling)
        f.write("cur_frame=%d\n" % cur_frame)
        f.write("result_value=%d\n" % result_value)
        f.write("last_jerk=%.4f\n" % last_jerk)
        f.write("shake_score=%.4f\n" % shake_score)
        f.write("last_touch_seen=%d\n" % last_touch_seen)
        if extra:
            f.write("extra=%s\n" % extra)
        f.close()
    except Exception:
        pass


def frame_path(idx):
    return "%s/spin_%03d.png" % (frame_dir, idx % FRAME_COUNT)


def file_exists(path):
    try:
        with open(path, "rb"):
            return True
    except OSError:
        return False


def resolve_frame_dir():
    global frame_dir

    for candidate in FRAME_DIR_CANDIDATES:
        if file_exists("%s/spin_000.png" % candidate):
            frame_dir = candidate
            return True
    return False


def clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def ease_out_cubic(t):
    return 1.0 - (1.0 - t) ** 3


def draw_hud():
    M5.Lcd.fillRect(0, 0, SCREEN_W, TOP_BAR_H, BG_COLOR)
    M5.Lcd.setTextSize(2)
    M5.Lcd.setTextColor(ACCENT_COLOR, BG_COLOR)
    M5.Lcd.drawString("3D Dice", 10, 10)
    draw_status_line()
    draw_result_value()


def draw_status_line():
    M5.Lcd.fillRect(0, BOTTOM_BAR_Y, SCREEN_W, BOTTOM_BAR_H, BG_COLOR)
    M5.Lcd.setTextSize(1)
    M5.Lcd.setTextColor(SUBTEXT_COLOR, BG_COLOR)
    M5.Lcd.drawString(status_text, 10, 220)


def set_status(message):
    global status_text
    status_text = message
    draw_status_line()


def set_result(value):
    global result_value
    result_value = value
    draw_result_value()


def set_result_visible(visible):
    global result_visible
    result_visible = visible
    draw_result_value()


def draw_result_value():
    M5.Lcd.fillRect(252, 4, 60, 34, BG_COLOR)
    if not result_visible:
        return

    panel_x = 258
    panel_y = 7
    panel_w = 50
    panel_h = 28
    panel_bg = 0x15202C

    M5.Lcd.fillRoundRect(panel_x, panel_y, panel_w, panel_h, 12, panel_bg)
    M5.Lcd.drawRoundRect(panel_x, panel_y, panel_w, panel_h, 12, 0x31495E)
    M5.Lcd.setTextColor(TEXT_COLOR, panel_bg)
    M5.Lcd.setTextSize(3)
    M5.Lcd.drawString(str(result_value), panel_x + 14, panel_y + 5)


def rotate_x(v, angle):
    x, y, z = v
    c = math.cos(angle)
    s = math.sin(angle)
    return (x, y * c - z * s, y * s + z * c)


def rotate_y(v, angle):
    x, y, z = v
    c = math.cos(angle)
    s = math.sin(angle)
    return (x * c + z * s, y, -x * s + z * c)


def rotate_z(v, angle):
    x, y, z = v
    c = math.cos(angle)
    s = math.sin(angle)
    return (x * c - y * s, x * s + y * c, z)


def frame_face_value(frame_idx):
    t = (frame_idx % FRAME_COUNT) / float(FRAME_COUNT)
    spin = math.tau * t
    rx = 0.82 + spin * 1.08 + 0.34 * math.sin(spin * 2.0 + 0.20)
    ry = 0.64 + spin * 1.62 + 0.30 * math.sin(spin * 3.0 + 1.10)
    rz = -0.14 + spin * 2.55 + 0.18 * math.cos(spin * 2.0 - 0.45)

    faces = (
        (1, (0.0, 1.0, 0.0)),
        (6, (0.0, -1.0, 0.0)),
        (2, (0.0, 0.0, 1.0)),
        (5, (0.0, 0.0, -1.0)),
        (3, (1.0, 0.0, 0.0)),
        (4, (-1.0, 0.0, 0.0)),
    )

    best_value = 1
    best_z = -999.0
    for value, normal in faces:
        rotated = rotate_z(rotate_y(rotate_x(normal, rx), ry), rz)
        if rotated[2] > best_z:
            best_z = rotated[2]
            best_value = value
    return best_value


def render_frame(frame_idx, ox=0, oy=0):
    global cur_frame

    cur_frame = frame_idx % FRAME_COUNT
    img_x = BASE_X + ox
    img_y = BASE_Y + oy

    M5.Lcd.fillRect(STAGE_X, STAGE_Y, STAGE_W, STAGE_H, BG_COLOR)
    M5.Lcd.drawImage(frame_path(cur_frame), img_x, img_y)
    draw_result_value()


def show_resource_error():
    M5.Lcd.fillScreen(BG_COLOR)
    M5.Lcd.setTextColor(TEXT_COLOR, BG_COLOR)
    M5.Lcd.setTextSize(2)
    M5.Lcd.drawString("Missing dice frames", 18, 50)
    M5.Lcd.setTextSize(1)
    M5.Lcd.drawString("Tried resource paths:", 18, 90)
    y = 110
    for candidate in FRAME_DIR_CANDIDATES:
        M5.Lcd.drawString(candidate, 18, y)
        y += 16


def init_audio():
    try:
        Speaker.begin()
    except Exception:
        pass
    try:
        Speaker.setVolume(180)
    except Exception:
        pass


def play_ready_sound():
    try:
        Speaker.tone(880, 40)
        time.sleep_ms(50)
        Speaker.tone(1320, 60)
    except Exception:
        pass


def play_roll_tick(step_idx):
    if step_idx % 4 != 0:
        return
    try:
        Speaker.tone(620 + (step_idx % 6) * 85, 10)
    except Exception:
        pass


def play_land_sound(value):
    try:
        Speaker.tone(520 + value * 55, 55)
        time.sleep_ms(15)
        Speaker.tone(920 + value * 35, 110)
    except Exception:
        pass


def can_roll():
    return time.ticks_diff(time.ticks_ms(), last_roll_ms) > ROLL_COOLDOWN_MS


def sample_motion():
    global ax_f, ay_f, last_mag, shake_score, last_jerk

    ax, ay, az = Imu.getAccel()
    ax_f = ax_f * LPF + ax * (1.0 - LPF)
    ay_f = ay_f * LPF + ay * (1.0 - LPF)

    mag = math.sqrt(ax * ax + ay * ay + az * az)
    jerk = abs(mag - last_mag)
    last_mag = mag
    last_jerk = jerk

    if jerk > SHAKE_DELTA_THRESHOLD:
        shake_score = min(3.0, shake_score + (jerk - SHAKE_DELTA_THRESHOLD) * 1.8)
    else:
        shake_score = max(0.0, shake_score - SHAKE_SCORE_DECAY)

    ox = int(clamp(ax_f * FOLLOW_GAIN, -MAX_OFFSET, MAX_OFFSET))
    oy = int(clamp(-ay_f * FOLLOW_GAIN, -MAX_OFFSET, MAX_OFFSET))
    return ox, oy, jerk


def touch_pressed():
    try:
        return M5.Touch.getCount() > 0
    except Exception:
        return False


def poll_touch_edge():
    global touch_is_down, touch_count, last_touch_seen

    touched = touch_pressed()
    if touched and (not touch_is_down):
        touch_is_down = True
        touch_count += 1
        last_touch_seen = time.ticks_ms()
        debug_log("touch down")
        return True

    if not touched:
        touch_is_down = False
    return False


def settle_to_frame(target):
    start = cur_frame
    delta = (target - start) % FRAME_COUNT
    if delta < 10:
        delta += FRAME_COUNT

    for i in range(10):
        M5.update()
        t = i / 9.0
        next_frame = (start + int(delta * ease_out_cubic(t))) % FRAME_COUNT
        jitter = 2 if i < 7 else 0
        render_frame(next_frame, random.randint(-jitter, jitter), random.randint(-jitter, jitter))
        time.sleep_ms(34 + i * 2)


def roll_once(trigger_name):
    global rolling, last_roll_ms, shake_score

    rolling = True
    shake_score = 0.0
    landing_frame = random.randrange(FRAME_COUNT)
    value = frame_face_value(landing_frame)
    set_result_visible(False)
    total_steps = random.randint(ROLL_MIN_STEPS, ROLL_MAX_STEPS)
    set_status("Rolling... (%s)" % trigger_name)
    debug_log("roll %s" % trigger_name)

    for i in range(total_steps):
        M5.update()
        t = i / float(total_steps - 1)
        delay_ms = FRAME_DELAY_MIN_MS + int((FRAME_DELAY_MAX_MS - FRAME_DELAY_MIN_MS) * (t * t))
        jitter = max(0, 7 - int(t * 7))
        render_frame(cur_frame + 1, random.randint(-jitter, jitter), random.randint(-jitter, jitter))
        play_roll_tick(i)
        time.sleep_ms(delay_ms)

    settle_to_frame(landing_frame)
    set_result(value)
    set_result_visible(True)
    render_frame(cur_frame, 0, 0)
    play_land_sound(value)
    set_status("SHAKE or TOUCH")
    last_roll_ms = time.ticks_ms()
    rolling = False


def setup():
    global cur_frame, last_mag

    debug_log("setup start")
    M5.begin()
    Widgets.setRotation(1)
    init_audio()

    if not resolve_frame_dir():
        debug_log("resolve failed")
        show_resource_error()
        write_debug_state("resolve_failed")
        return False

    M5.Lcd.fillScreen(BG_COLOR)
    cur_frame = 0
    set_result_visible(False)
    render_frame(cur_frame, 0, 0)

    ax, ay, az = Imu.getAccel()
    last_mag = math.sqrt(ax * ax + ay * ay + az * az)
    play_ready_sound()
    write_debug_state("setup_ok")
    debug_log("setup ok")
    return True


def loop():
    global loop_count, last_debug_flush_ms

    M5.update()
    loop_count += 1

    touch_edge = poll_touch_edge()
    ox, oy, _ = sample_motion()

    if not rolling:
        render_frame(cur_frame, ox, oy)

    if (not rolling) and can_roll():
        if touch_edge:
            roll_once("TOUCH")
        elif shake_score >= SHAKE_SCORE_TRIGGER:
            roll_once("SHAKE")

    now = time.ticks_ms()
    if time.ticks_diff(now, last_debug_flush_ms) > 1000:
        last_debug_flush_ms = now
        write_debug_state()

    time.sleep_ms(16)


def run():
    try:
        if setup():
            while True:
                loop()
    except Exception:
        debug_log("run exception")
        try:
            import traceback

            f = open(DEBUG_LOG_PATH, "a")
            traceback.print_exc(file=f)
            f.close()
        except Exception:
            pass
        raise
    except KeyboardInterrupt:
        debug_log("keyboard interrupt")
        write_debug_state("keyboard_interrupt")
        raise


if __name__ == "__main__":
    run()
