import pygame
import sys
import math
import subprocess
import os
import random
from pathlib import Path
# ================= 配置与常量 =================
WIDTH, HEIGHT = 600, 750
FPS = 60
CELL_SIZE = 80  # 网格大小
# 颜色定义
BG_COLOR = (243, 244, 246)       # 背景灰白色
GRID_COLOR = (209, 213, 219)     # 网格线颜色
TEXT_COLOR = (31, 41, 55)        # 深灰文本色
BTN_COLOR = (59, 130, 246)       # 按钮蓝色
BTN_HOVER = (37, 99, 235)        # 按钮悬停色
RED = (239, 68, 68)              # 错误提示红色

# 主菜单的原创像素场景色板。所有装饰都由基础几何图形绘制，
# 因此不会依赖或复刻参考图中的任何角色/素材。
SKY = (166, 220, 239)
SKY_LIGHT = (198, 235, 246)
GRASS = (98, 177, 71)
GRASS_DARK = (57, 126, 59)
HILL = (76, 143, 64)
WATER = (71, 151, 205)
WATER_DARK = (47, 111, 164)
WOOD = (172, 111, 52)
WOOD_DARK = (91, 56, 30)
CREAM = (255, 241, 199)
CREAM_SHADOW = (223, 191, 128)
BROWN = (104, 65, 35)
GOLD = (255, 190, 57)
GOLD_LIGHT = (255, 221, 104)
# 箭头颜色映射
ARROW_COLORS = {
    'U': (239, 68, 68),   # 上：红色
    'D': (59, 130, 246),  # 下：蓝色
    'L': (16, 185, 129),  # 左：绿色
    'R': (245, 158, 11)   # 右：橙色
}
# ================= 关卡设计 =================
# 遵循规则：同一行中L必须在R左侧，同一列中U必须在D上方，避免产生绝对死锁
LEVELS = [
    [   # 关卡 1: 3x3 简单基础
        ['U', 'U', 'R'],
        ['L', 'U', 'R'],
        ['L', 'D', 'D']
    ],
    [   # 关卡 2: 4x4 进阶交错
        ['U', 'U', 'U', 'R'],
        ['L', 'U', 'R', 'R'],
        ['L', 'L', 'D', 'R'],
        ['L', 'D', 'D', 'D']
    ],
    [   # 关卡 3: 5x5 复杂阻挡
        ['.', 'U', 'L', 'U', '.'],
        ['U', 'L', 'U', 'R', 'U'],
        ['L', 'U', 'R', 'D', 'R'],
        ['D', 'L', 'D', 'R', 'D'],
        ['.', 'D', 'R', 'D', '.']
    ]
]
# 每关时间限制（秒）
LEVEL_TIME_LIMIT = [30, 60, 90]
FOG_LEVEL_COUNT = 10  # 迷雾是完整的有限挑战，而非与无尽模式重复

# ================= 无尽模式随机关卡生成 =================
def _grid_solvable(grid):
    """模拟逐箭消除，判断该网格是否存在一条完整解。"""
    rows = len(grid)
    cols = len(grid[0])
    active = {}
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] in 'UDLR':
                active[(r, c)] = grid[r][c]
    while active:
        picked = None
        for (r, c), d in active.items():
            blocked = False
            for (r2, c2), _ in active.items():
                if (r2, c2) == (r, c):
                    continue
                if d == 'U' and c2 == c and r2 < r:
                    blocked = True; break
                if d == 'D' and c2 == c and r2 > r:
                    blocked = True; break
                if d == 'L' and r2 == r and c2 < c:
                    blocked = True; break
                if d == 'R' and r2 == r and c2 > c:
                    blocked = True; break
            if not blocked:
                picked = (r, c)
                break
        if picked is None:
            return False
        del active[picked]
    return True

def _fog_shell_solvable(grid):
    """迷雾模式专用校验：每一步只能选择当前剩余箭头的最外圈。"""
    active = {(r, c): value for r, row in enumerate(grid) for c, value in enumerate(row)
              if value in 'UDLR'}
    while active:
        rows = [pos[0] for pos in active]
        cols = [pos[1] for pos in active]
        top, bottom, left, right = min(rows), max(rows), min(cols), max(cols)
        picked = None
        for (row, col), direction in active.items():
            if row not in (top, bottom) and col not in (left, right):
                continue
            blocked = any(
                (direction == 'U' and other_col == col and other_row < row)
                or (direction == 'D' and other_col == col and other_row > row)
                or (direction == 'L' and other_row == row and other_col < col)
                or (direction == 'R' and other_row == row and other_col > col)
                for (other_row, other_col) in active if (other_row, other_col) != (row, col)
            )
            if not blocked:
                picked = (row, col)
                break
        if picked is None:
            return False
        del active[picked]
    return True

def generate_endless_level(level_num):
    """根据无尽模式关卡序号生成随机关卡：网格尺寸与箭头密度随难度递增。
    level_num 从 0 开始。保证生成的网格一定可解。"""
    # 网格尺寸：第1关3x3，每2关扩大1格，最大6x6（受屏幕尺寸限制）
    size = min(3 + level_num // 2, 6)
    # 箭头密度：随关卡递增，越往后越满，上限0.9
    density = min(0.55 + level_num * 0.05, 0.90)
    arrows = ['U', 'D', 'L', 'R']
    while True:
        grid = []
        for r in range(size):
            row = []
            for c in range(size):
                row.append(random.choice(arrows) if random.random() < density else '.')
            grid.append(row)
        # 至少保证有一支箭
        if any(v in 'UDLR' for row in grid for v in row) and _grid_solvable(grid):
            return grid

def endless_time_limit(level_num):
    """无尽模式每关时间限制，随关卡略增。"""
    return 30 + level_num * 5

def generate_fog_level(level_num):
    """迷雾模式：从5x5起步，高密度，确保外圈亮、内部被黑雾包裹。"""
    size = min(5 + level_num // 2, 6)
    density = min(0.90 + level_num * 0.015, 0.97)
    arrows = ['U', 'D', 'L', 'R']
    while True:
        grid = []
        for r in range(size):
            row = []
            for c in range(size):
                row.append(random.choice(arrows) if random.random() < density else '.')
            grid.append(row)
        if (any(v in 'UDLR' for row in grid for v in row)
                and _grid_solvable(grid) and _fog_shell_solvable(grid)):
            return grid
# ================= 实体类 =================
class Arrow:
    def __init__(self, row, col, direction, offset_x, offset_y, cell_size=CELL_SIZE):
        self.row = row
        self.col = col
        self.direction = direction
        self.state = 'idle'  # 状态：idle(静止), shaking(碰撞晃动), flying(飞出), dead(已清除)
        self.cell_size = cell_size
        # 屏幕中心像素坐标
        self.x = offset_x + col * cell_size + cell_size // 2
        self.y = offset_y + row * cell_size + cell_size // 2
        
        self.shake_timer = 0
        self.vx = 0
        self.vy = 0
        self.speed = 18  # 飞出速度（保留兼容）
        # 流畅飞出：蓄力预备 + 方向单位向量 + 逐步加速
        self.dirx = 0
        self.diry = 0
        self.fly_speed = 0.0
        self.windup_timer = 0
        self.fly_frame = 0
        self.trail = []  # [(x, y, strength)]，让飞出不再像突然消失
        self.is_visible = True  # 迷雾模式：是否已点亮可见
    def update(self):
        """更新箭头状态（动画逻辑）"""
        self.trail = [(x, y, strength * 0.72) for x, y, strength in self.trail
                      if strength * 0.72 > 0.12]
        if self.state == 'shaking':
            self.shake_timer -= 1
            if self.shake_timer <= 0:
                self.state = 'idle'
        elif self.state == 'windup':
            # 短暂蓄力后弹出
            self.windup_timer -= 1
            if self.windup_timer <= 0:
                self.state = 'flying'
                self.fly_speed = 5.0
        elif self.state == 'flying':
            # 加速度：起步慢、越飞越快（指数加速到封顶）
            self.trail.append((self.x, self.y, 1.0))
            self.trail = self.trail[-7:]
            self.fly_frame += 1
            self.fly_speed = min(30.0, self.fly_speed * 1.16 + 0.5)
            self.x += self.dirx * self.fly_speed
            self.y += self.diry * self.fly_speed
            # 飞出屏幕边缘后标记为死亡
            # 在刚越出画面时就结算，离场碎光仍能在可见边缘留下反馈。
            if self.x < -28 or self.x > WIDTH + 28 or self.y < -28 or self.y > HEIGHT + 28:
                self.state = 'dead'
                return True
        return False
    def draw(self, surface):
        """渲染箭头多边形"""
        if self.state == 'dead':
            return
        # 迷雾模式下未点亮：不画箭头本体，问号图标由 Game 层统一绘制
        if not self.is_visible:
            return
            
        dx, dy = 0, 0
        scale = 1.0
        if self.state == 'shaking':
            # 正弦晃动，幅度随剩余时间衰减
            decay = self.shake_timer / 20.0
            offset = math.sin(self.shake_timer * 1.5) * 6 * decay
            if self.direction in ['L', 'R']:
                dx = offset
            else:
                dy = offset
            # 错误点击同时有一点缩放回弹，避免只有生硬的左右晃动。
            scale = 1.0 - math.sin((1 - decay) * math.pi * 3) * 0.07
        elif self.state == 'windup':
            # 蓄力：先向飞行反方向轻微后拉并放大，再弹出
            p = 1 - self.windup_timer / 6.0
            pull = math.sin(p * math.pi)
            dx = -self.dirx * pull * 5
            dy = -self.diry * pull * 5
            scale = 1.0 + pull * 0.12
        # 基础箭头形状（指向上方）
        points = [(0, -22), (-16, 2), (-6, 2), (-6, 22), (6, 22), (6, 2), (16, 2)]

        # 根据方向旋转
        angle = {'U': 0, 'L': -90, 'D': 180, 'R': 90}[self.direction]
        color = ARROW_COLORS[self.direction]

        # 飞行拖尾：由大到小的同色像素片，低帧也能读出速度方向。
        if self.state == 'flying':
            base = (255, 239, 191)
            for tx, ty, strength in self.trail:
                trail_color = tuple(int(base[i] + (color[i] - base[i]) * strength * 0.55) for i in range(3))
                size = max(2, int(6 * strength))
                if self.direction in ['L', 'R']:
                    rect = pygame.Rect(int(tx - size), int(ty - size // 2), size * 2, size)
                else:
                    rect = pygame.Rect(int(tx - size // 2), int(ty - size), size, size * 2)
                pygame.draw.rect(surface, trail_color, rect)

        rad = math.radians(angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)

        rot_points = []
        for px, py in points:
            # 矩阵旋转公式 + 蓄力缩放
            nx = (px * cos_a - py * sin_a) * scale
            ny = (px * sin_a + py * cos_a) * scale
            rot_points.append((self.x + dx + nx, self.y + dy + ny))
            
        pygame.draw.polygon(surface, color, rot_points)
        # 与菜单木框一致的深色像素描边，避免原先的白描边显得像另一套 UI。
        pygame.draw.polygon(surface, WOOD_DARK, rot_points, 4)
# ================= 游戏主类 =================
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("一箭又一箭")
        # 隐藏系统光标，改用自绘像素柯基光标
        pygame.mouse.set_visible(False)
        self.build_cursor()
        # 设置窗口图标
        icon_path = Path(__file__).parent / "assets" / "game-icon.png"
        icon = pygame.image.load(str(icon_path)).convert_alpha()
        pygame.display.set_icon(icon)
        self.clock = pygame.time.Clock()
        # 背景音乐：夏日曼哈顿咖啡店 Jazz（用 macOS 原生 afplay 循环播放）
        bgm_path = str(Path(__file__).parent / "assets" / "bgm.m4a")
        # 循环脚本每秒检测游戏进程是否存活
        # 立即终止当前 afplay 并退出
        parent_pid = os.getpid()
        bgm_script = (
            f'while kill -0 {parent_pid} 2>/dev/null; do '
            f'afplay "{bgm_path}" & APID=$!; '
            f'while kill -0 $APID 2>/dev/null; do '
            f'if ! kill -0 {parent_pid} 2>/dev/null; then kill -9 $APID 2>/dev/null; exit 0; fi; '
            f'sleep 1; done; done'
        )
        self.bgm_process = subprocess.Popen(
            bgm_script,
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        # 交互音效由 pygame 混音器播放，与外部循环 BGM 分开；无音频设备时自动降级。
        self.sfx = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            sfx_specs = {
                'cast': ('sfx_cast.wav', 0.34),
                'error': ('sfx_error.wav', 0.34),
                'hint': ('sfx_hint.wav', 0.26),
                'win': ('sfx_win.wav', 0.32),
            }
            for name, (filename, volume) in sfx_specs.items():
                sound = pygame.mixer.Sound(str(Path(__file__).parent / 'assets' / filename))
                sound.set_volume(volume)
                self.sfx[name] = sound
        except pygame.error:
            self.sfx = {}
        # 柯基精灵
        sprite_path = Path(__file__).parent / "assets" / "corgi-reference-sprite.png"
        self.corgi_sprite = pygame.image.load(str(sprite_path)).convert_alpha()
        self.corgi_sprite = pygame.transform.scale(self.corgi_sprite, (140, 216))
        star_path = Path(__file__).parent / "assets" / "luck-star-reference.png"
        self.luck_star_sprite = pygame.image.load(str(star_path)).convert_alpha()
        self.luck_star_sprite = pygame.transform.smoothscale(self.luck_star_sprite, (28, 28))
        rating_star_path = Path(__file__).parent / "assets" / "clear-rating-star.png"
        self.clear_rating_star = pygame.image.load(str(rating_star_path)).convert_alpha()
        self.clear_rating_star = pygame.transform.smoothscale(self.clear_rating_star, (47, 46))
        # 失误爱心图标
        heart_path = Path(__file__).parent / "assets" / "heart.png"
        self.heart_sprite = pygame.image.load(str(heart_path)).convert_alpha()
        self.heart_sprite = pygame.transform.scale(self.heart_sprite, (30, 26))
        # 灰色版本（已消耗）
        self.heart_gray = pygame.transform.grayscale(self.heart_sprite)
        self.heart_gray.set_alpha(100)
        # 时间进度条骨头图标
        bone_path = Path(__file__).parent / "assets" / "bone.png"
        self.bone_sprite = pygame.image.load(str(bone_path)).convert_alpha()
        # 跑动柯基（四帧：蹲伏蓄力、跳起伸展、下落收腿、落地前伸）
        self.corgi_run_frames = []
        for i in range(1, 5):
            p = Path(__file__).parent / "assets" / f"corgi-run-{i}.png"
            img = pygame.image.load(str(p)).convert_alpha()
            self.corgi_run_frames.append(pygame.transform.scale(img, (60, int(60 * img.get_height() / img.get_width()))))
        # 宝箱（AI提示按钮）
        chest_path = Path(__file__).parent / "assets" / "chest.png"
        self.chest_sprite = pygame.image.load(str(chest_path)).convert_alpha()
        self.chest_sprite = pygame.transform.scale(self.chest_sprite, (56, 44))
        # 迷雾模式未点亮问号图标（用户抠图）
        fog_path = Path(__file__).parent / "assets" / "arrow.PNG"
        self.fog_sprite = pygame.image.load(str(fog_path)).convert_alpha()
        self.fog_sprite = pygame.transform.scale(self.fog_sprite, (50, 52))
        # 通关皇冠小狗
        dog_path = Path(__file__).parent / "assets" / "pass.PNG"
        self.pass_dog = pygame.image.load(str(dog_path)).convert_alpha()
        self.pass_dog = pygame.transform.scale(self.pass_dog, (130, 192))
        cry_dog_path = Path(__file__).parent / "assets" / "crying-dog.png"
        self.crying_dog = pygame.image.load(str(cry_dog_path)).convert_alpha()
        self.crying_dog = pygame.transform.smoothscale(self.crying_dog, (132, 152))
        # 菜单海面可钓目标：用户提供的调色板、四叶草与问号卡片。
        self.menu_fishing_sprites = {
            'basic': pygame.transform.smoothscale(pygame.image.load(str(Path(__file__).parent / 'assets' / 'fishing-palette.png')).convert_alpha(), (66, 59)),
            'endless': pygame.transform.smoothscale(pygame.image.load(str(Path(__file__).parent / 'assets' / 'lucky-clover.png')).convert_alpha(), (58, 56)),
            'fog': pygame.transform.smoothscale(pygame.image.load(str(Path(__file__).parent / 'assets' / 'mystery-card.png')).convert_alpha(), (53, 56)),
        }
        
        # 兼容系统的中文字体加载
        self.font_title = self.get_chinese_font(50)
        self.font_normal = self.get_chinese_font(28)
        self.font_small = self.get_chinese_font(20)
        self.font_pass = self.get_chinese_font(72)
        self.font_menu_title = self.get_chinese_font(36)
        
        # 游戏全局变量
        self.state = 'MENU'  # MENU, FISHING_RESULT, PLAYING, LEVEL_CLEAR, GAME_OVER, VICTORY
        self.game_mode = 'basic'  # 'basic' 基础模式 | 'endless' 无尽模式
        self.level_index = 0
        self.max_mistakes = 5
        self.mistakes = self.max_mistakes
        self.game_over_reason = None  # 'mistakes' | 'deadlock' | None
        self.current_stars = 1  # 本关通关星级 1~3
        self.clear_time = 0.0   # 本关通关用时（秒）
        self.total_clear_time = 0.0  # 当前基础模式流程的累计通关用时
        self.total_mistakes = 0      # 当前基础模式流程的累计失误次数
        self.clear_anim_start = 0  # 通关动画起始时间
        self.confetti = []   # 彩屑粒子
        self.fireworks = []  # 烟花粒子
        self.fw_timer = 0.0  # 烟花计时
        self.arrow_effects = []  # 关卡内：起飞、碰撞、离场的短促像素粒子
        
        self.arrows = []
        self.grid_rows = 0
        self.grid_cols = 0
        self.cell_size = CELL_SIZE
        self.board_offset_x = 0
        self.board_offset_y = 150
        self.level_start_time = 0  # 关卡开始时间
        
        # 按钮区域定义
        self.btn_restart = pygame.Rect(462, 13, 114, 88)
        self.btn_center = pygame.Rect(WIDTH//2 - 130, 628, 260, 58)
        # 主菜单三个模式按钮（并排）
        self.btn_basic = pygame.Rect(114, 628, 120, 58)
        self.btn_endless = pygame.Rect(240, 628, 120, 58)
        self.btn_fog = pygame.Rect(366, 628, 120, 58)
        # 菜单钓鱼选模式：三个可钓目标与一次短暂的甩线动画。
        self.fishing_mode_targets = {
            'basic': pygame.Rect(48, 542, 128, 110),
            'endless': pygame.Rect(237, 626, 128, 104),
            'fog': pygame.Rect(424, 560, 128, 110),
        }
        self.fishing_target_lanes = {
            'basic': (570, 0.86, 0.1),
            'endless': (645, 0.63, 2.2),
            'fog': (690, 0.76, 4.1),
        }
        self.menu_cast_mode = None
        self.menu_cast_start = 0
        self.menu_cast_target = None
        self.fishing_result_mode = None
        self.fishing_result_start = 0
        self.btn_fishing_cancel = pygame.Rect(0, 0, 0, 0)
        self.btn_fishing_confirm = pygame.Rect(0, 0, 0, 0)
        self.btn_fishing_close = pygame.Rect(0, 0, 0, 0)
        # AI提示宝箱（位置随棋盘大小动态计算）
        self.chest_rect = pygame.Rect(0, 0, 56, 44)
        # 返回菜单柯基按钮（位置动态计算）
        self.corgi_btn_rect = pygame.Rect(0, 0, 60, 56)
        self.hint_arrow_idx = -1   # 被提示高亮的箭头索引
        self.hint_timer = 0        # 提示剩余帧数

    def play_sfx(self, name):
        """播放短交互音；混音器不可用或音效缺失时保持静默。"""
        sound = self.sfx.get(name)
        if sound is not None:
            sound.play()

    def build_cursor(self):
        """加载用户自制像素柯基光标，最近邻缩放到与系统光标相近的尺寸。"""
        try:
            cursor_path = Path(__file__).parent / 'assets' / 'corgi-cursor-pixel.png'
            img = pygame.image.load(str(cursor_path)).convert_alpha()
            # 原图 64x76，缩到 10x10（最近邻保留硬边像素）
            self.cursor_surf = pygame.transform.scale(img, (32, 32))
            # 箭头尖（热点）缩放后约在 (1,0)
            self.cursor_hot = (0, 0)
        except (pygame.error, FileNotFoundError):
            pygame.mouse.set_visible(True)
            self.cursor_surf = None

    def draw_custom_cursor(self):
        """每帧最上层绘制像素光标，热点对齐鼠标；按下时轻微右下偏移。"""
        if self.cursor_surf is None:
            return
        cmx, cmy = pygame.mouse.get_pos()
        hx, hy = self.cursor_hot
        ox, oy = (1, 1) if pygame.mouse.get_pressed()[0] else (0, 0)
        self.screen.blit(self.cursor_surf, (cmx - hx + ox, cmy - hy + oy))

    def get_chinese_font(self, size):
        """加载像素风中文字体，回退到系统字体"""
        # 优先使用缝合像素字体
        pixel_font = Path(__file__).parent / "assets" / "fusion-pixel-12px-monospaced-zh_hans.ttf"
        if pixel_font.exists():
            return pygame.font.Font(str(pixel_font), size)
        # 回退到系统字体
        fonts = ['pingfangsc', 'pingfang', 'heiti', 'stheitisc', 'kaiti', 'microsoftyahei', 'simhei', 'simsun']
        for f in fonts:
            path = pygame.font.match_font(f)
            if path: return pygame.font.Font(path, size)
        return pygame.font.Font(None, size)
    def load_level(self):
        """加载当前关卡"""
        self.arrows.clear()
        self.arrow_effects.clear()
        self.mistakes = self.max_mistakes
        self.game_over_reason = None
        self.level_start_time = pygame.time.get_ticks()
        self.hint_arrow_idx = -1
        self.hint_timer = 0
        # 基础模式用固定关卡表；无尽/迷雾模式按序号生成随机关卡
        if self.game_mode == 'endless':
            grid = generate_endless_level(self.level_index)
        elif self.game_mode == 'fog':
            grid = generate_fog_level(self.level_index)
        else:
            grid = LEVELS[self.level_index]
        self.grid_rows = len(grid)
        self.grid_cols = len(grid[0])
        self.grid_map = [list(row) for row in grid]
        
        # 大棋盘（如6x6）适当缩小格子，避免与左右宝箱/柯基按钮重叠；
        # 水平安全区约 x=88~512（宽424），垂直安全区高约470。
        self.cell_size = min(CELL_SIZE, 400 // self.grid_cols, 470 // self.grid_rows)
        cs = self.cell_size
        # 居中计算
        board_w = self.grid_cols * cs
        board_h = self.grid_rows * cs
        self.board_offset_x = (WIDTH - board_w) // 2
        # 草坪区域 y=216~636，考虑底部河岸与水面视觉重量，取视觉中心略偏上
        grass_center_y = 380
        # 外框中心 = board_offset_y - 22 + (board_h + 44)/2 = board_offset_y + board_h/2
        self.board_offset_y = grass_center_y - board_h // 2
        
        for r in range(self.grid_rows):
            for c in range(self.grid_cols):
                val = grid[r][c]
                if val in ['U', 'D', 'L', 'R']:
                    self.arrows.append(Arrow(r, c, val, self.board_offset_x, self.board_offset_y, self.cell_size))
    def get_time_limit(self):
        """当前关卡时间限制（秒），基础模式取表，无尽/迷雾模式按序号动态计算。"""
        if self.game_mode in ('endless', 'fog'):
            return endless_time_limit(self.level_index)
        return LEVEL_TIME_LIMIT[self.level_index]

    def recompute_fog(self):
        """迷雾模式可见性：仅当前剩余箭头的动态最外圈可见。"""
        for a in self.arrows:
            a.is_visible = True
        if self.game_mode != 'fog':
            return
        active = [a for a in self.arrows if a.state != 'dead']
        if not active:
            return
        top = min(a.row for a in active)
        bottom = max(a.row for a in active)
        left = min(a.col for a in active)
        right = max(a.col for a in active)
        for arrow in active:
            arrow.is_visible = (arrow.row in (top, bottom)
                                or arrow.col in (left, right))
    def is_path_blocked(self, arrow):
        """核心算法：路径阻挡检测"""
        for other in self.arrows:
            # 忽略自己和已经飞走/消除的箭头
            if other == arrow or other.state in ['flying', 'dead']:
                continue
                
            # 根据方向，判断是否存在阻挡物
            if arrow.direction == 'U' and other.col == arrow.col and other.row < arrow.row: return True
            if arrow.direction == 'D' and other.col == arrow.col and other.row > arrow.row: return True
            if arrow.direction == 'L' and other.row == arrow.row and other.col < arrow.col: return True
            if arrow.direction == 'R' and other.row == arrow.row and other.col > arrow.col: return True
            
        return False
    def handle_click(self, mx, my):
        """处理鼠标点击事件"""
        # 0. 点击返回菜单柯基
        if self.corgi_btn_rect.collidepoint(mx, my):
            self.state = 'MENU'
            return
        # 1. 点击AI提示宝箱
        if self.chest_rect.collidepoint(mx, my):
            self.trigger_hint()
            return
        # 2. 点击重新开始按钮
        if self.btn_restart.collidepoint(mx, my):
            self.load_level()
            return
            
        # 2. 点击箭头
        for arrow in self.arrows:
            if arrow.state == 'idle':
                # 勾股定理判断点击是否在箭头中心圆角范围内
                dist = math.hypot(mx - arrow.x, my - arrow.y)
                if dist < self.cell_size // 2:
                    if self.is_path_blocked(arrow):
                        # 阻挡：执行晃动动画并扣除生命
                        arrow.state = 'shaking'
                        arrow.shake_timer = 22
                        self.mistakes -= 1
                        self.spawn_arrow_effect(arrow.x, arrow.y, ARROW_COLORS[arrow.direction], 'error')
                        self.play_sfx('error')
                    else:
                        # 只有棋盘最外圈的箭头有后拉蓄力；内部箭头保持直接飞出，
                        # 避免棋盘中部每次消除都出现不必要的回拉动作。
                        is_outer = (arrow.row in (0, self.grid_rows - 1)
                                    or arrow.col in (0, self.grid_cols - 1))
                        dvec = {'U': (0, -1), 'D': (0, 1),
                                'L': (-1, 0), 'R': (1, 0)}[arrow.direction]
                        arrow.dirx, arrow.diry = dvec
                        arrow.fly_speed = 5.0
                        if is_outer:
                            arrow.state = 'windup'
                            arrow.windup_timer = 7
                        else:
                            arrow.state = 'flying'
                        self.spawn_arrow_effect(arrow.x, arrow.y, ARROW_COLORS[arrow.direction],
                                                'launch', arrow.dirx, arrow.diry)
                    break # 每次点击只触发一个
    def draw_text(self, text, font, color, x, y, center=False):
        """辅助渲染文字（轻微像素加粗）"""
        surf = font.render(text, True, color)
        # 轻微加粗：右下偏移1像素，Surface 多留1像素避免裁剪
        bold = pygame.Surface((surf.get_width() + 1, surf.get_height() + 1), pygame.SRCALPHA)
        bold.blit(font.render(text, True, color), (1, 1))
        bold.blit(surf, (0, 0))
        rect = bold.get_rect()
        if center:
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        self.screen.blit(bold, rect)

    def draw_button(self, rect, text):
        """辅助渲染按钮"""
        mx, my = pygame.mouse.get_pos()
        color = BTN_HOVER if rect.collidepoint(mx, my) else BTN_COLOR
        pygame.draw.rect(self.screen, color, rect, border_radius=8)
        self.draw_text(text, self.font_normal, (255,255,255), rect.centerx, rect.centery, center=True)

    # ================= 原创像素风主菜单 =================
    def draw_pixel_cloud(self, x, y):
        """用整数网格绘制一朵轻量的像素云。"""
        cloud = (239, 250, 251)
        for rx, ry, rw, rh in [(0, 12, 80, 18), (14, 4, 36, 24), (44, 0, 26, 30)]:
            pygame.draw.rect(self.screen, cloud, (x + rx, y + ry, rw, rh))

    def draw_tree(self, x, y, scale=1):
        """原创场景树：粗颗粒树冠和木色树干。"""
        trunk_w = 12 * scale
        pygame.draw.rect(self.screen, WOOD_DARK, (x + 34 * scale, y + 54 * scale, trunk_w, 55 * scale))
        pygame.draw.rect(self.screen, WOOD, (x + 37 * scale, y + 54 * scale, 5 * scale, 55 * scale))
        leaf = GRASS_DARK
        leaf_light = (76, 153, 61)
        pygame.draw.rect(self.screen, leaf, (x, y + 28 * scale, 80 * scale, 36 * scale))
        pygame.draw.rect(self.screen, leaf, (x + 10 * scale, y + 10 * scale, 58 * scale, 42 * scale))
        pygame.draw.rect(self.screen, leaf_light, (x + 18 * scale, y, 34 * scale, 30 * scale))
        pygame.draw.rect(self.screen, (102, 183, 73), (x + 28 * scale, y + 17 * scale, 12 * scale, 10 * scale))

    def draw_pixel_flower(self, x, y, petal, center):
        """参考草坪里的小花：不画十字，使用错位花瓣、花心、茎和小叶。"""
        stem = (49, 122, 53)
        stem_light = (78, 153, 61)
        shade = tuple(max(0, c - 32) for c in petal)
        # 细茎与一片偏侧的小叶，花朵不会像界面符号一样悬空。
        pygame.draw.rect(self.screen, stem, (x + 7, y + 14, 4, 13))
        pygame.draw.rect(self.screen, stem_light, (x + 8, y + 15, 2, 11))
        pygame.draw.rect(self.screen, stem, (x + 2, y + 20, 6, 4))
        pygame.draw.rect(self.screen, stem_light, (x + 3, y + 19, 5, 3))
        # 四片方形花瓣错开半格，中心略高，保留参考图的像素花轮廓。
        pygame.draw.rect(self.screen, shade, (x + 5, y, 7, 7))
        pygame.draw.rect(self.screen, petal, (x + 6, y + 1, 5, 6))
        pygame.draw.rect(self.screen, shade, (x, y + 6, 7, 7))
        pygame.draw.rect(self.screen, petal, (x + 1, y + 6, 6, 5))
        pygame.draw.rect(self.screen, shade, (x + 11, y + 5, 7, 7))
        pygame.draw.rect(self.screen, petal, (x + 11, y + 6, 6, 5))
        pygame.draw.rect(self.screen, shade, (x + 6, y + 11, 7, 6))
        pygame.draw.rect(self.screen, petal, (x + 7, y + 11, 5, 4))
        pygame.draw.rect(self.screen, center, (x + 6, y + 6, 6, 6))
        pygame.draw.rect(self.screen, (255, 239, 137), (x + 7, y + 7, 4, 3))

    def draw_pixel_fishing_rod(self, start, tip):
        """严格按参考图等比缩小：脚边小黑握块 → 暖褐细主杆 → 深棕后段 → 短竿尖。"""
        sx, sy = start
        tx, ty = tip
        # 1) 紧贴脚边的独立小黑方块（约 9px），不与脚掌相连。
        pygame.draw.rect(self.screen, (43, 31, 23), (sx - 5, sy - 5, 10, 10))
        pygame.draw.rect(self.screen, (56, 38, 25), (sx - 4, sy - 4, 8, 8))
        # 2) 木杆从黑块右缘伸出，前半段暖褐，非抗锯齿线保留像素阶梯。
        ox, oy = sx + 4, sy
        joint = (int(ox + (tx - ox) * 0.63), int(oy + (ty - oy) * 0.63))
        pygame.draw.line(self.screen, (86, 49, 25), (ox, oy), joint, 5)
        pygame.draw.line(self.screen, (145, 81, 39), (ox, oy - 1), (joint[0], joint[1] - 1), 3)
        pygame.draw.line(self.screen, (164, 94, 45), (ox + 1, oy - 2), (joint[0], joint[1] - 2), 1)
        # 3) 后半段深棕、更细，末端压成短横块。
        pygame.draw.line(self.screen, (57, 36, 22), joint, tip, 3)
        pygame.draw.line(self.screen, (92, 51, 26), (joint[0], joint[1] - 1), (tx, ty - 1), 2)
        pygame.draw.rect(self.screen, (57, 36, 22), (tx - 3, ty - 2, 7, 4))
        pygame.draw.rect(self.screen, (85, 48, 25), (tx - 3, ty - 2, 5, 2))

    def draw_panel(self, rect):
        """奶油色信息卡，采用深棕描边与像素投影。"""
        shadow = rect.move(0, 6)
        pygame.draw.rect(self.screen, WOOD_DARK, shadow, border_radius=15)
        pygame.draw.rect(self.screen, BROWN, rect, border_radius=15)
        inner = rect.inflate(-10, -10)
        pygame.draw.rect(self.screen, CREAM, inner, border_radius=10)
        pygame.draw.line(self.screen, (255, 252, 223), (inner.left + 8, inner.top + 5),
                         (inner.right - 8, inner.top + 5), 2)

    def draw_reference_corgi(self, cx, bottom_y):
        rect = self.corgi_sprite.get_rect(midbottom=(cx, bottom_y))
        # 阴影收在草地范围内，避免与河岸的深色边线叠在一起而吃掉脚掌轮廓。
        pygame.draw.ellipse(self.screen, (49, 116, 66), (cx - 55, bottom_y - 10, 110, 10))
        self.screen.blit(self.corgi_sprite, rect)

    def draw_running_corgi(self, cx, base_y, excited=False):
        """跑动的像素柯基：蹲伏→跳起伸展→下落收腿→落地，四帧循环。"""
        t = pygame.time.get_ticks() / 1000
        cycle_dur = 0.6 if excited else 0.9
        hop_h = 15 if excited else 11
        cycle = (t / cycle_dur) % 1
        # 空中阶段 0.2~0.72，一条连续抛物线（中点0.46最高）
        air_lo, air_hi = 0.20, 0.72
        if cycle < air_lo:
            # 蹲伏蓄力（贴地）
            frame = self.corgi_run_frames[0]
            y = base_y
        elif cycle < 0.46:
            # 跳起伸展：上升到最高点
            frame = self.corgi_run_frames[1]
            p = (cycle - air_lo) / (0.46 - air_lo)
            y = base_y - math.sin(p * math.pi / 2) * hop_h
        elif cycle < air_hi:
            # 下落收腿衔接：从最高点下降
            frame = self.corgi_run_frames[2]
            p = (cycle - 0.46) / (air_hi - 0.46)
            y = base_y - math.cos(p * math.pi / 2) * hop_h
        else:
            # 落地前伸（贴地）
            frame = self.corgi_run_frames[3]
            y = base_y
        rect = frame.get_rect(midbottom=(cx, int(y)))
        # 地面阴影随高度变化
        height = base_y - y
        shadow_scale = max(0.6, 1 - height / 20)
        shadow_w = int(40 * shadow_scale)
        shadow_alpha = int(120 * shadow_scale)
        shadow_surf = pygame.Surface((shadow_w, 6), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (49, 116, 66, shadow_alpha), (0, 0, shadow_w, 6))
        self.screen.blit(shadow_surf, (cx - shadow_w // 2, base_y - 4))
        self.screen.blit(frame, rect)

    def draw_hint_chest(self):
        """关卡内的AI提示宝箱按钮，轻微弹跳+闪光，点击高亮一个可消除箭头。"""
        # 固定在棋盘左侧的草坪安全区。大棋盘也不会把图标或文字挤到河岸上。
        cx, cy = 48, 548
        self.chest_rect = pygame.Rect(cx - 28, cy - 22, 56, 44)

        t = pygame.time.get_ticks() / 1000
        hovering = self.chest_rect.collidepoint(pygame.mouse.get_pos())
        # 鼠标悬停或提示激活时跳得更欢
        amp = 7 if (hovering or self.hint_timer > 0) else 3
        bounce = abs(math.sin(t * 4)) * amp
        tilt = math.sin(t * 4) * (10 if hovering else 5)

        # 地面阴影
        pygame.draw.ellipse(self.screen, (49, 116, 66),
                            (cx - 24, cy + 18, 48, 7))
        rotated = pygame.transform.rotate(self.chest_sprite, tilt)
        rect = rotated.get_rect(center=(cx, int(cy - bounce)))
        self.screen.blit(rotated, rect)

        # 金色闪光
        for side in [-1, 1]:
            for i in range(2):
                phase = (t * 3 + i * 0.4 + (0 if side < 0 else 0.5)) % 1
                sx = cx + side * (26 + i * 5)
                sy = cy - bounce + (i - 0.5) * 14
                alpha = int(255 * (1 - abs(phase - 0.5) * 2))
                size = int(1 + 2 * math.sin(phase * math.pi))
                if size > 0 and alpha > 0:
                    sparkle = pygame.Surface((size * 4 + 2, size * 4 + 2), pygame.SRCALPHA)
                    c = (255, 220, 60, max(0, alpha))
                    pygame.draw.line(sparkle, c, (size*2, 0), (size*2, size*4), 1)
                    pygame.draw.line(sparkle, c, (0, size*2), (size*4, size*2), 1)
                    self.screen.blit(sparkle, (sx - size*2, sy - size*2))

        # 提示文字
        self.draw_text("AI提示", self.font_small, BROWN, cx, cy + 31, center=True)

    def trigger_hint(self):
        """找到一个可以安全消除的箭头并高亮提示（迷雾模式只提示已点亮的）。"""
        for i, arrow in enumerate(self.arrows):
            if (arrow.state == 'idle' and arrow.is_visible
                    and not self.is_path_blocked(arrow)):
                self.hint_arrow_idx = i
                self.hint_timer = 90  # 约1.5秒
                self.play_sfx('hint')
                return True
        return False

    def spawn_arrow_effect(self, x, y, color, kind, dirx=0, diry=0):
        """生成短生命周期像素粒子：起飞向前、失误向外、离场更明亮。"""
        count = {'launch': 6, 'error': 8, 'exit': 13}[kind]
        life = {'launch': 0.24, 'error': 0.34, 'exit': 0.46}[kind]
        for i in range(count):
            angle = math.tau * i / count + random.uniform(-0.18, 0.18)
            speed = random.uniform(1.2, 3.0) + (1.6 if kind == 'exit' else 0)
            vx = math.cos(angle) * speed + dirx * (2.8 if kind == 'launch' else 0)
            vy = math.sin(angle) * speed + diry * (2.8 if kind == 'launch' else 0)
            particle_color = (229, 89, 78) if kind == 'error' else color
            if kind == 'exit' and i % 3 == 0:
                particle_color = (255, 236, 151)
            self.arrow_effects.append({
                'x': x, 'y': y, 'vx': vx, 'vy': vy,
                'life': life, 'max_life': life, 'color': particle_color,
                'size': 4 if i % 3 else 6,
            })

    def update_draw_arrow_effects(self):
        """更新并绘制箭头粒子。它们只在棋盘上短暂存在，不影响点击规则。"""
        layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        alive = []
        for particle in self.arrow_effects:
            particle['x'] += particle['vx']
            particle['y'] += particle['vy']
            particle['vy'] += 0.08
            particle['vx'] *= 0.95
            particle['life'] -= 1 / FPS
            if particle['life'] <= 0:
                continue
            alpha = int(255 * particle['life'] / particle['max_life'])
            size = max(2, int(particle['size'] * (0.55 + 0.45 * particle['life'] / particle['max_life'])))
            pygame.draw.rect(layer, (*particle['color'], alpha),
                             (int(particle['x'] - size / 2), int(particle['y'] - size / 2), size, size))
            alive.append(particle)
        self.arrow_effects = alive
        self.screen.blit(layer, (0, 0))

    def draw_menu_corgi_button(self):
        """关卡右下角的跑动柯基，点击返回主菜单。"""
        # 与宝箱对称地放在右侧草坪，文字底部仍高于 y=622 的河岸。
        cx, base_y = 552, 569
        # 点击区域（比精灵略大，方便点）
        self.corgi_btn_rect = pygame.Rect(cx - 32, base_y - 52, 64, 56)
        hovering = self.corgi_btn_rect.collidepoint(pygame.mouse.get_pos())
        # 悬停时略微放大跳动
        self.draw_running_corgi(cx, base_y, excited=hovering)
        # 文字与狗狗的间距对齐宝箱“AI提示”（图标底缘下约 10px）
        self.draw_text("菜单", self.font_small, BROWN, cx, base_y + 10, center=True)

    def _star_points(self, cx, cy, r_outer, r_inner):
        pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            r = r_outer if i % 2 == 0 else r_inner
            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
        return pts

    def setup_clear_particles(self):
        """通关庆祝：预渲染放射光、光晕、初始化彩屑。"""
        self.confetti = []
        self.fireworks = []
        self.fw_timer = 0.0
        palette = [(255,205,70),(230,110,110),(120,190,240),(130,220,170),
                   (255,160,200),(255,170,90),(200,160,255)]
        for _ in range(70):
            self.confetti.append({
                'x': random.uniform(0, WIDTH),
                'y': random.uniform(-80, HEIGHT),
                'vy': random.uniform(1.0, 2.2),
                'sway': random.uniform(0.5, 1.6),
                'ph': random.uniform(0, 6.28),
                'w': random.randint(5, 9),
                'h': random.randint(8, 13),
                'color': random.choice(palette),
            })
        # 预渲染放射光芒（16 条黄色楔形，缓慢旋转）
        self.radial_img = pygame.Surface((800, 800), pygame.SRCALPHA)
        cx = cy = 400
        rays = 8
        inner = 110
        R = 620
        for i in range(rays):
            ang = i * (6.28318 / rays)
            spread = 0.26
            # 宽光带：根部也有宽度，外端更宽，半径足够覆盖到界面最底端
            x0a = cx + math.cos(ang - spread*0.5) * inner
            y0a = cy + math.sin(ang - spread*0.5) * inner
            x0b = cx + math.cos(ang + spread*0.5) * inner
            y0b = cy + math.sin(ang + spread*0.5) * inner
            x1 = cx + math.cos(ang - spread) * R
            y1 = cy + math.sin(ang - spread) * R
            x2 = cx + math.cos(ang + spread) * R
            y2 = cy + math.sin(ang + spread) * R
            a = 80 if i % 2 == 0 else 48
            pygame.draw.polygon(self.radial_img, (255, 238, 175, a),
                                [(x0a, y0a), (x1, y1), (x2, y2), (x0b, y0b)])
        # 预渲染中心光晕（奶油黄径向渐变圆）
        self.glow_img = pygame.Surface((360, 360), pygame.SRCALPHA)
        gc = 180
        for r in range(180, 0, -8):
            a = int(130 * (1 - r / 180) ** 1.5)
            pygame.draw.circle(self.glow_img, (255, 238, 170, a), (gc, gc), r)

    def spawn_firework(self):
        """在顶部随机位置绽放一朵像素烟花。"""
        palette = [(255,210,80),(255,120,120),(120,200,255),(160,255,170),(255,170,220)]
        cx = random.uniform(80, WIDTH - 80)
        cy = random.uniform(90, 200)
        color = random.choice(palette)
        for _ in range(26):
            ang = random.uniform(0, 6.28)
            spd = random.uniform(1.5, 3.8)
            self.fireworks.append({
                'x': cx, 'y': cy,
                'vx': math.cos(ang) * spd,
                'vy': math.sin(ang) * spd,
                'life': random.uniform(0.7, 1.2),
                'color': color,
            })

    def update_draw_clear_particles(self, t):
        """更新并绘制彩屑与烟花（在元素背后绘制）。"""
        # 烟花定时绽放
        self.fw_timer += 1.0 / 60
        if self.fw_timer >= 0.85:
            self.fw_timer = 0.0
            self.spawn_firework()
        # 彩屑下落摇摆
        for p in self.confetti:
            p['ph'] += 0.04 * p['sway']
            p['y'] += p['vy']
            p['x'] += math.sin(p['ph']) * 0.6
            if p['y'] > HEIGHT + 20:
                p['y'] = -20
                p['x'] = random.uniform(0, WIDTH)
            rect = pygame.Rect(int(p['x']), int(p['y']), p['w'], p['h'])
            self.screen.fill(p['color'], rect)
        # 烟花粒子扩散衰减
        for f in self.fireworks:
            f['x'] += f['vx']
            f['y'] += f['vy']
            f['vy'] += 0.03
            f['vx'] *= 0.985
            f['vy'] *= 0.985
            f['life'] -= 1.0 / 60
        self.fireworks = [f for f in self.fireworks if f['life'] > 0]
        for f in self.fireworks:
            a = max(0.0, min(1.0, f['life']))
            col = tuple(int(c * a + 255 * (1 - a) * 0.2) for c in f['color'])
            pygame.draw.circle(self.screen, f['color'], (int(f['x']), int(f['y'])), 3)

    def draw_mode_button(self, rect, title, subtitle, highlight_color):
        """主菜单模式选择按钮：木框卡片，标题+副标题。"""
        mx, my = pygame.mouse.get_pos()
        hovering = rect.collidepoint(mx, my)
        offset_y = -2 if hovering else 0
        draw_rect = rect.move(0, offset_y)
        pygame.draw.rect(self.screen, WOOD_DARK, draw_rect.move(0, 6), border_radius=16)
        pygame.draw.rect(self.screen, BROWN, draw_rect, border_radius=16)
        pygame.draw.rect(self.screen, highlight_color if hovering else CREAM,
                         draw_rect.inflate(-9, -9), border_radius=11)
        self.draw_text(title, self.font_small, BROWN, draw_rect.centerx, draw_rect.centery - 10, center=True)
        self.draw_text(subtitle, self.font_small, (137, 91, 48), draw_rect.centerx, draw_rect.centery + 14, center=True)

    def draw_menu_buttons(self):
        """主菜单三个模式入口。"""
        self.draw_mode_button(self.btn_basic, "基础模式", "3 关经典", (255, 248, 225))
        self.draw_mode_button(self.btn_endless, "无尽模式", "无限递增", (255, 236, 180))
        self.draw_mode_button(self.btn_fog, "迷雾模式", "盲猜探索", (230, 230, 220))

    def start_game_mode(self, mode):
        """完成甩线后进入对应模式，并初始化本轮累计数据。"""
        self.game_mode = mode
        self.total_clear_time = 0.0
        self.total_mistakes = 0
        self.level_index = 0
        self.menu_cast_mode = None
        self.menu_cast_target = None
        self.cast_reeling = False
        self._reel_hook = None
        self.fishing_result_mode = None
        self.load_level()
        self.state = 'PLAYING'

    def get_menu_fishing_target_rect(self, mode):
        """匀速缓慢左右漂移（三角波往返），同步点击区域。"""
        lane_y, speed, phase = self.fishing_target_lanes[mode]
        t = pygame.time.get_ticks() / 1000
        period = 2 * math.pi / speed
        ph = ((t / period + phase / (2 * math.pi)) % 2.0)
        k = ph * 2 - 1 if ph < 1.0 else (2 - ph) * 2 - 1
        x = WIDTH // 2 + k * 216
        rect = pygame.Rect(int(x - 56), lane_y - 48, 112, 102)
        self.fishing_mode_targets[mode] = rect
        return rect

    def draw_menu_fishing_target(self, mode, label, tint):
        """将一个模式画成水上的可钓漂浮物，而非传统菜单按钮。"""
        rect = self.get_menu_fishing_target_rect(mode)
        hovering = rect.collidepoint(pygame.mouse.get_pos()) and self.menu_cast_mode is None
        time_s = pygame.time.get_ticks() / 800
        bob = math.sin(time_s + rect.centerx * 0.035) * 2
        cx, cy = rect.centerx, int(rect.centery + bob)
        if self.menu_cast_mode == mode and self.menu_cast_target:
            cx, cy = self.menu_cast_target

        cast_elapsed = ((pygame.time.get_ticks() - self.menu_cast_start) / 1000.0
                        if self.menu_cast_mode == mode else 0.0)
        # 入水停顿后，目标只有一份，并随鱼钩回到岸边；不再在水面留下重影。
        if self.menu_cast_mode == mode and cast_elapsed >= 0.88:
            if getattr(self, 'cast_reeling', False):
                item = self.menu_fishing_sprites[mode]
                hx, hy = getattr(self, '_reel_hook', (cx, cy))
                # 被钓起后有轻微摆动，像录像里食物挂在线上被收回。
                swing = math.sin(cast_elapsed * 25) * 7
                caught = pygame.transform.rotozoom(item, swing, 1.0)
                self.screen.blit(caught, caught.get_rect(center=(hx, hy + int(math.sin(cast_elapsed * 31) * 2))))
            return

        # 水面淡椭圆水影（无额外弧线）
        pygame.draw.ellipse(self.screen, WATER_DARK, (cx - 38, cy + 24, 76, 10))
        item = self.menu_fishing_sprites[mode]
        # 钩子碰到目标的一瞬间，素材会有很短的受力震颤与放大回弹。
        impact_age = cast_elapsed - 0.48
        if 0 <= impact_age < 0.18:
            impact = impact_age / 0.18
            shake = int(math.sin(impact_age * 120) * (1 - impact) * 4)
            scale = 1.0 + math.sin(impact * math.pi) * 0.12
            hit_item = pygame.transform.rotozoom(item, math.sin(impact_age * 95) * 4, scale)
            self.screen.blit(hit_item, hit_item.get_rect(center=(cx + shake, cy - 3)))
        else:
            self.screen.blit(item, item.get_rect(center=(cx, cy - 3)))
        # 小色标用于区分模式，但文字保持简短。
        tag = pygame.Rect(cx - 43, cy + 34, 86, 25)
        pygame.draw.rect(self.screen, (37, 99, 144), tag, border_radius=7)
        pygame.draw.rect(self.screen, tint, tag.inflate(-4, -4), border_radius=5)
        self.draw_text(label, self.font_small, (39, 67, 77), tag.centerx, tag.centery, center=True)

    def draw_menu_fishing_choices(self):
        """绘制海面三种模式目标、鱼线与落钩动画（先算钩子，再画目标）。"""
        # 黑色握块紧贴右前脚脚边（右爪右缘约 x=339、脚面 y≈470~486）。
        rod_start = (345, 474)
        rod_tip = (505, 506)
        hook = rod_tip
        self.cast_reeling = False
        tip = ""
        elapsed = 0.0
        if self.menu_cast_mode:
            target = self.menu_cast_target or self.fishing_mode_targets[self.menu_cast_mode].center
            elapsed = (pygame.time.get_ticks() - self.menu_cast_start) / 1000.0
            # 1) 抛竿：钩子先被甩到远侧，再落入选中物旁。曲线模仿录像里
            #    "先向外拉直、后向下落水" 的走线，而不是直直地戳向目标。
            if elapsed < 0.48:
                k = elapsed / 0.48
                ease = 1 - (1 - k) ** 3
                cast_control = (rod_tip[0] + (target[0] - rod_tip[0]) * 0.78,
                                min(rod_tip[1] - 44, target[1] - 86))
                hook = (
                    int((1-ease)**2 * rod_tip[0] + 2*(1-ease)*ease * cast_control[0] + ease**2 * target[0]),
                    int((1-ease)**2 * rod_tip[1] + 2*(1-ease)*ease * cast_control[1] + ease**2 * target[1]),
                )
                tip = "甩竿中…"
            # 2) 入水：短暂停住，扩散水波，给用户确认“钓中”的反馈。
            elif elapsed < 0.88:
                hook = target
                tip = "上钩啦！"
            # 3) 收线：目标沿向上弧线回到竿尖，完成后再切换模式。
            else:
                self.cast_reeling = True
                k = min(1.0, (elapsed - 0.88) / 0.94)
                ease = 1 - (1 - k) ** 2
                # 收线时先轻轻上提，再朝竿尖收拢，避免素材像直线瞬移。
                control = (target[0] + (rod_tip[0] - target[0]) * 0.2, target[1] - 108)
                hook = (
                    int((1 - ease) ** 2 * target[0] + 2 * (1 - ease) * ease * control[0] + ease ** 2 * rod_tip[0]),
                    int((1 - ease) ** 2 * target[1] + 2 * (1 - ease) * ease * control[1] + ease ** 2 * rod_tip[1]),
                )
                self._reel_hook = hook
                tip = "收杆中…" if k < 0.92 else "钓到了！"
        # 先画漂浮物（收杆阶段被钓的跟随钩子）
        self.draw_menu_fishing_target('basic', '基础', (247, 211, 118))
        self.draw_menu_fishing_target('endless', '无尽', (187, 231, 149))
        self.draw_menu_fishing_target('fog', '迷雾', (183, 207, 228))
        # 收线时只有竿尖极轻微抖动，保留原视频中鱼竿固定在岸上的感觉。
        rod_tip_draw = rod_tip
        if self.menu_cast_mode:
            tremor = 1 if elapsed < 0.48 else 2
            rod_tip_draw = (rod_tip[0] + int(math.sin(elapsed * 42) * tremor), rod_tip[1])
        self.draw_pixel_fishing_rod(rod_start, rod_tip_draw)
        # 录像中的鱼线是绷直的细白线；用一条像素线保持原视频的利落感。
        if self.menu_cast_mode:
            pygame.draw.line(self.screen, (156, 182, 190), rod_tip_draw, hook, 2)
            pygame.draw.line(self.screen, (246, 245, 221), rod_tip_draw, hook, 1)
        # 入水阶段的同心椭圆水波；停留越久，波纹越向外扩展。
        if self.menu_cast_mode and 0.48 <= elapsed < 0.88:
            ripple_progress = (elapsed - 0.48) / 0.40
            for rr in (int(9 + ripple_progress * 15), int(19 + ripple_progress * 22)):
                pygame.draw.arc(self.screen, (205, 194, 118),
                                (hook[0]-rr, hook[1]-rr//2, rr*2, rr),
                                0.2, math.pi - 0.2, 2)
        pygame.draw.rect(self.screen, (104, 91, 67), (hook[0]-2, hook[1]-2, 5, 5))
        pygame.draw.rect(self.screen, (248, 244, 211), (hook[0]-1, hook[1]-2, 3, 3))
        pygame.draw.arc(self.screen, (222, 224, 213), (hook[0]-2, hook[1]+1, 7, 9), 0, math.pi, 1)
        # 收杆钓起时的星星闪光
        if self.cast_reeling and elapsed > 0.82:
            for k in range(3):
                sa = elapsed * 6 + k * 2.1
                sx = hook[0] + math.cos(sa) * 22
                sy = hook[1] + math.sin(sa) * 18
                pygame.draw.circle(self.screen, (255, 230, 110), (int(sx), int(sy)), 3)
        # 上钩后先"震一下再炸开"：短促的像素碎光把收线和结果弹窗衔接起来。
        if self.cast_reeling:
            burst_age = elapsed - 0.88
            if 0 <= burst_age < 0.22:
                p = burst_age / 0.22
                burst = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                for i in range(10):
                    ang = i * math.tau / 10 + 0.18
                    distance = 13 + p * (22 + (i % 3) * 7)
                    sx = int(hook[0] + math.cos(ang) * distance)
                    sy = int(hook[1] + math.sin(ang) * distance * 0.7)
                    size = 4 if i % 2 else 3
                    color = (255, 239, 139, int(235 * (1 - p))) if i % 2 else (250, 250, 224, int(230 * (1 - p)))
                    pygame.draw.rect(burst, color, (sx - size // 2, sy - size // 2, size, size))
                pygame.draw.ellipse(burst, (255, 233, 129, int(190 * (1 - p))),
                                    (hook[0] - int(17 + p * 19), hook[1] - int(7 + p * 9),
                                     int(34 + p * 38), int(14 + p * 18)), 2)
                self.screen.blit(burst, (0, 0))

        if self.menu_cast_mode:
            names = {'basic': '基础模式', 'endless': '无尽模式', 'fog': '迷雾模式'}
            self.draw_text(f"{tip} {names[self.menu_cast_mode]}", self.font_small,
                           (245, 244, 215), WIDTH // 2, 526, center=True)
        else:
            self.draw_text("选择一个漂浮物，甩竿开始冒险", self.font_small,
                           (238, 247, 229), WIDTH // 2, 526, center=True)

    def draw_fishing_result(self):
        """钓中后弹出的模式说明框：沿用参考视频的奶油木框与双按钮结构。"""
        mode = self.fishing_result_mode
        if mode is None:
            return
        details = {
            'basic': {
                'title': '基础模式', 'subtitle': '~ 完成 3 关挑战 ~',
                'rules': ('点击没有被阻挡的箭头，', '让所有箭头逃离棋盘。'),
            },
            'endless': {
                'title': '无尽模式', 'subtitle': '~ 挑战更高关卡 ~',
                'rules': ('关卡会持续升级，箭头不断增加，', '看看你能坚持到第几关。'),
            },
            'fog': {
                'title': '迷雾模式', 'subtitle': '~ 完成 10 关迷雾挑战 ~',
                'rules': ('迷雾会遮住部分箭头，', '找出安全路线再行动。'),
            },
        }[mode]
        t = (pygame.time.get_ticks() - self.fishing_result_start) / 1000.0
        reveal = min(1.0, t / 0.22)
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((26, 52, 54, int(142 * reveal)))
        self.screen.blit(veil, (0, 0))

        # 第一帧的一点暖白闪屏。
        if t < 0.10:
            flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            flash.fill((255, 246, 185, int(58 * (1 - t / 0.10))))
            self.screen.blit(flash, (0, 0))

        # 结果框出现前的碎光爆发：先由中心向外散开，再被木框盖住。
        burst_p = min(1.0, t / 0.30)
        if burst_p < 1.0:
            burst = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            cx, cy = WIDTH // 2, 375
            for i in range(16):
                angle = i * math.tau / 16 + 0.1
                distance = 44 + burst_p * (178 + (i % 4) * 13)
                px = int(cx + math.cos(angle) * distance)
                py = int(cy + math.sin(angle) * distance * 0.76)
                size = 5 if i % 3 == 0 else 3
                color = (255, 224, 103, int(245 * (1 - burst_p))) if i % 2 else (255, 250, 211, int(235 * (1 - burst_p)))
                pygame.draw.rect(burst, color, (px - size // 2, py - size // 2, size, size))
            radius = int(22 + burst_p * 125)
            pygame.draw.ellipse(burst, (255, 239, 158, int(170 * (1 - burst_p))),
                                (cx - radius, cy - radius // 2, radius * 2, radius), 2)
            self.screen.blit(burst, (0, 0))

        # 从下方轻弹入场。
        ease = 1 - (1 - reveal) ** 3
        shake_p = max(0.0, 1.0 - t / 0.14)
        shake_x = int(math.sin(t * 105) * 4 * shake_p)
        shake_y = int(math.sin(t * 78) * 2 * shake_p)
        panel = pygame.Rect(80 + shake_x, int(145 + (1 - ease) * 34 + shake_y), 440, 460)
        pygame.draw.rect(self.screen, (72, 45, 27), panel.move(0, 12), border_radius=26)
        pygame.draw.rect(self.screen, (116, 74, 39), panel, border_radius=26)
        pygame.draw.rect(self.screen, (171, 122, 70), panel.inflate(-8, -8), border_radius=21)
        inner = panel.inflate(-18, -18)
        pygame.draw.rect(self.screen, (255, 244, 207), inner, border_radius=17)
        pygame.draw.line(self.screen, (255, 252, 225),
                         (inner.left + 19, inner.top + 9), (inner.right - 19, inner.top + 9), 2)

        # 角星随时间微转，边缘仍是透明的柔和像素。
        spin = (pygame.time.get_ticks() * 0.12) % 360
        left_star = pygame.transform.rotozoom(self.luck_star_sprite, spin, 1.62)
        right_star = pygame.transform.rotozoom(self.luck_star_sprite, -spin, 1.62)
        self.screen.blit(left_star, left_star.get_rect(center=(panel.left + 2, panel.top + 2)))
        self.screen.blit(right_star, right_star.get_rect(center=(panel.right - 2, panel.top + 2)))

        # 红色关闭键。
        self.btn_fishing_close = pygame.Rect(panel.right - 58, panel.top + 20, 40, 40)
        close = self.btn_fishing_close
        pygame.draw.rect(self.screen, (65, 42, 27), close.move(0, 5), border_radius=10)
        pygame.draw.rect(self.screen, (111, 61, 36), close, border_radius=10)
        pygame.draw.rect(self.screen, (224, 75, 65), close.inflate(-7, -7), border_radius=7)
        self.draw_text('×', self.font_title, (255, 249, 226), close.centerx, close.centery - 2, center=True)

        self.draw_text(details['title'], self.font_title, (89, 55, 31), panel.centerx, panel.top + 52, center=True)
        self.draw_text(details['subtitle'], self.font_normal, (151, 108, 67), panel.centerx, panel.top + 95, center=True)

        # 钓到的素材作为结果物，轻微上下浮动。
        item = self.menu_fishing_sprites[mode]
        item = pygame.transform.rotozoom(item, math.sin(t * 6) * 2, 1.15)
        self.screen.blit(item, item.get_rect(center=(panel.centerx, panel.top + 168 + int(math.sin(t * 5) * 3))))
        self.draw_text('玩法规则', self.font_normal, (105, 65, 35), panel.centerx, panel.top + 218, center=True)

        rule_box = pygame.Rect(panel.left + 36, panel.top + 244, panel.width - 72, 92)
        self.draw_dashed_rect(rule_box, (181, 139, 91), width=3, dash=11, gap=8)
        self.draw_text(details['rules'][0], self.font_small, (100, 62, 36), rule_box.centerx,
                       rule_box.top + 30, center=True)
        self.draw_text(details['rules'][1], self.font_small, (100, 62, 36), rule_box.centerx,
                       rule_box.top + 62, center=True)

        # 重新选择或直接开始。
        self.btn_fishing_cancel = pygame.Rect(panel.left + 40, panel.bottom - 74, 160, 54)
        self.btn_fishing_confirm = pygame.Rect(panel.right - 200, panel.bottom - 74, 160, 54)
        for rect, main, light, text in (
            (self.btn_fishing_cancel, (109, 155, 80), (181, 220, 151), '重新选择'),
            (self.btn_fishing_confirm, (53, 121, 159), (105, 181, 219), '开始挑战'),
        ):
            hovering = rect.collidepoint(pygame.mouse.get_pos())
            draw_rect = rect.move(0, -2 if hovering else 0)
            pygame.draw.rect(self.screen, (67, 43, 27), draw_rect.move(0, 6), border_radius=14)
            pygame.draw.rect(self.screen, main, draw_rect, border_radius=14)
            pygame.draw.rect(self.screen, light, draw_rect.inflate(-8, -8), border_radius=10)
            self.draw_text(text, self.font_normal, (51, 67, 43) if main[1] > 140 else (27, 65, 92),
                           draw_rect.centerx, draw_rect.centery, center=True)

    def draw_menu(self):
        """渲染一个独立、可直接进入游戏的开始界面。"""
        # 天空与远景
        self.screen.fill(SKY)
        pygame.draw.rect(self.screen, SKY_LIGHT, (0, 0, WIDTH, 105))
        self.draw_pixel_cloud(58, 94)
        self.draw_pixel_cloud(435, 122)
        pygame.draw.ellipse(self.screen, HILL, (-90, 214, 340, 190))
        pygame.draw.ellipse(self.screen, (67, 133, 62), (265, 212, 410, 210))
        pygame.draw.rect(self.screen, GRASS, (0, 326, WIDTH, 178))
        self.draw_tree(21, 243, 1)
        self.draw_tree(497, 231, 1)
        self.draw_tree(420, 281, 0.55)

        # 地面像素纹理
        for x, y in [(34, 366), (90, 451), (145, 405), (223, 356), (370, 430), (455, 373), (553, 448), (294, 471)]:
            pygame.draw.rect(self.screen, (78, 153, 62), (x, y, 8, 5))
        for x, y, petal, center in [
            (132, 449, (245, 111, 172), (255, 218, 88)),
            (182, 467, (157, 107, 205), (255, 220, 88)),
            (514, 462, (255, 247, 218), (255, 217, 87)),
        ]:
            self.draw_pixel_flower(x, y, petal, center)

        # 河岸与水面
        pygame.draw.rect(self.screen, WOOD_DARK, (0, 500, WIDTH, 14))
        pygame.draw.rect(self.screen, WOOD, (0, 492, WIDTH, 10))
        for x in range(18, WIDTH, 75):
            pygame.draw.rect(self.screen, (194, 174, 138), (x, 493, 27, 8))
        pygame.draw.rect(self.screen, WATER, (0, 514, WIDTH, HEIGHT - 514))
        for y in (548, 600, 655, 715):
            for x in range((y * 3) % 47 - 20, WIDTH, 78):
                pygame.draw.rect(self.screen, WATER_DARK, (x, y, 38, 4))
        for x, y in [(71, 577), (202, 543), (453, 581), (527, 642), (118, 692)]:
            pygame.draw.rect(self.screen, (145, 210, 235), (x, y, 12, 4))

        # 顶部身份卡片
        progress = pygame.Rect(24, 22, 222, 66)
        self.draw_panel(progress)
        self.draw_text("汪汪救箭队", self.font_menu_title, BROWN, progress.centerx, progress.centery, center=True)

        stage = pygame.Rect(390, 22, 186, 66)
        self.draw_panel(stage)
        self.draw_text("今日进度", self.font_small, BROWN, stage.left + 18, stage.top + 13)
        for i in range(3):
            color = GOLD if i < 2 else (214, 193, 146)
            pygame.draw.polygon(self.screen, color, [(stage.left + 24 + i * 36, stage.top + 44),
                                                      (stage.left + 29 + i * 36, stage.top + 36),
                                                      (stage.left + 34 + i * 36, stage.top + 44),
                                                      (stage.left + 29 + i * 36, stage.top + 51)])
        self.draw_text("2 / 3", self.font_small, BROWN, stage.right - 53, stage.top + 35)
        self.draw_reference_corgi(WIDTH // 2, 487)

        # 木牌文案
        sign = pygame.Rect(384, 386, 160, 68)
        pygame.draw.rect(self.screen, WOOD_DARK, sign.move(0, 4))
        pygame.draw.rect(self.screen, WOOD, sign)
        pygame.draw.rect(self.screen, (211, 151, 75), sign.inflate(-8, -8))
        pygame.draw.rect(self.screen, WOOD_DARK, (sign.centerx - 4, sign.bottom, 8, 38))
        self.draw_text("点击箭头", self.font_small, BROWN, sign.centerx, sign.top + 13, center=True)
        self.draw_text("冲出重围", self.font_small, BROWN, sign.centerx, sign.top + 37, center=True)

        self.draw_menu_fishing_choices()

    def draw_playing_background(self):
        """关卡页延续菜单的草地与河岸，给棋盘留出干净的视觉舞台。"""
        self.screen.fill(SKY)
        pygame.draw.rect(self.screen, SKY_LIGHT, (0, 0, WIDTH, 104))
        self.draw_pixel_cloud(54, 103)
        self.draw_pixel_cloud(432, 110)
        pygame.draw.ellipse(self.screen, HILL, (-100, 116, 350, 176))
        pygame.draw.ellipse(self.screen, (67, 133, 62), (275, 118, 380, 178))
        pygame.draw.rect(self.screen, GRASS, (0, 216, WIDTH, 420))
        self.draw_tree(18, 184, 0.65)
        self.draw_tree(530, 183, 0.57)

        # 草地上的离散像素纹理，避免大面积纯色。
        for x, y, w in [(32, 301, 8), (93, 573, 6), (174, 250, 7), (390, 592, 8),
                        (457, 276, 6), (554, 472, 8), (254, 611, 6), (122, 430, 8)]:
            pygame.draw.rect(self.screen, (76, 151, 61), (x, y, w, 5))

        # 底部河岸，呼应开始页但不会干扰棋盘操作区。
        pygame.draw.rect(self.screen, WOOD_DARK, (0, 630, WIDTH, 14))
        pygame.draw.rect(self.screen, WOOD, (0, 622, WIDTH, 10))
        for x in range(18, WIDTH, 75):
            pygame.draw.rect(self.screen, (194, 174, 138), (x, 623, 27, 8))
        pygame.draw.rect(self.screen, WATER, (0, 644, WIDTH, HEIGHT - 644))
        for x in range(24, WIDTH, 78):
            pygame.draw.rect(self.screen, WATER_DARK, (x, 685, 39, 4))
            pygame.draw.rect(self.screen, WATER_DARK, (x - 28, 727, 34, 4))

    def draw_restart_button(self):
        """时间进度条，中间骨头图标随时间移动，点击可重置当前关卡。"""
        rect = self.btn_restart
        # 计算时间进度
        time_limit = self.get_time_limit()
        elapsed = (pygame.time.get_ticks() - self.level_start_time) / 1000
        progress = min(1.0, elapsed / time_limit)
        remaining = time_limit - elapsed

        # 进度条位置
        bar_x = rect.left + 8
        bar_y = rect.centery
        bar_w = rect.width - 16
        bar_h = 10
        # 进度条背景
        pygame.draw.rect(self.screen, (200, 180, 150), (bar_x, bar_y, bar_w, bar_h), border_radius=5)

        # 进度填充（时间越少越红）
        fill_w = int(bar_w * (1 - progress))
        if remaining < 10:
            fill_color = RED
        elif remaining < 20:
            fill_color = (245, 158, 11)
        else:
            fill_color = (98, 177, 71)
        pygame.draw.rect(self.screen, fill_color, (bar_x, bar_y, fill_w, bar_h), border_radius=5)

        # 骨头图标位置（随时间从右向左移动，剩余越多越靠右）
        bone_x = bar_x + int(bar_w * (1 - progress))
        bone_y = bar_y + bar_h // 2
        bone_rect = self.bone_sprite.get_rect(center=(bone_x, bone_y))
        self.screen.blit(self.bone_sprite, bone_rect)

        # 时间文字（位置适当下调）
        self.draw_text(f"{int(remaining):02d}s", self.font_small, BROWN,
                       rect.centerx, rect.top + 25, center=True)

    def draw_playing_hud(self, active_count):
        """在顶部显示关卡、剩余箭头和失误次数。"""
        level_card = pygame.Rect(24, 13, 196, 88)
        lives_card = pygame.Rect(240, 13, 202, 88)
        self.draw_panel(level_card)
        self.draw_panel(lives_card)
        if self.game_mode == 'endless':
            self.draw_text(f"无尽 {self.level_index + 1}", self.font_normal, BROWN,
                           level_card.left + 18, level_card.top + 13)
        elif self.game_mode == 'fog':
            self.draw_text(f"迷雾 {self.level_index + 1}", self.font_normal, BROWN,
                           level_card.left + 18, level_card.top + 13)
        else:
            self.draw_text(f"第 {self.level_index + 1} 关", self.font_normal, BROWN,
                           level_card.left + 18, level_card.top + 13)
        self.draw_text(f"剩余 {active_count} 支箭", self.font_small, (137, 91, 48),
                       level_card.left + 19, level_card.top + 53)
        self.draw_text("失误机会", self.font_small, BROWN, lives_card.left + 18, lives_card.top + 14)
        # 用爱心图标显示剩余失误次数。
        for i in range(self.max_mistakes):
            x = lives_card.left + 20 + i * 31
            y = lives_card.top + 48
            heart_img = self.heart_sprite if i < self.mistakes else self.heart_gray
            self.screen.blit(heart_img, (x, y))
        self.draw_restart_button()

    def draw_reference_star(self, cx, cy, angle, mirror=False):
        """使用参考图色调校正后的等臂幸运星精灵，并持续旋转。"""
        star = pygame.transform.flip(self.luck_star_sprite, True, False) if mirror else self.luck_star_sprite
        # rotozoom 使用滤波旋转，半透明边缘不会出现硬朗的像素方块。
        rotated = pygame.transform.rotozoom(star, angle, 1.0)
        self.screen.blit(rotated, rotated.get_rect(center=(cx, cy)))

    def draw_dashed_rect(self, rect, color, width=2, dash=16, gap=10):
        """绘制等粗虚线框，供棋盘外圈使用。"""
        def dashed_line(start, end):
            sx, sy = start
            ex, ey = end
            length = int(math.hypot(ex - sx, ey - sy))
            if length == 0:
                return
            ux, uy = (ex - sx) / length, (ey - sy) / length
            cursor = 0
            while cursor < length:
                finish = min(cursor + dash, length)
                pygame.draw.line(self.screen, color,
                                 (round(sx + ux * cursor), round(sy + uy * cursor)),
                                 (round(sx + ux * finish), round(sy + uy * finish)), width)
                cursor += dash + gap

        dashed_line((rect.left, rect.top), (rect.right - 1, rect.top))
        dashed_line((rect.right - 1, rect.top), (rect.right - 1, rect.bottom - 1))
        dashed_line((rect.right - 1, rect.bottom - 1), (rect.left, rect.bottom - 1))
        dashed_line((rect.left, rect.bottom - 1), (rect.left, rect.top))

    def draw_pixel_board(self):
        """参考幸运面板的厚木框棋盘；格子与箭头共用深棕描边。"""
        cs = self.cell_size
        board_w = self.grid_cols * cs
        board_h = self.grid_rows * cs
        outer = pygame.Rect(self.board_offset_x - 22, self.board_offset_y - 22,
                            board_w + 44, board_h + 44)
        # 与参考弹窗一致的三层关系：外侧深棕投影 → 褐色主边框 → 内侧浅色。
        pygame.draw.rect(self.screen, WOOD_DARK, outer.move(0, 7), border_radius=18)
        pygame.draw.rect(self.screen, BROWN, outer, border_radius=18)
        cream_panel = outer.inflate(-14, -14)
        pygame.draw.rect(self.screen, CREAM, cream_panel, border_radius=9)

        grid_rect = pygame.Rect(self.board_offset_x, self.board_offset_y, board_w, board_h)
        for r in range(self.grid_rows):
            for c in range(self.grid_cols):
                cell = pygame.Rect(self.board_offset_x + c * cs,
                                   self.board_offset_y + r * cs,
                                   cs, cs)
                pygame.draw.rect(self.screen, (255, 239, 191), cell)
                # 单个角落高光使格子读为木盘上的卡槽。
                pygame.draw.rect(self.screen, (255, 250, 216), (cell.left + 4, cell.top + 4, 14, 3))

        # 内部分格保留等粗实线；最外圈改为虚线。
        grid_line = (205, 166, 105)
        for col in range(1, self.grid_cols):
            x = self.board_offset_x + col * cs
            pygame.draw.line(self.screen, grid_line, (x, grid_rect.top), (x, grid_rect.bottom), 2)
        for row in range(1, self.grid_rows):
            y = self.board_offset_y + row * cs
            pygame.draw.line(self.screen, grid_line, (grid_rect.left, y), (grid_rect.right, y), 2)
        self.draw_dashed_rect(grid_rect, grid_line, width=2)

        # 参考面板两侧角标：每帧读取时间，所以它们会持续旋转。
        spin = (pygame.time.get_ticks() * 0.16) % 360
        self.draw_reference_star(outer.left + 4, outer.top + 3, spin)
        self.draw_reference_star(outer.right - 4, outer.top + 3, -spin, mirror=True)

    def draw_playing_footer(self):
        # 动态定位在棋盘外框正下方，避免大关卡重叠
        board_bottom = self.board_offset_y + self.grid_rows * self.cell_size + 22
        footer_y = board_bottom + 10
        footer = pygame.Rect((WIDTH - 322) // 2, footer_y, 322, 39)
        self.draw_panel(footer)
        self.draw_text("点击没有阻挡的箭头，让它逃出去", self.font_small, BROWN,
                       footer.centerx, footer.centery, center=True)

    def draw_completion_button(self, label):
        """通关页的蓝色主行动按钮，不再使用木框。"""
        rect = self.btn_center
        hovering = rect.collidepoint(pygame.mouse.get_pos())
        draw_rect = rect.move(0, -2 if hovering else 0)
        pygame.draw.rect(self.screen, (31, 83, 122), draw_rect.move(0, 6), border_radius=16)
        pygame.draw.rect(self.screen, (60, 151, 204), draw_rect, border_radius=16)
        pygame.draw.rect(self.screen, (111, 190, 224) if hovering else (91, 174, 216),
                         draw_rect.inflate(-8, -8), border_radius=12)
        self.draw_text(label, self.font_normal, (29, 63, 91), draw_rect.centerx, draw_rect.centery, center=True)

    def draw_completion_screen(self, title, action_label, t, show_total=False):
        """通关奖励页：沿用原有棋盘舞台与庆祝动画，不再覆盖木框弹窗。"""
        self.draw_playing_background()
        self.draw_pixel_board()
        # 保留原有的舞台感，但降低遮罩和放射光的侵入性。
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((42, 54, 48, 112))
        self.screen.blit(veil, (0, 0))
        # 放大光束图层，使旋转光带持续延伸到界面底部的水面区域。
        rotated = pygame.transform.rotozoom(self.radial_img, t * 7, 1.25)
        rotated.set_alpha(42)
        self.screen.blit(rotated, rotated.get_rect(center=(WIDTH // 2, 320)))
        glow = self.glow_img.copy()
        glow.set_alpha(108)
        self.screen.blit(glow, glow.get_rect(center=(WIDTH // 2, 315)))
        self.update_draw_clear_particles(t)

        # 标题、皇冠柯基、评级和统计沿纵轴排列，避免遮挡棋盘与互相拥挤。
        title_font = self.font_pass if title == "PASS" else self.font_title
        pass_color = (78, 228, 113)
        # 轻微深绿投影加强饱和绿色在浅光束上的可读性。
        self.draw_text(title, title_font, (28, 111, 61), WIDTH // 2 + 3, 146 + 4, center=True)
        self.draw_text(title, title_font, pass_color, WIDTH // 2, 146, center=True)
        dog = pygame.transform.smoothscale(self.pass_dog, (112, 166))
        float_y = math.sin(t * 3.5) * 3 if t > 0.55 else 0
        self.screen.blit(dog, dog.get_rect(midbottom=(WIDTH // 2, 374 + float_y)))

        lit_count = min(self.current_stars, max(0, int((t - 0.25) / 0.22) + 1))
        for i in range(3):
            star = self.clear_rating_star.copy()
            if i >= lit_count:
                star = pygame.transform.grayscale(star)
                star.set_alpha(75)
            scale = 1.0
            pop_t = t - 0.25 - i * 0.22
            if i < lit_count and 0 <= pop_t < 0.18:
                scale = 1.24 - pop_t * 1.3
            star = pygame.transform.rotozoom(star, 0, scale)
            star_y = 430 - (18 if i == 1 else 0)
            self.screen.blit(star, star.get_rect(center=(WIDTH // 2 + (i - 1) * 58, star_y)))

        used = self.total_mistakes if show_total else self.max_mistakes - self.mistakes
        elapsed = self.total_clear_time if show_total else self.clear_time
        prefix = "总用时" if show_total else "用时"
        mistake_label = "总失误" if show_total else "失误"
        self.draw_text(f"{prefix} {elapsed:.1f} 秒   ·   {mistake_label} {used} 次",
                       self.font_small, (245, 239, 209), WIDTH // 2, 485, center=True)

        self.btn_center.update(WIDTH // 2 - 130, 548, 260, 58)
        self.draw_completion_button(action_label)

    def draw_failure_button(self, label):
        """失败页的冷蓝行动按钮，与通关页按钮保持相同层级。"""
        rect = self.btn_center
        hovering = rect.collidepoint(pygame.mouse.get_pos())
        draw_rect = rect.move(0, -2 if hovering else 0)
        pygame.draw.rect(self.screen, (31, 64, 101), draw_rect.move(0, 6), border_radius=16)
        pygame.draw.rect(self.screen, (75, 137, 198), draw_rect, border_radius=16)
        pygame.draw.rect(self.screen, (135, 190, 237) if hovering else (111, 171, 222),
                         draw_rect.inflate(-8, -8), border_radius=12)
        self.draw_text(label, self.font_normal, (30, 61, 92), draw_rect.centerx, draw_rect.centery, center=True)

    def draw_game_over_screen(self):
        """冷蓝色失败页：复用通关构图，不使用木框弹窗。"""
        self.draw_playing_background()
        self.draw_pixel_board()
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((30, 68, 103, 138))
        self.screen.blit(veil, (0, 0))

        # 从角色两侧缓慢下落的泪滴，避免失败页显得静止且生硬。
        phase = pygame.time.get_ticks() / 700
        for index, x in enumerate((184, 212, 390, 418)):
            y = 210 + ((phase * 24 + index * 42) % 230)
            pygame.draw.circle(self.screen, (113, 181, 239), (x, int(y)), 5)
            pygame.draw.polygon(self.screen, (113, 181, 239), [(x, int(y - 10)), (x - 5, int(y - 2)), (x + 5, int(y - 2))])

        reason_title = {
            'mistakes': 'OOPS',
            'timeout': 'TIME UP',
            'deadlock': 'STUCK',
        }.get(self.game_over_reason, 'OOPS')
        title_font = self.font_pass if reason_title == 'OOPS' else self.font_title
        self.draw_text(reason_title, title_font, (25, 75, 118), WIDTH // 2 + 3, 148 + 4, center=True)
        self.draw_text(reason_title, title_font, (123, 190, 238), WIDTH // 2, 148, center=True)
        self.screen.blit(self.crying_dog, self.crying_dog.get_rect(midbottom=(WIDTH // 2, 397)))

        # 只保留一句可行动的短提示，避免与失败情绪争夺焦点。
        self.draw_text('再试一次吧', self.font_normal, (223, 240, 252), WIDTH // 2, 448, center=True)
        remaining = sum(1 for arrow in self.arrows if arrow.state != 'dead')
        self.draw_text(f'还剩 {remaining} 支箭', self.font_small, (192, 222, 245), WIDTH // 2, 485, center=True)

        self.btn_center.update(WIDTH // 2 - 130, 548, 260, 58)
        self.draw_failure_button('再 试 一 次')
    def run(self):
        """游戏主循环"""
        while True:
            self.screen.fill(BG_COLOR)
            mx, my = pygame.mouse.get_pos()
            
            # --- 事件处理 ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    os.killpg(os.getpgid(self.bgm_process.pid), 15)
                    pygame.quit()
                    sys.exit()
                    
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.state == 'MENU':
                        if self.menu_cast_mode is None:
                            for mode in self.fishing_mode_targets:
                                target = self.get_menu_fishing_target_rect(mode)
                                if target.collidepoint(mx, my):
                                    self.menu_cast_mode = mode
                                    self.menu_cast_start = pygame.time.get_ticks()
                                    self.menu_cast_target = target.center
                                    self.play_sfx('cast')
                                    break

                    elif self.state == 'FISHING_RESULT':
                        if self.btn_fishing_close.collidepoint(mx, my) or self.btn_fishing_cancel.collidepoint(mx, my):
                            self.state = 'MENU'
                            self.menu_cast_mode = None
                            self.menu_cast_target = None
                            self.fishing_result_mode = None
                        elif self.btn_fishing_confirm.collidepoint(mx, my):
                            self.start_game_mode(self.fishing_result_mode)
                    
                    elif self.state == 'PLAYING':
                        self.handle_click(mx, my)
                        
                    elif self.state == 'LEVEL_CLEAR':
                        if self.btn_center.collidepoint(mx, my):
                            self.level_index += 1
                            # 基础为 3 关，迷雾为 10 关；只有无尽模式持续生成新关卡。
                            mode_limit = FOG_LEVEL_COUNT if self.game_mode == 'fog' else len(LEVELS)
                            if self.game_mode in ('basic', 'fog') and self.level_index >= mode_limit:
                                self.state = 'VICTORY'
                            else:
                                self.load_level()
                                self.state = 'PLAYING'

                    elif self.state == 'GAME_OVER':
                        if self.btn_center.collidepoint(mx, my):
                            self.load_level()
                            self.state = 'PLAYING'

                    elif self.state == 'VICTORY':
                        if self.btn_center.collidepoint(mx, my):
                            self.state = 'MENU'
            # 菜单钓中目标后，先完整收线，再弹出对应模式的规则说明。
            if (self.state == 'MENU' and self.menu_cast_mode is not None
                    and pygame.time.get_ticks() - self.menu_cast_start >= 1850):
                self.fishing_result_mode = self.menu_cast_mode
                self.fishing_result_start = pygame.time.get_ticks()
                self.state = 'FISHING_RESULT'
            # --- 状态逻辑与渲染 ---
            if self.state == 'MENU':
                self.draw_menu()

            elif self.state == 'FISHING_RESULT':
                self.draw_menu()
                self.draw_fishing_result()
                
            elif self.state == 'PLAYING':
                self.draw_playing_background()
                # 更新箭头
                for arrow in self.arrows:
                    if arrow.update():
                        self.spawn_arrow_effect(arrow.x, arrow.y, ARROW_COLORS[arrow.direction], 'exit',
                                                arrow.dirx, arrow.diry)
                # 迷雾模式：每帧重算可见性（箭头飞走后相邻箭头点亮）
                self.recompute_fog()
                    
                # 统计存活的箭头数量
                active_arrows = [a for a in self.arrows if a.state in ['idle', 'shaking', 'windup']]
                remain_count = sum(1 for a in self.arrows if a.state != 'dead')
                
                # 胜负判定
                if len(active_arrows) == 0 and remain_count == 0: # 等待飞出动画结束
                    # 根据耗时与失误次数评定 1~3 星
                    self.clear_time = (pygame.time.get_ticks() - self.level_start_time) / 1000
                    used_mistakes = self.max_mistakes - self.mistakes
                    time_limit = self.get_time_limit()
                    # 时间定基础档：耗时占比 <50% 三星、50%~75% 二星、>=75% 一星
                    ratio = self.clear_time / time_limit
                    if ratio < 0.5:
                        base_stars = 3
                    elif ratio < 0.75:
                        base_stars = 2
                    else:
                        base_stars = 1
                    # 每累计 2 次失误降 1 档，最低保留 1 星
                    self.current_stars = max(1, base_stars - used_mistakes // 2)
                    self.clear_anim_start = pygame.time.get_ticks()
                    if self.game_mode in ('basic', 'fog'):
                        self.total_clear_time += self.clear_time
                        self.total_mistakes += used_mistakes
                    self.setup_clear_particles()
                    self.play_sfx('win')
                    self.state = 'LEVEL_CLEAR'
                elif self.mistakes <= 0:
                    self.game_over_reason = 'mistakes'
                    self.state = 'GAME_OVER'
                elif (pygame.time.get_ticks() - self.level_start_time) / 1000 >= self.get_time_limit():
                    self.game_over_reason = 'timeout'
                    self.state = 'GAME_OVER'
                else:
                    # 死锁检测：存活箭头非空、无箭头在飞、且全部被阻挡 → 无解
                    flying_arrows = [a for a in self.arrows if a.state == 'flying']
                    if active_arrows and not flying_arrows and all(self.is_path_blocked(a) for a in active_arrows):
                        self.game_over_reason = 'deadlock'
                        self.state = 'GAME_OVER'
                # 渲染与开始页一致的木框 HUD、棋盘和说明卡。
                self.draw_playing_hud(len(active_arrows))
                self.draw_pixel_board()
                self.update_draw_arrow_effects()
                # 渲染所有未清除的箭头；迷雾模式未点亮处显示问号图标
                for idx, arrow in enumerate(self.arrows):
                    if arrow.state != 'dead' and not arrow.is_visible:
                        fr = self.fog_sprite.get_rect(center=(arrow.x, arrow.y))
                        self.screen.blit(self.fog_sprite, fr)
                    else:
                        arrow.draw(self.screen)
                # AI提示高亮（闪烁金色圆环）
                if self.hint_timer > 0 and 0 <= self.hint_arrow_idx < len(self.arrows):
                    ha = self.arrows[self.hint_arrow_idx]
                    if ha.state == 'idle':
                        if self.hint_timer % 20 < 12:
                            pygame.draw.circle(self.screen, (255, 210, 60),
                                               (ha.x, ha.y), self.cell_size // 2 - 4, 4)
                        self.hint_timer -= 1
                    else:
                        self.hint_timer = 0
                # AI提示宝箱
                self.draw_hint_chest()
                # 返回菜单柯基
                self.draw_menu_corgi_button()
                self.draw_playing_footer()
                    
            elif self.state == 'LEVEL_CLEAR':
                t = (pygame.time.get_ticks() - self.clear_anim_start) / 1000
                self.draw_completion_screen("PASS", "继 续 冒 险", t)
            elif self.state == 'GAME_OVER':
                self.draw_game_over_screen()
                
            elif self.state == 'VICTORY':
                t = (pygame.time.get_ticks() - self.clear_anim_start) / 1000
                self.draw_completion_screen("ALL CLEAR", "返 回 主 菜 单", t, show_total=True)
            self.draw_custom_cursor()
            pygame.display.flip()
            self.clock.tick(FPS)
if __name__ == "__main__":
    game = Game()
    game.run()
