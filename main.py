import pygame
import sys
import math
import subprocess
import os
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
# ================= 实体类 =================
class Arrow:
    def __init__(self, row, col, direction, offset_x, offset_y):
        self.row = row
        self.col = col
        self.direction = direction
        self.state = 'idle'  # 状态：idle(静止), shaking(碰撞晃动), flying(飞出), dead(已清除)
        
        # 屏幕中心像素坐标
        self.x = offset_x + col * CELL_SIZE + CELL_SIZE // 2
        self.y = offset_y + row * CELL_SIZE + CELL_SIZE // 2
        
        self.shake_timer = 0
        self.vx = 0
        self.vy = 0
        self.speed = 18  # 飞出速度
    def update(self):
        """更新箭头状态（动画逻辑）"""
        if self.state == 'shaking':
            self.shake_timer -= 1
            if self.shake_timer <= 0:
                self.state = 'idle'
        elif self.state == 'flying':
            self.x += self.vx
            self.y += self.vy
            # 飞出屏幕边缘后标记为死亡
            if self.x < -100 or self.x > WIDTH + 100 or self.y < -100 or self.y > HEIGHT + 100:
                self.state = 'dead'
    def draw(self, surface):
        """渲染箭头多边形"""
        if self.state == 'dead':
            return
            
        dx, dy = 0, 0
        if self.state == 'shaking':
            # 利用正弦函数实现左右/上下晃动
            offset = math.sin(self.shake_timer * 1.5) * 6
            if self.direction in ['L', 'R']:
                dx = offset
            else:
                dy = offset
        # 基础箭头形状（指向上方）
        points = [(0, -22), (-16, 2), (-6, 2), (-6, 22), (6, 22), (6, 2), (16, 2)]
        
        # 根据方向旋转
        angle = {'U': 0, 'L': -90, 'D': 180, 'R': 90}[self.direction]
        color = ARROW_COLORS[self.direction]
        
        rad = math.radians(angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        
        rot_points = []
        for px, py in points:
            # 矩阵旋转公式
            nx = px * cos_a - py * sin_a
            ny = px * sin_a + py * cos_a
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
        self.clock = pygame.time.Clock()
        # 背景音乐：夏日曼哈顿咖啡店 Jazz（用 macOS 原生 afplay 循环播放）
        bgm_path = str(Path(__file__).parent / "assets" / "bgm.m4a")
        self.bgm_process = subprocess.Popen(
            f'while true; do afplay "{bgm_path}"; done',
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        # 来自用户提供参考图的柯基精灵。路径相对本脚本，避免受启动目录影响。
        sprite_path = Path(__file__).parent / "assets" / "corgi-reference-sprite.png"
        self.corgi_sprite = pygame.image.load(str(sprite_path)).convert_alpha()
        # 按原始比例做最近邻缩放，完整保留脚掌下方的深棕色像素描边。
        self.corgi_sprite = pygame.transform.scale(self.corgi_sprite, (140, 216))
        star_path = Path(__file__).parent / "assets" / "luck-star-reference.png"
        self.luck_star_sprite = pygame.image.load(str(star_path)).convert_alpha()
        # 缩小为参考图相对面板的比例；柔化蒙版会保留边沿半透明感。
        self.luck_star_sprite = pygame.transform.smoothscale(self.luck_star_sprite, (28, 28))
        
        # 兼容系统的中文字体加载
        self.font_title = self.get_chinese_font(50)
        self.font_normal = self.get_chinese_font(28)
        self.font_small = self.get_chinese_font(20)
        
        # 游戏全局变量
        self.state = 'MENU'  # MENU, PLAYING, LEVEL_CLEAR, GAME_OVER, VICTORY
        self.level_index = 0
        self.max_mistakes = 5
        self.mistakes = self.max_mistakes
        self.game_over_reason = None  # 'mistakes' | 'deadlock' | None
        
        self.arrows = []
        self.grid_rows = 0
        self.grid_cols = 0
        self.board_offset_x = 0
        self.board_offset_y = 150
        
        # 按钮区域定义
        self.btn_restart = pygame.Rect(462, 13, 114, 88)
        self.btn_center = pygame.Rect(WIDTH//2 - 130, 628, 260, 58)
    def get_chinese_font(self, size):
        """寻找系统内置的中文字体以防乱码"""
        fonts = ['pingfangsc', 'pingfang', 'heiti', 'stheitisc', 'kaiti', 'microsoftyahei', 'simhei', 'simsun']
        for f in fonts:
            path = pygame.font.match_font(f)
            if path: return pygame.font.Font(path, size)
        return pygame.font.Font(None, size) # 回退到默认
    def load_level(self):
        """加载当前关卡"""
        self.arrows.clear()
        self.mistakes = self.max_mistakes
        self.game_over_reason = None
        grid = LEVELS[self.level_index]
        self.grid_rows = len(grid)
        self.grid_cols = len(grid[0])
        
        # 居中计算
        board_w = self.grid_cols * CELL_SIZE
        board_h = self.grid_rows * CELL_SIZE
        self.board_offset_x = (WIDTH - board_w) // 2
        # 草坪区域 y=216~636，考虑底部河岸与水面视觉重量，取视觉中心略偏上
        grass_center_y = 380
        # 外框中心 = board_offset_y - 22 + (board_h + 44)/2 = board_offset_y + board_h/2
        self.board_offset_y = grass_center_y - board_h // 2
        
        for r in range(self.grid_rows):
            for c in range(self.grid_cols):
                val = grid[r][c]
                if val in ['U', 'D', 'L', 'R']:
                    self.arrows.append(Arrow(r, c, val, self.board_offset_x, self.board_offset_y))
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
        # 1. 点击重新开始按钮
        if self.btn_restart.collidepoint(mx, my):
            self.load_level()
            return
            
        # 2. 点击箭头
        for arrow in self.arrows:
            if arrow.state == 'idle':
                # 勾股定理判断点击是否在箭头中心圆角范围内
                dist = math.hypot(mx - arrow.x, my - arrow.y)
                if dist < CELL_SIZE // 2:
                    if self.is_path_blocked(arrow):
                        # 阻挡：执行晃动动画并扣除生命
                        arrow.state = 'shaking'
                        arrow.shake_timer = 20
                        self.mistakes -= 1
                    else:
                        # 通畅：执行飞出动画
                        arrow.state = 'flying'
                        if arrow.direction == 'U': arrow.vy = -arrow.speed
                        elif arrow.direction == 'D': arrow.vy = arrow.speed
                        elif arrow.direction == 'L': arrow.vx = -arrow.speed
                        elif arrow.direction == 'R': arrow.vx = arrow.speed
                    break # 每次点击只触发一个
    def draw_text(self, text, font, color, x, y, center=False):
        """辅助渲染文字"""
        surf = font.render(text, True, color)
        rect = surf.get_rect()
        if center:
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        self.screen.blit(surf, rect)
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
        """将用户提供图片中提取的透明柯基精灵置于草地上。"""
        rect = self.corgi_sprite.get_rect(midbottom=(cx, bottom_y))
        # 阴影收在草地范围内，避免与河岸的深色边线叠在一起而吃掉脚掌轮廓。
        pygame.draw.ellipse(self.screen, (49, 116, 66), (cx - 55, bottom_y - 10, 110, 10))
        self.screen.blit(self.corgi_sprite, rect)

    def draw_menu_button(self):
        """主按钮延续菜单卡片的材质，而非通用蓝色按钮。"""
        rect = self.btn_center
        hovering = rect.collidepoint(pygame.mouse.get_pos())
        offset_y = -2 if hovering else 0
        draw_rect = rect.move(0, offset_y)
        pygame.draw.rect(self.screen, WOOD_DARK, draw_rect.move(0, 6), border_radius=18)
        pygame.draw.rect(self.screen, BROWN, draw_rect, border_radius=18)
        pygame.draw.rect(self.screen, GOLD_LIGHT if hovering else CREAM, draw_rect.inflate(-10, -10), border_radius=13)
        self.draw_text("开 始 冒 险", self.font_normal, BROWN, draw_rect.centerx, draw_rect.centery - 1, center=True)
        # 一个小箭头图标，让按钮的意图在无文字时也成立。
        tip_x, tip_y = draw_rect.right - 34, draw_rect.centery
        pygame.draw.polygon(self.screen, (205, 91, 43), [(tip_x + 10, tip_y), (tip_x - 5, tip_y - 10), (tip_x - 5, tip_y + 10)])

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
        for x, y, color in [(78, 478, (255, 217, 77)), (493, 468, (245, 112, 117)), (529, 414, (225, 233, 119))]:
            pygame.draw.rect(self.screen, color, (x, y, 5, 14))
            pygame.draw.rect(self.screen, color, (x - 5, y + 4, 15, 5))

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
        self.draw_text("箭 阵 逃 脱", self.font_normal, BROWN, progress.left + 20, progress.top + 18)

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

        # 居中的参考图柯基素材
        self.draw_reference_corgi(WIDTH // 2, 487)

        # 木牌文案
        sign = pygame.Rect(384, 386, 160, 68)
        pygame.draw.rect(self.screen, WOOD_DARK, sign.move(0, 4))
        pygame.draw.rect(self.screen, WOOD, sign)
        pygame.draw.rect(self.screen, (211, 151, 75), sign.inflate(-8, -8))
        pygame.draw.rect(self.screen, WOOD_DARK, (sign.centerx - 4, sign.bottom, 8, 38))
        self.draw_text("点击箭头", self.font_small, BROWN, sign.centerx, sign.top + 13, center=True)
        self.draw_text("冲出重围", self.font_small, BROWN, sign.centerx, sign.top + 37, center=True)

        self.draw_text("找出没有阻挡的方向", self.font_small, (238, 247, 229), WIDTH // 2, 577, center=True)
        self.draw_menu_button()

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
        """小型木框重开按钮；按钮区域仍使用 self.btn_restart。"""
        rect = self.btn_restart
        hovering = rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(self.screen, WOOD_DARK, rect.move(0, 4), border_radius=14)
        pygame.draw.rect(self.screen, BROWN, rect, border_radius=14)
        pygame.draw.rect(self.screen, GOLD_LIGHT if hovering else CREAM, rect.inflate(-9, -9), border_radius=10)
        self.draw_text("重  排", self.font_small, BROWN, rect.centerx, rect.centery, center=True)

    def draw_playing_hud(self, active_count):
        """在顶部显示关卡、剩余箭头和失误次数。"""
        level_card = pygame.Rect(24, 13, 196, 88)
        lives_card = pygame.Rect(240, 13, 202, 88)
        self.draw_panel(level_card)
        self.draw_panel(lives_card)
        self.draw_text(f"第 {self.level_index + 1} 关", self.font_normal, BROWN,
                       level_card.left + 18, level_card.top + 13)
        self.draw_text(f"剩余 {active_count} 支箭", self.font_small, (137, 91, 48),
                       level_card.left + 19, level_card.top + 53)
        self.draw_text("失误机会", self.font_small, BROWN, lives_card.left + 18, lives_card.top + 16)
        # 用像素心形而不是纯数字强调错误次数。
        for i in range(self.max_mistakes):
            color = (220, 58, 54) if i < self.mistakes else (207, 185, 141)
            x, y = lives_card.left + 21 + i * 27, lives_card.top + 55
            pygame.draw.rect(self.screen, color, (x, y, 8, 8))
            pygame.draw.rect(self.screen, color, (x + 8, y, 8, 8))
            pygame.draw.rect(self.screen, color, (x + 4, y + 7, 8, 8))
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
        board_w = self.grid_cols * CELL_SIZE
        board_h = self.grid_rows * CELL_SIZE
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
                cell = pygame.Rect(self.board_offset_x + c * CELL_SIZE,
                                   self.board_offset_y + r * CELL_SIZE,
                                   CELL_SIZE, CELL_SIZE)
                pygame.draw.rect(self.screen, (255, 239, 191), cell)
                # 单个角落高光使格子读为木盘上的卡槽。
                pygame.draw.rect(self.screen, (255, 250, 216), (cell.left + 4, cell.top + 4, 14, 3))

        # 内部分格保留等粗实线；最外圈改为参考图式虚线。
        grid_line = (205, 166, 105)
        for col in range(1, self.grid_cols):
            x = self.board_offset_x + col * CELL_SIZE
            pygame.draw.line(self.screen, grid_line, (x, grid_rect.top), (x, grid_rect.bottom), 2)
        for row in range(1, self.grid_rows):
            y = self.board_offset_y + row * CELL_SIZE
            pygame.draw.line(self.screen, grid_line, (grid_rect.left, y), (grid_rect.right, y), 2)
        self.draw_dashed_rect(grid_rect, grid_line, width=2)

        # 参考面板两侧角标：每帧读取时间，所以它们会持续旋转。
        spin = (pygame.time.get_ticks() * 0.16) % 360
        self.draw_reference_star(outer.left + 4, outer.top + 3, spin)
        self.draw_reference_star(outer.right - 4, outer.top + 3, -spin, mirror=True)

    def draw_playing_footer(self):
        # 动态定位在棋盘外框正下方，避免大关卡重叠
        board_bottom = self.board_offset_y + self.grid_rows * CELL_SIZE + 22
        footer_y = board_bottom + 10
        footer = pygame.Rect((WIDTH - 322) // 2, footer_y, 322, 39)
        self.draw_panel(footer)
        self.draw_text("点击没有阻挡的箭头，让它逃出去", self.font_small, BROWN,
                       footer.centerx, footer.centery, center=True)
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
                        if self.btn_center.collidepoint(mx, my):
                            self.level_index = 0
                            self.load_level()
                            self.state = 'PLAYING'
                    
                    elif self.state == 'PLAYING':
                        self.handle_click(mx, my)
                        
                    elif self.state == 'LEVEL_CLEAR':
                        if self.btn_center.collidepoint(mx, my):
                            self.level_index += 1
                            if self.level_index >= len(LEVELS):
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
            # --- 状态逻辑与渲染 ---
            if self.state == 'MENU':
                self.draw_menu()
                
            elif self.state == 'PLAYING':
                self.draw_playing_background()
                # 更新箭头
                for arrow in self.arrows:
                    arrow.update()
                    
                # 统计存活的箭头数量
                active_arrows = [a for a in self.arrows if a.state in ['idle', 'shaking']]
                remain_count = sum(1 for a in self.arrows if a.state != 'dead')
                
                # 胜负判定
                if len(active_arrows) == 0 and remain_count == 0: # 等待飞出动画结束
                    self.state = 'LEVEL_CLEAR'
                elif self.mistakes <= 0:
                    self.game_over_reason = 'mistakes'
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
                # 渲染所有未清除的箭头
                for arrow in self.arrows:
                    arrow.draw(self.screen)
                self.draw_playing_footer()
                    
            elif self.state == 'LEVEL_CLEAR':
                self.draw_text("关卡完成！", self.font_title, (16, 185, 129), WIDTH//2, 250, center=True)
                self.draw_button(self.btn_center, "下一关")
                
            elif self.state == 'GAME_OVER':
                if self.game_over_reason == 'deadlock':
                    self.draw_text("陷入死局，无解", self.font_title, (245, 158, 11), WIDTH//2, 230, center=True)
                    self.draw_text("剩余箭头互相阻挡，无法继续消除", self.font_small, TEXT_COLOR, WIDTH//2, 300, center=True)
                else:
                    self.draw_text("失误次数耗尽", self.font_title, RED, WIDTH//2, 250, center=True)
                self.draw_button(self.btn_center, "再试一次")
                
            elif self.state == 'VICTORY':
                self.draw_text("恭喜通关全部关卡！", self.font_title, (245, 158, 11), WIDTH//2, 250, center=True)
                self.draw_button(self.btn_center, "返回主菜单")
            pygame.display.flip()
            self.clock.tick(FPS)
if __name__ == "__main__":
    game = Game()
    game.run()
