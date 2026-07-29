import io
import math
import os
import random

import pygame


class Confetti:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-5, 5)
        self.vy = random.uniform(-10, -3)
        self.gravity = 0.2
        self.color = (
            random.randint(50, 255),
            random.randint(50, 255),
            random.randint(50, 255),
        )
        self.size = random.randint(4, 10)
        self.life = random.randint(40, 80)
        self.max_life = self.life

    def update(self):
        self.vy += self.gravity
        self.x += self.vx
        self.y += self.vy
        self.life -= 1

    def draw(self, surface):
        if self.life > 0:
            alpha = int(255 * (self.life / self.max_life))
            pygame.draw.rect(
                surface, self.color, (self.x, self.y, self.size, self.size)
            )


class Game:
    WIN_WIDTH = 700
    WIN_HEIGHT = 700
    WIN_THRESHOLD = 20

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((self.WIN_WIDTH, self.WIN_HEIGHT))
        pygame.display.set_caption("Key Game")
        self.clock = pygame.time.Clock()

        base = os.path.dirname(os.path.abspath(__file__))
        self.chest_img = pygame.image.load(os.path.join(base, "chest.jpeg")).convert()
        self.chest_img = pygame.transform.scale(self.chest_img, (200, 150))

        self.key_img = pygame.image.load(os.path.join(base, "key.webp")).convert_alpha()
        self.key_img = pygame.transform.scale(self.key_img, (80, 100))

        self.key_x = float(self.WIN_WIDTH // 2)
        self.key_y = float(self.WIN_HEIGHT // 2)

        self.chest_x = 0
        self.chest_y = 0
        self._randomize_chest()

        self.confetti_particles = []
        self.key_fitted = False
        self.confetti_done = False
        self.show_confetti = False
        self.win_timer = 0

        self.font = pygame.font.SysFont("Arial", 24, bold=True)
        self.big_font = pygame.font.SysFont("Arial", 36, bold=True)

        self.current_phrase = ""
        self.phrase_timer = 0
        self.phrases_dict = {}
        self.audio_playing = False

        self.running = True

    def _randomize_chest(self):
        margin = 100
        self.chest_x = random.randint(margin, self.WIN_WIDTH - 200 - margin)
        self.chest_y = random.randint(margin, self.WIN_HEIGHT - 150 - margin)

    def set_phrases(self, phrases_dict):
        self.phrases_dict = phrases_dict

    def play_phrase(self, phrase, audio_b64):
        self.current_phrase = phrase
        self.phrase_timer = 120
        try:
            from phrases import decode_audio

            audio_data = decode_audio(audio_b64)
            sound = pygame.mixer.Sound(io.BytesIO(audio_data))
            sound.play()
            self.audio_playing = True
        except Exception:
            pass

    def update(self, yaw, pitch, face_detected):
        speed = 600
        dt = self.clock.get_time() / 1000.0

        if face_detected:
            self.key_x += yaw * speed * dt
            self.key_y += pitch * speed * dt

        self.key_x = max(0, min(self.WIN_WIDTH - 80, self.key_x))
        self.key_y = max(0, min(self.WIN_HEIGHT - 100, self.key_y))

        key_center_x = self.key_x + 40
        key_center_y = self.key_y + 50
        chest_center_x = self.chest_x + 100
        chest_center_y = self.chest_y + 75

        dist = math.sqrt(
            (key_center_x - chest_center_x) ** 2 + (key_center_y - chest_center_y) ** 2
        )

        if dist < self.WIN_THRESHOLD and not self.key_fitted:
            self.key_fitted = True
            self.show_confetti = True
            self.confetti_done = False
            self.confetti_particles = []
            for _ in range(100):
                self.confetti_particles.append(Confetti(chest_center_x, chest_center_y))
        elif dist >= self.WIN_THRESHOLD and self.key_fitted:
            self.key_fitted = False
            self.show_confetti = False
            self.confetti_done = True
            self._randomize_chest()

        if self.show_confetti:
            for p in self.confetti_particles:
                p.update()
            self.confetti_particles = [p for p in self.confetti_particles if p.life > 0]
            if not self.confetti_particles:
                self.show_confetti = False
                self.confetti_done = True
                self.win_timer = 360

        if self.win_timer > 0:
            self.win_timer -= 1
            if self.win_timer == 0:
                self._randomize_chest()

        if self.phrase_timer > 0:
            self.phrase_timer -= 1

    def draw(self):
        self.screen.fill((255, 255, 255))

        self.screen.blit(self.chest_img, (self.chest_x, self.chest_y))

        keyhole_x = self.chest_x + 100 - 10
        keyhole_y = self.chest_y + 75 - 15
        pygame.draw.rect(self.screen, (80, 60, 20), (keyhole_x, keyhole_y, 20, 30))
        pygame.draw.rect(self.screen, (50, 40, 15), (keyhole_x + 6, keyhole_y, 8, 20))
        pygame.draw.circle(
            self.screen, (50, 40, 15), (keyhole_x + 10, keyhole_y + 20), 5
        )

        self.screen.blit(self.key_img, (self.key_x, self.key_y))

        if self.show_confetti:
            for p in self.confetti_particles:
                p.draw(self.screen)

        if self.key_fitted:
            win_text = self.big_font.render("KEY FITTED!", True, (255, 215, 0))
            self.screen.blit(
                win_text, (self.WIN_WIDTH // 2 - win_text.get_width() // 2, 20)
            )

        if self.phrase_timer > 0 and self.current_phrase:
            phrase_surface = self.font.render(
                self.current_phrase, True, (255, 255, 255)
            )
            phrase_rect = phrase_surface.get_rect(
                center=(self.WIN_WIDTH // 2, self.WIN_HEIGHT - 40)
            )
            bg_rect = phrase_rect.inflate(20, 10)
            pygame.draw.rect(self.screen, (0, 0, 0, 180), bg_rect, border_radius=8)
            self.screen.blit(phrase_surface, phrase_rect)

        pygame.display.flip()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

    def tick(self):
        self.clock.tick(60)

    def quit(self):
        pygame.quit()
