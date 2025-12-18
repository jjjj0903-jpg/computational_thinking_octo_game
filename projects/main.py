'''requirements'''

from game_code import vector, floor
from tkinter import *
import time
from PIL import Image, ImageTk, ImageDraw, ImageFont
from game_code.utils import load_image
import math
import tkinter as tk
from PIL import Image, ImageTk, ImageOps

def debug_show_image(img, title="Preview"):
    """PIL 이미지(img)를 단독 Tk 창으로 띄워서 정상 로드 여부 확인."""
    win = tk.Toplevel()
    win.title(title)

    # PIL → Tkinter 변환
    tk_img = ImageTk.PhotoImage(img)

    label = tk.Label(win, image=tk_img)
    label.image = tk_img
    label.pack()

    win.mainloop()


# ===============================
#  기본 설정
# ===============================

WIDTH, HEIGHT = 800, 1000      # 화면(카메라) 크기
WIDTH = int(WIDTH)
HEIGHT = int(HEIGHT)
STAGE_HEIGHT = 5000
WORLD_HEIGHT = STAGE_HEIGHT * 3           # 월드 전체 세로 길이
WORLD_WIDTH = WIDTH           # 가로 스크롤은 안 함

BALL_RADIUS = 40

GRAVITY = 0.4
BOUNCE_FACTOR = 1.0
HORIZ_SPEED = 5

TILE_WIDTH = 160
TILE_HEIGHT = 20
GRID = 40

GROUND_Y = WORLD_HEIGHT - TILE_HEIGHT     # 바닥 타일 윗면 (월드 좌표)
FLOOR_Y = GROUND_Y - BALL_RADIUS          # 공 중심이 설 위치

PLATFORMS = []

PLATFORM_BOUNCE_SPEED = 14.0

TOP_MARGIN = HEIGHT * 0.3
BOTTOM_MARGIN = HEIGHT * 0.7
STEP_DY = 180  # 공통으로 쓰자

# 밑에서부터 위로 올라가는 순서로 경로 넣기
STAGE_PATHS = [
    "images/stage1.png",  # 맨 아래
    "images/stage2.png",  # 그 위
    "images/stage3.png",  # 맨 위
]

REPEAT_PER_STAGE = 3     # 각 스테이지 이미지를 몇 번씩 반복할지
from PIL import Image, ImageTk, ImageOps

# 아래에서 위로 올라가는 순서
STAGE_PATHS = [
    "images/stage1.png",  # 맨 아래
    "images/stage2.png",  # 중간
    "images/stage3.png",  # 맨 위
]

REPEAT_PER_STAGE = 3         # 각 스테이지 타일 3번 반복
TARGET_STAGE_HEIGHT = 5000   # 3번 쌓은 블록을 최종적으로 맞출 높이


def load_world_background_blocks_rescaled():
    """
    1) stage1, stage2, stage3 각각에 대해:
         - 원본 타일 이미지를 width만 맞춘 후
         - 세로로 3번 쌓아 하나의 블록(예: 800x4608)을 만들고
         - 그 블록을 (WIDTH x TARGET_STAGE_HEIGHT)로 리사이즈

    2) 이렇게 얻은 3개의 블록 이미지를
       아래에서 위로 순서대로 붙여 최종 월드(폭 WIDTH, 높이 TARGET_STAGE_HEIGHT*3)를 만든다.
    """

    global WORLD_HEIGHT, GROUND_Y, FLOOR_Y

    blocks = []                # 최종 리사이즈된 블록 이미지를 담을 리스트
    original_block_heights = []  # 각 블록의 원래 높이 (디버그용)

    for idx, path in enumerate(STAGE_PATHS):
        # 1) 이미지 로드 + EXIF 회전 보정
        img = Image.open(path).convert("RGBA")
        img = ImageOps.exif_transpose(img)

        orig_w, orig_h = img.size

        # 2) 가로를 WIDTH에 맞추기 (리사이즈 X, crop/pad만)
        if orig_w > WIDTH:
            left = (orig_w - WIDTH) // 2
            right = left + WIDTH
            img = img.crop((left, 0, right, orig_h))
        elif orig_w < WIDTH:
            padded = Image.new("RGBA", (WIDTH, orig_h))
            x_offset = (WIDTH - orig_w) // 2
            padded.paste(img, (x_offset, 0))
            img = padded

        tile_w, tile_h = img.size  # (WIDTH, orig_h)

        # 3) 이 스테이지의 블록(타일 3번)을 세로로 쌓기
        block_h = tile_h * REPEAT_PER_STAGE
        original_block_heights.append(block_h)

        block_img = Image.new("RGBA", (WIDTH, block_h))

        offset_y = block_h
        for _ in range(REPEAT_PER_STAGE):
            offset_y -= tile_h
            block_img.paste(img, (0, offset_y))

        # 4) 블록을 (WIDTH x TARGET_STAGE_HEIGHT)로 리사이즈
        block_img_resized = block_img.resize(
            (WIDTH, TARGET_STAGE_HEIGHT),
            Image.LANCZOS
        )

        blocks.append(block_img_resized)

    # 5) 최종 월드 높이 = 블록 3개 * TARGET_STAGE_HEIGHT
    total_h = TARGET_STAGE_HEIGHT * len(blocks)
    world = Image.new("RGBA", (WIDTH, total_h))

    # 6) 아래에서 위로 블록 붙이기
    offset_y = total_h
    for block_img in blocks:
        offset_y -= TARGET_STAGE_HEIGHT
        world.paste(block_img, (0, offset_y))

    # 7) Tkinter용으로 변환
    bg_image = ImageTk.PhotoImage(world)

    # 8) 월드 전역 Y좌표 업데이트
    WORLD_HEIGHT = total_h
    GROUND_Y = WORLD_HEIGHT - TILE_HEIGHT
    FLOOR_Y = GROUND_Y - BALL_RADIUS

    # =============================
    #  🔍 디버그 정보
    # =============================
    print("\n===== WORLD DEBUG INFO (BLOCK RESCALED) =====")
    print(f"WIDTH                : {WIDTH}")
    print(f"Original block heights (stage1,2,3) : {original_block_heights}")
    print(f"TARGET_STAGE_HEIGHT  : {TARGET_STAGE_HEIGHT}")
    print(f"Total WORLD_HEIGHT   : {WORLD_HEIGHT}")
    print(f"World image size     : {world.size}")  # (WIDTH, total_h)

    # 각 스테이지 블록 top y 계산
    stage_tops = []
    cursor = total_h
    for _ in blocks:
        cursor -= TARGET_STAGE_HEIGHT
        stage_tops.append(cursor)
    print(f"Stage top Y positions (from bottom): {stage_tops}")
    print("=============================================\n")

    return bg_image



def generate_platforms_1(start_y, count):
    """기존의 교차형 플랫폼을 count개 생성 (좌우 번갈이)"""
    result = []

    left_x = WIDTH * 0.15
    right_x = WIDTH * 0.65

    for i in range(count):
        raw_y = start_y - i * STEP_DY
        raw_x = left_x if i % 2 == 0 else right_x

        x = floor(raw_x, GRID, offset=0)
        y = floor(raw_y, GRID, offset=0)
        pos = vector(x, y)

        # 🔸 bounce_mul = 1.0 (일반 발판)
        result.append((pos, TILE_WIDTH, TILE_HEIGHT, 1.0))

    final_y = start_y - (count * STEP_DY)
    return result, final_y

def generate_platforms_2(start_y, count):
    """
    RR 패턴으로 발판 count개 생성.
    (오른쪽 → 오른쪽)
    """
    result = []

    LEFT_X = WIDTH * 0.15
    RIGHT_X = WIDTH * 0.65

    y = start_y

    for i in range(count):
        # RR 패턴: 항상 오른쪽
        raw_x = RIGHT_X

        x = floor(raw_x, GRID, offset=0)
        yy = floor(y, GRID, offset=0)
        pos = vector(x, yy)

        # 일반 발판 (bounce_mul=1.0)
        result.append((pos, TILE_WIDTH, TILE_HEIGHT, 1.0))

        y -= STEP_DY

    return result, y


def generate_platforms_4(start_y, count):
    """
    LL 패턴으로 발판 count개 생성.
    (왼쪽 → 왼쪽)
    """
    result = []

    LEFT_X = WIDTH * 0.15
    RIGHT_X = WIDTH * 0.65

    y = start_y

    for i in range(count):
        # LL 패턴: 항상 왼쪽
        raw_x = LEFT_X

        x = floor(raw_x, GRID, offset=0)
        yy = floor(y, GRID, offset=0)
        pos = vector(x, yy)

        # 일반 발판 (bounce_mul=1.0)
        result.append((pos, TILE_WIDTH, TILE_HEIGHT, 1.0))

        y -= STEP_DY

    return result, y


def generate_platforms_3(start_y, count):
    """
    타입3 플랫폼:
      - 발판 사이 Y 간격은 두 배 (2 * STEP_DY)
      - 이 발판에서 튕길 때 점프력(속도)은 두 배 (bounce_mul=2.0)
    """
    result = []

    gap = STEP_DY * 2       # 🔸 간격 2배
    left_x = WIDTH * 0.15
    right_x = WIDTH * 0.65

    for i in range(count):
        raw_y = start_y - i * gap
        # 좌우 번갈이 or 한쪽만 등, 여기선 번갈이로 예시
        raw_x = left_x if i % 2 == 0 else right_x

        x = floor(raw_x, GRID, offset=0)
        y = floor(raw_y, GRID, offset=0)
        pos = vector(x, y)

        # 🔥 트램펄린 발판: bounce_mul = 2.0
        result.append((pos, TILE_WIDTH, TILE_HEIGHT, 2.0))

    final_y = start_y - (count * gap)
    return result, final_y
import random

def build_platforms():
    """
    y 값이 0보다 클 동안 계속 위로 올라가며
    플랫폼을 2개씩 랜덤 타입으로 생성하는 while-loop 방식.
    """

    global PLATFORMS
    PLATFORMS = []

    y = FLOOR_Y - 100   # 플랫폼 시작 지점
    batch_size = 2     # 한 번에 2개씩 생성

    # 사용할 플랫폼 생성기
    generators = [
        generate_platforms_1,
        generate_platforms_2,
        generate_platforms_3,
        generate_platforms_4
        
    ]

    # 가중치 (원하면 조절 가능)
    weights = [0.6, 0.125, 0.15, 0.125]

    # 월드 상단까지 계속 생성
    while y > 0:

        # 1) 어떤 타입을 쓸지 랜덤으로 선택
        generator = random.choices(generators, weights=weights, k=1)[0]

        # 2) 그 타입으로 2개의 플랫폼 생성
        plats, y = generator(y, batch_size)

        # 3) 전체 플랫폼 리스트에 추가
        PLATFORMS.extend(plats)

    print(f"[build_platforms] total = {len(PLATFORMS)} platforms")

def draw_floor(canvas, camera_y):
    """바닥 타일을 월드 전체 가로에 깔고, 카메라에 맞춰서 그림."""
    screen_ground_y = GROUND_Y - camera_y
    screen_bottom_y = WORLD_HEIGHT - camera_y

    for x in range(0, WORLD_WIDTH, TILE_WIDTH // 2):
        canvas.create_rectangle(
            x, screen_ground_y,
            x + TILE_WIDTH // 2, screen_bottom_y,
            fill="#210D04", outline="#250C04"
        )


def draw_platforms(canvas, camera_y):
    """발판들을 월드좌표 -> 화면좌표로 변환해 그림."""
    for pos, w, h, bounce_mul in PLATFORMS:
        screen_x1 = pos.x
        screen_y1 = pos.y - camera_y
        screen_x2 = screen_x1 + w
        screen_y2 = screen_y1 + h

        if screen_y2 < 0 or screen_y1 > HEIGHT:
            continue

        # 트램펄린 발판은 색을 다르게 그려도 좋음
        fill_color = "#1F0C03"       # 기본 발판
        if bounce_mul > 1.0:
            fill_color = "#013825"   # 점프력 2배 발판 표시

        canvas.create_rectangle(
            screen_x1, screen_y1,
            screen_x2, screen_y2,
            fill=fill_color,
            outline="#200F04"
        )




class Ball:
    """문어(플레이어) 엔티티."""

    def __init__(self, canvas, color='red'):
        self.canvas = canvas

        start_x = WIDTH // 2
        start_y = FLOOR_Y - 200  
        self.pos = vector(start_x, start_y)
        self.vel = vector(0, 0)
        self.hp = 3    
        self.invincible_timer = 0.0
        self.platform_disable_timer = 0.0  # 🔥 발판 통과 타이머
        self.color = color

        self.image_idle = None
        self.image_jump = None
        self.image_hurt = None
        diameter = BALL_RADIUS * 2

        '''이미지 로드 '''
        try:
            self.image_idle = load_image(
                "images/octo.png",
                diameter=diameter,
                do_crop=True
            )
        except Exception as e:
            print("octo.png 로드 실패:", e)

        try:
            self.image_jump = load_image(
                "images/octo_jump.png",
                diameter=diameter,
                do_crop=True
            )
        except Exception as e:
            print("octo_jump.png 로드 실패:", e)

        try:
            self.image_hurt = load_image(
                "images/octo_hurt.png",
                diameter=diameter,
                do_crop=True
            )
        except Exception as e:
            print("octo_hurt.png 로드 실패:", e)

        self.current_image = self.image_idle

    def update_sprite(self):
        """
        현재 상태에 따라 self.current_image를 결정:
        1) invincible_timer > 0      → hurt 이미지
        2) vel.y < 0 (상승 중)       → jump 이미지
        3) 그 외(낙하/정지)          → idle 이미지
        """
        # 1) 피격 무적 상태 
        if self.invincible_timer > 0 and self.image_hurt is not None:
            self.current_image = self.image_hurt
            return

        # 2) 상승 중 (vel.y < 0) → 점프 이미지
        if self.vel.y < 0 and self.image_jump is not None:
            self.current_image = self.image_jump
            return

        # 3) 기본 상태 → idle
        if self.image_idle is not None:
            self.current_image = self.image_idle
        else:
            self.current_image = None  # fallback로 원 그리기

    def update_physics(self):
        old_y = self.pos.y

        # 중력
        self.vel.y += GRAVITY
        self.pos += self.vel

        if self.invincible_timer > 0:
            self.invincible_timer -= 0.01  # 프레임 간격에 맞춰 조절

        # 🔹 발판 통과 타이머
        if self.platform_disable_timer > 0:
            self.platform_disable_timer -= 0.01

        # -----------------------------
        # 발판 충돌 (위에서 내려올 때만 + 발판 비활성 아닐 때만)
        # -----------------------------
        if self.vel.y > 0 and self.platform_disable_timer <= 0:
            for pos, w, h, bounce_mul in PLATFORMS:
                left = pos.x
                right = pos.x + w
                top = pos.y

                if left - BALL_RADIUS <= self.pos.x <= right + BALL_RADIUS:
                    if old_y + BALL_RADIUS <= top <= self.pos.y + BALL_RADIUS:
                        self.pos.y = top - BALL_RADIUS

                        # 🔥 여기에서 발판에 따라 점프력 다르게
                        jump_speed = PLATFORM_BOUNCE_SPEED * bounce_mul
                        if bounce_mul > 1.0:
                            jump_speed *= 0.7   # 약 30% 감소

                        self.vel.y = -jump_speed
                        break

        # 바닥 충돌: 항상 같은 속도로 튀도록
        if self.pos.y > FLOOR_Y:
            self.pos.y = FLOOR_Y
            self.vel.y = -PLATFORM_BOUNCE_SPEED

        # 좌우 벽 
        if self.pos.x - BALL_RADIUS < 0:
            self.pos.x = BALL_RADIUS
            self.vel.x = abs(self.vel.x)
        if self.pos.x + BALL_RADIUS > WIDTH:
            self.pos.x = WIDTH - BALL_RADIUS
            self.vel.x = -abs(self.vel.x)

        self.update_sprite()

    def take_damage(self, damage, knockback=None):
        """
        Enemy에게 맞았을 때 호출:
        - 무적 상태가 아니면 hp 감소
        - 넉백(velocity) 적용
        - invincible_timer 설정
        """
        if self.invincible_timer > 0:
            return  # 이미 무적이면 무시

        self.hp -= damage
        print(f"Ball hit! hp = {self.hp}")

        # 넉백 적용
        if knockback is not None:
            self.vel.x = knockback.x
            self.vel.y = knockback.y

        # 무적 시간 부여 
        self.invincible_timer = 0.5
        self.platform_disable_timer = 0.7

        # 피격 직후 스프라이트 즉시 업데이트
        self.update_sprite()

    def draw(self, camera_y):
        """카메라 기준으로 문어 이미지(또는 원) 그리기."""
        screen_x = self.pos.x
        screen_y = self.pos.y - camera_y

        if self.current_image is not None:
            self.canvas.create_image(
                screen_x,
                screen_y,
                image=self.current_image
            )
        else:
            x0 = screen_x - BALL_RADIUS
            y0 = screen_y - BALL_RADIUS
            x1 = screen_x + BALL_RADIUS
            y1 = screen_y + BALL_RADIUS
            self.canvas.create_oval(
                x0, y0, x1, y1,
                fill=self.color,
                outline='black',
                width=2
            )

    def move_left(self, event=None):
        self.vel.x = -HORIZ_SPEED

    def move_right(self, event=None):
        self.vel.x = HORIZ_SPEED

    def stop_horizontal(self, event=None):
        self.vel.x = 0

# ===============================
#  게임 루프 (실제 플레이)
# ===============================
class Enemy:
    """
    곰치/복어/아귀/상어 등의 공통 적 클래스.

    - type에 따라 패턴 다르게:
      * "puffer": 제자리에서 부풀었다 줄어들기 + 살짝 떠다님
      * "moray": 벽에서 튀어나왔다 들어가기
      * "angler": 거의 고정, 위치만 중요 (스테이지 끝쪽)
      * "shark": 좌우로 빠르게 패트롤
    """

    def __init__(self, canvas, x, y, w, h,
                 enemy_type="puffer",
                 image=None,
                 image_big=None,
                 damage=1):

        self.canvas = canvas
        self.pos = vector(x, y)   # 중심 기준
        self.w = w
        self.h = h
        self.base_w = w
        self.base_h = h

        self.type = enemy_type
        self.damage = damage

        # 기본 이미지 (idle 개념)
        self.image = image

        # 복어 전용: 작은/큰 이미지
        self.image_small = image      # 기본값: small
        self.image_big = image_big    # big 상태에서 사용

        self.state = "idle"
        if self.type == "puffer":
            self.state = "small"      # 복어 시작 상태

        # 패턴용 상태 변수들
        self.time = 0.0          # 공통 타이머
        self.puffer_timer = 0.0  # 복어 전용 타이머
        self.dir = 1             # 좌우/안팎 방향
        self.speed = 2.0         # 기본 속도
        self.base_x = x
        self.base_y = y

        self.active = True       # False 되면 무시
                  
        if self.type == "moray":
            self.moray_state = "crouch"     # "crouch" -> "attack_out" -> "attack_back"
            self.moray_timer = 0.0
            self.moray_move_duration = 1  # 🔥 나갈 때 0.5초, 돌아올 때 0.5초
            self.moray_offset = 300         # 🔥 더 멀리 튀어나오게 (원래 150 → 260 정도로 증가)
            self.moray_side = 1             # 1: 오른쪽으로 나갔다 돌아옴, -1: 왼쪽
            self.moray_img_cro = None       # gom_cro
            self.moray_img_idle = self.image
            self.moray_img_act = None       # gom_act

    # -------------------------------------------------------
    # 패턴 업데이트
    # -------------------------------------------------------
    def update(self):
        if not self.active:
            return

        # 대략 프레임당 0.016 ~ 0.02 정도로 가정
        self.time += 0.016

        if self.type == "puffer":
            self._update_puffer()

        elif self.type == "moray":
            self._update_moray()

        elif self.type == "shark":
            self._update_shark()

        elif self.type == "angler":
            self._update_angler()

    # ---------- 각 타입별 내부 패턴 함수들 ----------
    def _update_puffer(self):

        dy = math.sin(self.time * 2.0) * 5
        self.pos.y = self.base_y + dy

        move_range = 300  
        dx = math.sin(self.time * 0.5) * move_range
        self.pos.x = self.base_x + dx

        # --------------------------
        # 3) 크기 토글 (기존)
        # --------------------------
        self.puffer_timer += 0.016

        if self.puffer_timer >= 1.0:
            self.puffer_timer = 0.0

            if self.state == "small":
                self.state = "big"
                if self.image_big is not None:
                    self.image = self.image_big

                self.w = self.base_w * 2
                self.h = self.base_h * 2

            else:
                self.state = "small"
                if self.image_small is not None:
                    self.image = self.image_small

                self.w = self.base_w
                self.h = self.base_h



    def _update_moray(self):
        """
        곰치 패턴:

        1) gom_cro (동굴 안) 상태로 3초 대기
        2) 그 후:
        - 1초 동안 앞으로 쭉 나옴 (attack_out)
        - 1초 동안 다시 뒤로 복귀 (attack_back)
        - 이 두 구간 동안 0.5초마다 gom <-> gom_act 이미지 토글
        3) 다시 crouch 로 돌아가서 반복
        """

        dt = 0.016
        self.moray_timer += dt

        # 안전장치: 이미지 세트가 안 들어왔으면 그냥 아무것도 안 함
        if self.moray_img_cro is None:
            self.moray_img_cro = self.image
        if self.moray_img_idle is None:
            self.moray_img_idle = self.image

        # ---- 상태별 동작 ----
        if self.moray_state == "crouch":
            # 동굴 안에서 대기 (3초)
            self.pos.x = self.base_x
            self.image = self.moray_img_cro

            if self.moray_timer >= 2.0:
                # 앞으로 튀어나오기 시작
                self.moray_state = "attack_out"
                self.moray_timer = 0.0

        elif self.moray_state in ("attack_out", "attack_back"):

            # 0 ~ 1 까지의 진행도(progress)
            t = min(self.moray_timer / self.moray_move_duration, 1.0)

            if self.moray_state == "attack_out":
                # base_x 에서 앞으로 나가는 중
                offset = self.moray_offset * t
            else:
                # base_x 에서 다시 뒤로 들어가는 중
                offset = self.moray_offset * (1.0 - t)

            # 왼쪽/오른쪽 방향 선택
            self.pos.x = self.base_x + self.moray_side * offset

            # 0.5초마다 gom <-> gom_act 토글
            if self.moray_img_act is not None:
                phase = int(self.moray_timer / 0.5) % 2
                if phase == 0:
                    self.image = self.moray_img_idle
                else:
                    self.image = self.moray_img_act
            else:
                self.image = self.moray_img_idle

            # 현재 공격 단계가 끝났으면 다음 상태로
            if self.moray_timer >= self.moray_move_duration:
                if self.moray_state == "attack_out":
                    # 앞으로 나가는 거 끝 → 이제 뒤로 복귀 단계
                    self.moray_state = "attack_back"
                else:
                    # 다시 동굴로 복귀 완료 → crouch 상태로
                    self.moray_state = "crouch"

                self.moray_timer = 0.0


    def _update_shark(self):
        """
        상어: 모래시계(∞) 패턴으로 빠르게 이동
        - 3시 → 8시 → 3시 → 10시 방향으로 계속 반복되는 느낌
        """

        # 중심 기준 반경(좌우, 상하 범위)
        R = 300   # 좌우 이동 범위
        H = 150   # 상하 이동 범위

        # 속도 (값 키우면 전체 움직임이 빨라짐)
        omega = 2.0

        # time은 update()에서 계속 증가 중
        self.pos.x = self.base_x + R * math.sin(self.time * omega)
        self.pos.y = self.base_y + H * math.sin(self.time * 2 * omega)
    
    def _update_angler(self):
        # 천천히 위아래 이동
        dy = math.sin(self.time * 1.2) * 5
        self.pos.y = self.base_y + dy

        move_range = 300  
        dx = math.sin(self.time * 0.2) * move_range
        self.pos.x = self.base_x + dx


    # -------------------------------------------------------
    # 렌더링
    # -------------------------------------------------------
    def draw(self, camera_y):
        if not self.active:
            return

        screen_x = self.pos.x
        screen_y = self.pos.y - camera_y

        if self.image is not None:
            self.canvas.create_image(
                screen_x,
                screen_y,
                image=self.image,
                anchor="center"  
            )
        else:
            # 디버그용: 사각형으로 표시
            x0 = screen_x - self.w / 2
            y0 = screen_y - self.h / 2
            x1 = screen_x + self.w / 2
            y1 = screen_y + self.h / 2
            self.canvas.create_rectangle(
                x0, y0, x1, y1,
                outline="red",
                width=2
            )

    # -------------------------------------------------------
    # 충돌 판정
    # -------------------------------------------------------
    def collides_with(self, ball):
        """
        circle( ball.pos, BALL_RADIUS ) vs
        rect( self.pos, self.w, self.h ) 충돌 판정.
        """
        if not self.active:
            return False

        # 적 사각형의 경계 (월드 좌표)
        left = self.pos.x - self.w / 2
        right = self.pos.x + self.w / 2
        top = self.pos.y - self.h / 2
        bottom = self.pos.y + self.h / 2

        # 원 중심을 사각형에 clamp
        closest_x = min(max(ball.pos.x, left), right)
        closest_y = min(max(ball.pos.y, top), bottom)

        dx = ball.pos.x - closest_x
        dy = ball.pos.y - closest_y
        dist_sq = dx * dx + dy * dy

        return dist_sq <= (BALL_RADIUS ** 2)

    # -------------------------------------------------------
    # 충돌 시 처리
    # -------------------------------------------------------
    def on_hit_ball(self, ball):
        """
        ball과 이미 충돌했다고 판단되었을 때 호출.
        - Ball.take_damage()를 통해 데미지, 넉백, 무적 처리
        """
        if not self.active:
            return

        # Ball이 이미 무적 상태라면 무시
        if getattr(ball, "invincible_timer", 0) > 0:
            return

        # 넉백 벡터 계산
        dx = ball.pos.x - self.pos.x
        dy = ball.pos.y - self.pos.y

        if dx == 0 and dy == 0:
            dy = -1

        length = (dx * dx + dy * dy) ** 0.5
        nx = dx / length
        ny = dy / length

        bounce_speed = 8.0
        knockback = vector(nx * bounce_speed, ny * bounce_speed)

        # Ball 내부 로직 활용 (hp 감소 + 무적 + 튕김)
        if hasattr(ball, "take_damage"):
            ball.take_damage(self.damage, knockback)
        else:
            # 혹시 take_damage 미구현이면 최소한 hp만 줄이기
            if hasattr(ball, "hp"):
                ball.hp -= self.damage
                print(f"Ball hit! hp = {ball.hp}")

def build_enemies_stage1(canvas):
    enemies = []
    angler_img = load_image("images/ah.png", 140, rotate_deg=90)

    for i, y in enumerate(range(10000, 15001, 1000)):   # 10000,11000,12000,13000,14000,15000
        if i == 0 or i == 5:
            continue 
        x = random.randint(WIDTH//2 - 100, WIDTH//2 + 100)

        enemies.append(Enemy(
            canvas,
            x=x,
            y=y,
            w=140,
            h=140,
            enemy_type="angler",
            image=angler_img,
            damage=1
        ))

    return enemies




def build_enemies_stage2(canvas):
    enemies = []

    # 🔹 곰치 1용 (반전 O)
    gom_idle_flip = load_image("images/gom.png",     160, rotate_deg=90, squre=2, hflip=True)
    gom_act_flip  = load_image("images/gom_act.png", 160, rotate_deg=90, squre=2, hflip=True)
    gom_cro_flip  = load_image("images/gom_cro.png", 160, rotate_deg=90, squre=1, hflip=True)

    # 🔹 곰치 2용 (반전 X)
    gom_idle = load_image("images/gom.png",     160, rotate_deg=90, squre=2, hflip=False)
    gom_act  = load_image("images/gom_act.png", 160, rotate_deg=90, squre=2, hflip=False)
    gom_cro  = load_image("images/gom_cro.png", 160, rotate_deg=90, squre=1, hflip=False)

    # --- y 범위 계산 ---
    STAGE2_BOTTOM = WORLD_HEIGHT - 5000   # =10000
    STAGE2_TOP    = WORLD_HEIGHT - 10000  # =5000
    BAND_HEIGHT   = 1000
    NUM_BANDS     = 5

    for i in range(NUM_BANDS):

        # 밴드 중앙  
        band_center_y = STAGE2_BOTTOM - (i * BAND_HEIGHT + BAND_HEIGHT // 2)

        moray1_y = band_center_y - 500   # << 여기 요구사항 반영

        moray1 = Enemy(
            canvas,
            x=0,
            y=moray1_y,
            w=160, h=80,
            enemy_type="moray",
            image=gom_idle_flip,
            damage=1
        )
        moray1.moray_img_cro  = gom_cro_flip
        moray1.moray_img_idle = gom_idle_flip
        moray1.moray_img_act  = gom_act_flip
        moray1.moray_side     = 1
        enemies.append(moray1)

        moray2 = Enemy(
            canvas,
            x=WIDTH,
            y=band_center_y,
            w=160, h=80,
            enemy_type="moray",
            image=gom_idle,
            damage=1
        )
        moray2.moray_img_cro  = gom_cro
        moray2.moray_img_idle = gom_idle
        moray2.moray_img_act  = gom_act
        moray2.moray_side     = -1
        enemies.append(moray2)

    print(f"[build_enemies_stage2] done: {len(enemies)} morays")
    return enemies


def build_enemies_stage3(canvas):
    enemies = []

    # --------------------------
    # 🔹 이미지 로드
    # --------------------------
    puffer_small = load_image("images/bok_sml.png", 80)
    puffer_big   = load_image("images/bok_big.png", 160)
    shark_img    = load_image("images/shark.png", 140, rotate_deg=90, squre=1)

    # --------------------------
    # 🔹 Stage3 복어 배치
    #     y = 1000, 2000, 3000, 4000, 5000
    #     → 가운데 3개만 사용 (2000, 3000, 4000)
    # --------------------------
    for i, y in enumerate(range(1000, 5001, 1000)):   # 1000~5000
        if i == 0 or i == 4:
            continue  # 1000, 5000 제외

        x = random.randint(WIDTH // 2 - 120, WIDTH // 2 + 120)

        enemies.append(Enemy(
            canvas,
            x=x,
            y=y,
            w=160,
            h=120,
            enemy_type="puffer",
            image=puffer_small,
            image_big=puffer_big,
            damage=1
        ))

    # --------------------------
    # 🔹 Stage3 상어 배치
    #     후보 y 값: 1500, 2500, 3500, 4500
    #     → 랜덤으로 1개 선택
    # --------------------------
    shark_y_candidates = [1500, 2500, 3500, 4500]
    shark_y = random.choice(shark_y_candidates)

    # 겹침 방지: 상어는 가급적 중앙을 피해서 배치
    shark_x_candidates = [
        random.randint(50, int(WIDTH * 0.3)),      # 왼쪽 30% 랜덤
        random.randint(int(WIDTH * 0.7), WIDTH-50) # 오른쪽 30% 랜덤
    ]
    shark_x = random.choice(shark_x_candidates)

    enemies.append(Enemy(
        canvas,
        x=shark_x,
        y=shark_y,
        w=200,
        h=100,
        enemy_type="shark",
        image=shark_img,
        damage=1
    ))

    return enemies



def run_game(root, canvas, bg_image):
    build_platforms()   
    # init_platforms()
    ball = Ball(canvas, color='yellow')


    enemies = []
    enemies = build_enemies_stage1(canvas)
    enemies_2 = build_enemies_stage2(canvas)
    enemies_3 = build_enemies_stage3(canvas)
    enemies.extend(enemies_2)
    enemies.extend(enemies_3)

    camera_y = WORLD_HEIGHT - HEIGHT
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()

    root.bind('<Left>', ball.move_left)
    root.bind('<Right>', ball.move_right)
    root.bind('<KeyRelease-Left>', ball.stop_horizontal)
    root.bind('<KeyRelease-Right>', ball.stop_horizontal)

    while True:
        ball.update_physics()

        screen_ball_y = ball.pos.y - camera_y

        # 🔹 엔딩 조건 체크: 아래에서부터 15000 이상 올라오면 엔딩
        progress = WORLD_HEIGHT - ball.pos.y
        if progress >= 15000:
            print("== REACHED TOP, PLAY ENDING! ==")
            play_ending_scene(root, canvas)
            return  # run_game 끝내고 main으로 복귀

        # 🔥 적 업데이트 + 충돌
        for enemy in enemies:
            enemy.update()
            if enemy.collides_with(ball):
                enemy.on_hit_ball(ball)

        # 카메라 업데이트
        if screen_ball_y < TOP_MARGIN:
            camera_y = max(ball.pos.y - TOP_MARGIN, 0)
        elif screen_ball_y > BOTTOM_MARGIN:
            camera_y = min(ball.pos.y - BOTTOM_MARGIN, WORLD_HEIGHT - HEIGHT)

        # 화면 지우기
        canvas.delete("all")

        # 배경
        if bg_image is not None:
            canvas.create_image(
                0, -camera_y,
                image=bg_image,
                anchor='nw'
            )

        draw_floor(canvas, camera_y)
        draw_platforms(canvas, camera_y)

        # 🎯 플레이어 그리기
        ball.draw(camera_y)

        # 🎯 적 그리기 (빠져있던 부분!)
        for enemy in enemies:
            enemy.draw(camera_y)

        root.update_idletasks()
        root.update()
        time.sleep(0.01)


# ===============================
#  시작 화면(타이틀) 표시
# ===============================
from PIL import Image, ImageTk, ImageOps, ImageDraw, ImageFont

def play_intro_scene(root, canvas, stay_time=3, fade_time=0.6, steps=10):
    canvas.delete("all")

    intro_paths = [
        "images/int1.png",
        "images/int2.png",
    ]

    frames = []

    for path in intro_paths:
        try:
            img = Image.open(path)
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGBA")

            orig_w, orig_h = img.size
            frame = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))

            offset_x = max((WIDTH  - orig_w) // 2, 0)
            offset_y = max((HEIGHT - orig_h) // 2, 0)
            frame.paste(img, (offset_x, offset_y), img)

            frames.append(frame)

        except Exception as e:
            print("인트로 이미지 로드 실패:", path, e)

    if not frames:
        return

    # ============================
    # 🔹 첫 번째 컷: "Nobody likes me..."
    # ============================
    frame1 = frames[0]
    draw1 = ImageDraw.Draw(frame1)

    text1 = "Nobody likes me..."
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except:
        font = ImageFont.load_default()

    bbox1 = draw1.textbbox((0, 0), text1, font=font)
    tw1 = bbox1[2] - bbox1[0]
    th1 = bbox1[3] - bbox1[1]

    x1 = (WIDTH - tw1) // 2
    y1 = HEIGHT - th1 - 80

    draw1.text((x1+2, y1+2), text1, font=font, fill=(0, 0, 0, 200))     # 그림자
    draw1.text((x1, y1),       text1, font=font, fill=(255, 255, 255))  # 본문

    frames[0] = frame1

    # ============================
    # 🔹 두 번째 컷: "i'm drowning..."
    # ============================
    frame2 = frames[1]
    draw2 = ImageDraw.Draw(frame2)

    text2 = "i'm drowning..."
    bbox2 = draw2.textbbox((0, 0), text2, font=font)
    tw2 = bbox2[2] - bbox2[0]
    th2 = bbox2[3] - bbox2[1]

    x2 = (WIDTH - tw2) // 2
    y2 = HEIGHT - th2 - 80

    draw2.text((x2+2, y2+2), text2, font=font, fill=(0, 0, 0, 200))
    draw2.text((x2, y2),     text2, font=font, fill=(255, 255, 255))

    frames[1] = frame2

    # ============================
    # 🔹 아래는 기존 페이드 전환 & 컷 표시
    # ============================
    cur_pil = frames[0]
    cur_tk = ImageTk.PhotoImage(cur_pil)
    canvas._cutscene_img = cur_tk
    canvas.create_image(0, 0, image=cur_tk, anchor="nw")
    root.update_idletasks()
    root.update()
    time.sleep(stay_time)

    for next_pil in frames[1:]:
        for i in range(1, steps + 1):
            t = i / float(steps)
            blended = Image.blend(cur_pil, next_pil, t)
            blended_tk = ImageTk.PhotoImage(blended)

            canvas._cutscene_img = blended_tk
            canvas.delete("all")
            canvas.create_image(0, 0, image=blended_tk, anchor="nw")
            root.update_idletasks()
            root.update()
            time.sleep(fade_time / steps)

        cur_pil = next_pil
        cur_tk = ImageTk.PhotoImage(cur_pil)
        canvas._cutscene_img = cur_tk

        canvas.delete("all")
        canvas.create_image(0, 0, image=cur_tk, anchor="nw")
        root.update_idletasks()
        root.update()
        time.sleep(stay_time)

    canvas.delete("all")
    root.update_idletasks()
    root.update()
# 화면을 천천히 흰색으로 채우는 페이드 아웃
def fade_to_white(root, canvas, duration=1.5, steps=15):
    """
    duration 동안 화면 색을 검정 → 흰색으로 점점 밝게 만듦.
    (게임 마지막 화면을 그대로 쓰진 않고, 단색 그라데이션으로 연출)
    """
    for i in range(steps + 1):
        t = i / float(steps)   # 0.0 ~ 1.0
        v = int(255 * t)       # 0 ~ 255 (검정 → 흰색)
        color = f"#{v:02x}{v:02x}{v:02x}"

        canvas.delete("all")
        canvas.create_rectangle(0, 0, WIDTH, HEIGHT,
                                fill=color, outline=color)

        root.update_idletasks()
        root.update()
        time.sleep(duration / steps)

def draw_outlined_text(canvas, x, y, text, font, fill="white", outline="black"):
    """흰색 텍스트 + 조금 더 두꺼운 검정 테두리"""
    # 살짝 더 두꺼운 외곽선 (상하좌우 + 대각 + 2픽셀)
    offsets = [
        (-2, 0), (2, 0), (0, -2), (0, 2),
        (-1, -1), (1, -1), (-1, 1), (1, 1),
    ]
    for ox, oy in offsets:
        canvas.create_text(
            x + ox, y + oy,
            text=text,
            fill=outline,
            font=font,
        )
    # 본문(흰색)
    canvas.create_text(
        x, y,
        text=text,
        fill=fill,
        font=font,
    )
def play_ending_scene(root, canvas, stay_time=4, fade_time=0.6, steps=12):
    """
    엔딩 컷신: ed1.png ~ ed5.png
    - 리사이즈 X, 검정 배경 위 중앙 배치
    - 컷마다 (영문/한글) 자막 표시
    - 컷 사이에는 부드러운 페이드 전환
    """

    # 엔딩 전에 흰색으로 페이드 인
    fade_to_white(root, canvas, duration=1.5, steps=15)

    canvas.delete("all")

    ending_paths = [
        "images/ed1.png",
        "images/ed2.png",
        "images/ed3.png",
        "images/ed4.png",
        "images/ed5.png",
    ]

    captions = [
        (
            "I thought… this world had no place for me.",
            "이 세상에 내가 있을 자리는 없다고 생각했다."
        ),
        (
            "So I hid myself… sinking deeper and deeper.",
            "그래서 나는 숨었고, 점점 더 깊이 가라앉았다."
        ),
        (
            "But even in the deepest darkness… a small light found me.",
            "하지만 가장 깊은 어둠 속에서도… 작은 빛이 나를 찾아왔다."
        ),
        (
            "I realized… I was never truly alone.",
            "나는 깨달았다. 나는 결코 완전히 혼자가 아니었다는 것을."
        ),
        (
            "And now… I can finally rise again.",
            "그리고 이제… 나는 다시 일어설 수 있다."
        ),
    ]

    # 1) 이미지 로드 + 레터박스화
    frames = []
    for path in ending_paths:
        try:
            img = Image.open(path)
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGBA")

            orig_w, orig_h = img.size

            frame = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
            offset_x = max((WIDTH  - orig_w) // 2, 0)
            offset_y = max((HEIGHT - orig_h) // 2, 0)
            frame.paste(img, (offset_x, offset_y), img)

            frames.append(frame)
        except Exception as e:
            print("엔딩 이미지 로드 실패:", path, e)

    if not frames:
        return

    # 개수 맞추기
    n = min(len(frames), len(captions))
    frames = frames[:n]
    captions = captions[:n]

    # 자막 위치(하단)
    text_y_eng = HEIGHT - 90
    text_y_kor = HEIGHT - 60

    # 2) 첫 컷 표시
    cur_pil = frames[0]
    eng_text, kor_text = captions[0]

    cur_tk = ImageTk.PhotoImage(cur_pil)
    canvas._ending_img = cur_tk

    canvas.delete("all")
    canvas.create_image(0, 0, image=cur_tk, anchor="nw")

    # 첫 컷 자막
    draw_outlined_text(
        canvas,
        WIDTH // 2,
        text_y_eng,
        eng_text,
        font=("Arial", 18, "bold"),
    )
    draw_outlined_text(
        canvas,
        WIDTH // 2,
        text_y_kor,
        kor_text,
        font=("맑은 고딕", 18, "bold"),
    )

    root.update_idletasks()
    root.update()
    time.sleep(stay_time)

    # 3) 컷간 페이드 전환
    for idx in range(1, n):
        next_pil = frames[idx]
        next_eng, next_kor = captions[idx]

        # cur_pil → next_pil 페이드
        for i in range(1, steps + 1):
            t = i / float(steps)

            blended = Image.blend(cur_pil, next_pil, t)
            blended_tk = ImageTk.PhotoImage(blended)

            canvas._ending_img = blended_tk
            canvas.delete("all")
            canvas.create_image(0, 0, image=blended_tk, anchor="nw")

            # 페이드 중에는 "다음 컷" 자막을 표시
            draw_outlined_text(
                canvas,
                WIDTH // 2,
                text_y_eng,
                next_eng,
                font=("Arial", 18, "bold"),
            )
            draw_outlined_text(
                canvas,
                WIDTH // 2,
                text_y_kor,
                next_kor,
                font=("맑은 고딕", 18, "bold"),
            )

            root.update_idletasks()
            root.update()
            time.sleep(fade_time / steps)

        # 다음 컷을 현재 컷으로 확정
        cur_pil = next_pil
        eng_text, kor_text = next_eng, next_kor

        cur_tk = ImageTk.PhotoImage(cur_pil)
        canvas._ending_img = cur_tk

        canvas.delete("all")
        canvas.create_image(0, 0, image=cur_tk, anchor="nw")

        # 확정된 컷 자막 표시
        draw_outlined_text(
            canvas,
            WIDTH // 2,
            text_y_eng,
            eng_text,
            font=("Arial", 18, "bold"),
        )
        draw_outlined_text(
            canvas,
            WIDTH // 2,
            text_y_kor,
            kor_text,
            font=("맑은 고딕", 18, "bold"),
        )

        root.update_idletasks()
        root.update()
        time.sleep(stay_time)

    # 4) 엔딩 종료 후 화면 정리
    canvas.delete("all")
    root.update_idletasks()
    root.update()


def draw_start_screen(canvas, title_image):
    """시작 화면을 그려주고 START 버튼 영역을 반환."""
    canvas.delete("all")

    # 전체 배경으로 타이틀 이미지
    if title_image is not None:
        canvas.create_image(0, 0, image=title_image, anchor='nw')
    else:
        canvas.create_rectangle(0, 0, WIDTH, HEIGHT, fill="#001a33")

    # START 버튼 (하단 중앙)
    btn_w, btn_h = 260, 80
    x1 = (WIDTH - btn_w) // 2
    y1 = int(HEIGHT * 0.75)
    x2 = x1 + btn_w
    y2 = y1 + btn_h

    canvas.create_rectangle(
        x1, y1, x2, y2,
        fill="#004c99", outline="white", width=3
    )
    canvas.create_text(
        (x1 + x2) / 2,
        (y1 + y2) / 2,
        text="START",
        fill="white",
        font=("Arial", 28, "bold")
    )

    canvas.create_text(
        WIDTH / 2,
        y1 - 40,
        text="",
        fill="white",
        font=("Arial", 18)
    )

    return (x1, y1, x2, y2)


# ===============================
#  메인 (시작 화면 → 게임 화면)
# ===============================
def main():
    root = Tk()
    root.title("문어, 빛을 찾다")

    canvas = Canvas(
        root,
        width=WIDTH,
        height=HEIGHT,
        bd=0,
        highlightthickness=0,
        bg='#000000'
    )
    canvas.pack()
    root.update()

    # --- 타이틀 이미지 로드 ---
    title_image = None
    try:
        title_pil = Image.open("images/title_screen.png").convert("RGBA")
        title_pil = title_pil.resize((WIDTH, HEIGHT), Image.LANCZOS)
        title_image = ImageTk.PhotoImage(title_pil)
    except Exception as e:
        print("title_screen.png 로드 실패(없어도 실행 가능):", e)

    # --- 월드 배경: stage1,2,3 블록 5000씩 쌓기 ---
    try:
        bg_image = load_world_background_blocks_rescaled()
    except Exception as e:
        print("world background 생성 실패:", e)
        bg_image = None

    # 🔁 엔딩 후에도 다시 시작화면으로 돌아오도록 루프
    while True:
        # --- 시작 화면 표시 ---
        btn_bbox = draw_start_screen(canvas, title_image)
        btn_x1, btn_y1, btn_x2, btn_y2 = btn_bbox

        started = {"flag": False}

        def on_mouse_click(event):
            if btn_x1 <= event.x <= btn_x2 and btn_y1 <= event.y <= btn_y2:
                started["flag"] = True

        def on_space(event):
            started["flag"] = True

        canvas.bind("<Button-1>", on_mouse_click)
        root.bind("<space>", on_space)

        # 스타트 눌릴 때까지 대기
        while not started["flag"]:
            root.update_idletasks()
            root.update()
            time.sleep(0.01)

        # 입력 해제 + 화면 클리어
        canvas.unbind("<Button-1>")
        root.unbind("<space>")
        canvas.delete("all")

        # 🔹⭐ 여기서 인트로 컷신 재생
        play_intro_scene(root, canvas, stay_time=3, fade_time=0.6)

        # --- 실제 게임 루프 시작 ---
        # run_game 내부에서 꼭:
        #  - 조건 만족 시 play_ending_scene 호출
        #  - 그리고 return 으로 종료
        run_game(root, canvas, bg_image)
        # 여기까지 오면 게임 한 판 끝난 거라
        # while True 덕분에 다시 시작 화면으로 자연스럽게 복귀


if __name__ == '__main__':
    main()
