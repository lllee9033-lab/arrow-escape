import pygame
import sys
import math
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
        pygame.draw.polygon(surface, (255, 255, 255), rot_points, 2) # 白色描边
# ================= 游戏主类 =================
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("一箭又一箭 - AIGC开发实践")
        self.clock = pygame.time.Clock()
        
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
        self.board_offset_y = 180
        
        # 按钮区域定义
        self.btn_restart = pygame.Rect(440, 30, 130, 40)
        self.btn_center = pygame.Rect(WIDTH//2 - 100, 500, 200, 50)
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
        self.board_offset_x = (WIDTH - board_w) // 2
        
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
    def run(self):
        """游戏主循环"""
        while True:
            self.screen.fill(BG_COLOR)
            mx, my = pygame.mouse.get_pos()
            
            # --- 事件处理 ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
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
                self.draw_text("一 箭 又 一 箭", self.font_title, TEXT_COLOR, WIDTH//2, 250, center=True)
                self.draw_button(self.btn_center, "开始游戏")
                
            elif self.state == 'PLAYING':
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
                # 渲染 HUD 信息
                self.draw_text(f"第 {self.level_index + 1} 关", self.font_normal, TEXT_COLOR, 30, 25)
                self.draw_text(f"剩余箭头: {len(active_arrows)}", self.font_small, TEXT_COLOR, 30, 65)
                
                mistake_color = RED if self.mistakes <= 2 else TEXT_COLOR
                self.draw_text(f"剩余失误: {self.mistakes} / {self.max_mistakes}", self.font_small, mistake_color, 30, 95)
                
                # 重新开始按钮
                self.draw_button(self.btn_restart, "重新开始")
                
                # 渲染棋盘网格底图
                for r in range(self.grid_rows):
                    for c in range(self.grid_cols):
                        cx = self.board_offset_x + c * CELL_SIZE
                        cy = self.board_offset_y + r * CELL_SIZE
                        pygame.draw.rect(self.screen, GRID_COLOR, (cx, cy, CELL_SIZE, CELL_SIZE), 1)
                # 渲染所有未清除的箭头
                for arrow in self.arrows:
                    arrow.draw(self.screen)
                    
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
