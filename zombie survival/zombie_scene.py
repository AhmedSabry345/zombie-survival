import math
import os
from pathlib import Path
import random
import time

import cv2 as cv
import numpy as np

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame


class Zombie:
    _animation_frames = None
    _attack_frames = None
    _attack_poses = (0.0, 0.18, 0.42, 0.78, 1.0, 0.72, 0.28, 0.0)
    _frame_count = 16
    _reference_depth = 5.5
    _sprite_size = (240, 300)
    _sprite_ground = 250
    _sprite_focal_length = 394
    _fall_duration = 0.45
    _death_duration = 1.65
    _part_bounds = {
        "head": (88, 94, 152, 166),
        "left_arm": (68, 138, 113, 207),
        "right_arm": (127, 138, 172, 207),
        "torso": (82, 148, 158, 224),
        "left_leg": (86, 201, 120, 264),
        "right_leg": (120, 201, 154, 264),
    }
    _hit_order = ("head", "left_arm", "right_arm", "left_leg", "right_leg", "torso")

    @staticmethod
    def _ground_y(height, distance):
        depth = min(max(distance / 6.0, 0.0), 1.0)
        return round(height * (0.43 + 0.46 * (1 - depth)))

    @staticmethod
    def _center_x(width, lane, distance):
        depth = min(max(distance / 6.0, 0.0), 1.0)
        perspective_lane = 0.018 + 0.32 * (1 - depth)
        return round(width / 2 + lane * width * perspective_lane)

    def __init__(self, lane, distance):
        self.lane = lane
        self.distance = distance
        self.phase = random.uniform(0, math.tau)
        self.spawn_timer = 0.0
        self.health = 100.0
        self.missing_parts = set()
        self.hit_stains = []
        self.death_timer = None
        self.death_direction = random.choice((-1, 1))
        self.ash_started = False
        self.is_attacking = False
        self.attack_timer = 0.0
        self.attack_cooldown = random.uniform(0.0, 0.5)
        self.ammo_drop_checked = False

    def _posture_scale(self):
        if self.death_timer is not None:
            return 1.0, 1.0
        missing_legs = sum(
            part in self.missing_parts for part in ("left_leg", "right_leg")
        )
        if missing_legs == 1:
            return 1.04, 0.94
        if missing_legs == 2:
            return 1.3, 0.58
        return 1.0, 1.0

    def _posture_offset(self, width, height):
        if self.death_timer is not None:
            return 0, 0
        missing_legs = sum(
            part in self.missing_parts for part in ("left_leg", "right_leg")
        )
        if missing_legs == 1:
            return (
                round(math.sin(self.phase * 0.45) * width * 0.006),
                round(abs(math.sin(self.phase * 0.55)) * height * 0.009),
            )
        return 0, 0

    def update(self, delta_time, other_zombies=None):
        if self.death_timer is not None:
            self.death_timer += delta_time
            return False
        if self.spawn_timer < 0.9:
            self.spawn_timer = min(0.9, self.spawn_timer + delta_time)
            self.phase += delta_time * 5.2
            return False

        missing_legs = sum(
            part in self.missing_parts for part in ("left_leg", "right_leg")
        )
        if missing_legs == 2:
            movement_speed = 0.055
            gait_speed = 1.55
        elif missing_legs == 1:
            movement_speed = 0.12
            gait_speed = 3.25
        else:
            movement_speed = 0.24
            gait_speed = 5.2
        self.phase += delta_time * gait_speed
        self.attack_cooldown = max(0.0, self.attack_cooldown - delta_time)
        if self.is_attacking:
            self.attack_timer += delta_time
            if self.attack_timer >= 0.46:
                self.is_attacking = False
                self.attack_timer = 0.0
                self.attack_cooldown = 1.15
                return True
            return False

        separation = 0.0
        for other in other_zombies or ():
            if other is self or other.death_timer is not None:
                continue
            lane_gap = self.lane - other.lane
            distance_gap = abs(self.distance - other.distance)
            if distance_gap < 0.72 and abs(lane_gap) < 0.3:
                if abs(lane_gap) < 0.001:
                    direction = -1.0 if self.phase < other.phase else 1.0
                else:
                    direction = math.copysign(1.0, lane_gap)
                separation += direction * (0.3 - abs(lane_gap))
        target_lane = max(-0.82, min(0.82, separation))
        self.lane += max(-0.2 * delta_time,
                         min(0.2 * delta_time, (target_lane - self.lane) * 0.7 * delta_time))

        if self.distance <= 1.45:
            self.distance = 1.45
            if self.attack_cooldown <= 0.0:
                self.is_attacking = True
                self.attack_timer = 0.0
            return False

        self.distance -= movement_speed * delta_time
        return False

    def draw(self, canvas):
        self.prepare_animation()
        height, width = canvas.shape[:2]
        camera_depth = self.distance + 3.5
        scale = (height / 480) * self._reference_depth / camera_depth
        spawn_scale = self._spawn_scale() if self.death_timer is None else 1.0
        attack_progress = min(self.attack_timer / 0.46, 1.0) if self.is_attacking else 0.0
        attack_lunge = (
            math.sin(math.pi * attack_progress)
            if self.is_attacking else 0.0
        )
        if self.is_attacking:
            spawn_scale *= 1.0 + attack_lunge * 0.24
        scale *= spawn_scale
        if self.is_attacking:
            attack_index = round(attack_progress * (len(self._attack_frames) - 1))
            sprite, sprite_mask = self._attack_frames[attack_index]
        else:
            frame_index = round((self.phase % math.tau) * self._frame_count / math.tau) % self._frame_count
            sprite, sprite_mask = self._animation_frames[frame_index]
        if self.hit_stains:
            sprite = sprite.copy()
            for stain_x, stain_y, stain_size in self.hit_stains:
                center = (round(stain_x), round(stain_y))
                cv.ellipse(sprite, center, (stain_size, max(2, stain_size // 2)),
                           -22, 0, 360, (10, 15, 160), -1, cv.LINE_AA)
                cv.circle(sprite, (center[0] + stain_size, center[1] - 2),
                          max(1, stain_size // 3), (5, 10, 110), -1, cv.LINE_AA)
        posture_width, posture_height = self._posture_scale()
        sprite_width = max(1, round(sprite.shape[1] * scale * posture_width))
        sprite_height = max(1, round(sprite.shape[0] * scale * posture_height))
        interpolation = cv.INTER_AREA if scale < 1 else cv.INTER_LINEAR
        sprite = cv.resize(sprite, (sprite_width, sprite_height), interpolation=interpolation)
        if self.missing_parts:
            sprite_mask = sprite_mask.copy()
            for part in self.missing_parts:
                left, top, right, bottom = self._part_bounds[part]
                sprite_mask[top:bottom, left:right] = 0
        sprite_mask = cv.resize(sprite_mask, (sprite_width, sprite_height), interpolation=cv.INTER_NEAREST)

        center_x = self._center_x(width, self.lane, self.distance)
        ground_y = self._ground_y(height, self.distance)
        offset_x, offset_y = self._posture_offset(width, height)
        center_x += offset_x
        ground_y += offset_y
        ground_y += round(height * 0.035 * attack_lunge)
        cv.ellipse(canvas, (center_x, ground_y + 3),
               (max(4, sprite_width // 6), max(2, sprite_width // 20)),
               0, 0, 360, (5, 12, 8), -1, cv.LINE_AA)
        opacity = 1.0
        if self.death_timer is not None:
            fall_progress = min(self.death_timer / self._fall_duration, 1.0)
            ash_progress = min(
                max((self.death_timer - self._fall_duration) /
                    (self._death_duration - self._fall_duration), 0.0), 1.0
            )
            opacity = 1.0 - ash_progress
            tint = np.full_like(sprite, (55, 60, 65))
            sprite = cv.addWeighted(sprite, 1.0 - ash_progress * 0.65,
                                    tint, ash_progress * 0.65, 0)
            pivot = (sprite_width / 2, sprite_height * self._sprite_ground / self._sprite_size[1])
            rotated_size = math.ceil(math.hypot(sprite_width, sprite_height))
            fall_ease = fall_progress * fall_progress * (3 - 2 * fall_progress)
            rotation = cv.getRotationMatrix2D(
                pivot, self.death_direction * 86 * fall_ease,
                1.0 - fall_progress * 0.07 - ash_progress * 0.12
            )
            target_pivot = (rotated_size / 2, rotated_size * self._sprite_ground / self._sprite_size[1])
            rotation[0, 2] += target_pivot[0] - pivot[0]
            rotation[1, 2] += target_pivot[1] - pivot[1]
            sprite = cv.warpAffine(sprite, rotation, (rotated_size, rotated_size),
                                   flags=cv.INTER_LINEAR, borderMode=cv.BORDER_CONSTANT)
            sprite_mask = cv.warpAffine(sprite_mask, rotation, (rotated_size, rotated_size),
                                        flags=cv.INTER_NEAREST, borderMode=cv.BORDER_CONSTANT)
            sprite_width = rotated_size
            sprite_height = rotated_size

        left = center_x - sprite_width // 2
        top = ground_y - round(sprite_height * self._sprite_ground / self._sprite_size[1])
        source_left = max(0, -left)
        source_top = max(0, -top)
        target_left = max(0, left)
        target_top = max(0, top)
        copy_width = min(sprite_width - source_left, width - target_left)
        copy_height = min(sprite_height - source_top, height - target_top)
        if copy_width <= 0 or copy_height <= 0:
            return

        source = sprite[source_top:source_top + copy_height, source_left:source_left + copy_width]
        mask = sprite_mask[source_top:source_top + copy_height, source_left:source_left + copy_width]
        target = canvas[target_top:target_top + copy_height, target_left:target_left + copy_width]
        if opacity == 1.0:
            visible = mask > 0
            target[visible] = source[visible]
        else:
            alpha = (mask.astype(np.float32) / 255 * opacity)[:, :, None]
            target[:] = (source * alpha + target * (1 - alpha)).astype(np.uint8)

    def _spawn_scale(self):
        progress = min(self.spawn_timer / 0.9, 1.0)
        if progress < 0.72:
            return 0.08 + 1.17 * progress / 0.72
        return 1.25 - 0.25 * (progress - 0.72) / 0.28

    def ash_points(self, canvas_shape, count=35):
        height, width = canvas_shape[:2]
        scale = (height / 480) * self._reference_depth / (self.distance + 3.5)
        if self.death_timer is None:
            scale *= self._spawn_scale()
        posture_width, posture_height = self._posture_scale()
        sprite_width = max(1, round(self._sprite_size[0] * scale * posture_width))
        sprite_height = max(1, round(self._sprite_size[1] * scale * posture_height))
        frame_index = round((self.phase % math.tau) * self._frame_count / math.tau) % self._frame_count
        _, sprite_mask = self._animation_frames[frame_index]
        sprite_mask = sprite_mask.copy()
        for part in self.missing_parts:
            left, top, right, bottom = self._part_bounds[part]
            sprite_mask[top:bottom, left:right] = 0
        rows, columns = np.nonzero(sprite_mask)
        if not len(rows):
            return []

        selected = np.random.choice(len(rows), size=min(count, len(rows)), replace=False)
        center_x = self._center_x(width, self.lane, self.distance)
        ground_y = self._ground_y(height, self.distance)
        offset_x, offset_y = self._posture_offset(width, height)
        center_x += offset_x
        ground_y += offset_y
        pivot = (sprite_width / 2, sprite_height * self._sprite_ground / self._sprite_size[1])
        rotated_size = math.ceil(math.hypot(sprite_width, sprite_height))
        fall_progress = min((self.death_timer or 0.0) / self._fall_duration, 1.0)
        fall_ease = fall_progress * fall_progress * (3 - 2 * fall_progress)
        rotation = cv.getRotationMatrix2D(
            pivot, self.death_direction * 86 * fall_ease,
            1.0 - fall_progress * 0.07
        )
        target_pivot = (rotated_size / 2, rotated_size * self._sprite_ground / self._sprite_size[1])
        rotation[0, 2] += target_pivot[0] - pivot[0]
        rotation[1, 2] += target_pivot[1] - pivot[1]
        left = center_x - rotated_size // 2
        top = ground_y - round(rotated_size * self._sprite_ground / self._sprite_size[1])

        points = []
        for index in selected:
            local_x = columns[index] * sprite_width / self._sprite_size[0]
            local_y = rows[index] * sprite_height / self._sprite_size[1]
            rotated_x = rotation[0, 0] * local_x + rotation[0, 1] * local_y + rotation[0, 2]
            rotated_y = rotation[1, 0] * local_x + rotation[1, 1] * local_y + rotation[1, 2]
            points.append((left + round(rotated_x), top + round(rotated_y)))
        return points

    def hit_test(self, point, canvas_shape):
        if point is None:
            return None

        height, width = canvas_shape[:2]
        scale = (height / 480) * self._reference_depth / (self.distance + 3.5)
        if self.death_timer is None:
            scale *= self._spawn_scale()
        posture_width, posture_height = self._posture_scale()
        sprite_width = max(1, round(self._sprite_size[0] * scale * posture_width))
        sprite_height = max(1, round(self._sprite_size[1] * scale * posture_height))
        center_x = self._center_x(width, self.lane, self.distance)
        ground_y = self._ground_y(height, self.distance)
        offset_x, offset_y = self._posture_offset(width, height)
        center_x += offset_x
        ground_y += offset_y
        sprite_left = center_x - sprite_width // 2
        sprite_top = ground_y - round(sprite_height * self._sprite_ground / self._sprite_size[1])

        for part in self._hit_order:
            if part in self.missing_parts:
                continue
            left, top, right, bottom = self._part_bounds[part]
            bounds = (
                sprite_left + round(left * sprite_width / self._sprite_size[0]),
                sprite_top + round(top * sprite_height / self._sprite_size[1]),
                sprite_left + round(right * sprite_width / self._sprite_size[0]),
                sprite_top + round(bottom * sprite_height / self._sprite_size[1]),
            )
            if bounds[0] <= point[0] <= bounds[2] and bounds[1] <= point[1] <= bounds[3]:
                return part
        return None

    def take_hit(self, part, damage=20.0):
        if part not in self._part_bounds or self.death_timer is not None:
            return None
        if part in self.missing_parts:
            return None

        damage_multiplier = {
            "head": 1.6,
            "torso": 1.25,
            "left_arm": 0.8,
            "right_arm": 0.8,
            "left_leg": 0.8,
            "right_leg": 0.8,
        }[part]
        self.health = max(0.0, self.health - damage * damage_multiplier)
        if self.health <= 0:
            self.death_timer = 0.0
            return "fatal"
        if part not in ("head", "torso"):
            self.missing_parts.add(part)
        return "injury"

    def add_hit_stain(self, point, canvas_shape):
        height, width = canvas_shape[:2]
        scale = (height / 480) * self._reference_depth / (self.distance + 3.5)
        if self.death_timer is None:
            scale *= self._spawn_scale()
        posture_width, posture_height = self._posture_scale()
        sprite_width = max(1, round(self._sprite_size[0] * scale * posture_width))
        sprite_height = max(1, round(self._sprite_size[1] * scale * posture_height))
        sprite_left = self._center_x(width, self.lane, self.distance) - sprite_width // 2
        sprite_top = self._ground_y(height, self.distance) - round(
            sprite_height * self._sprite_ground / self._sprite_size[1]
        )
        offset_x, offset_y = self._posture_offset(width, height)
        sprite_left += offset_x
        sprite_top += offset_y
        local_x = (point[0] - sprite_left) * self._sprite_size[0] / sprite_width
        local_y = (point[1] - sprite_top) * self._sprite_size[1] / sprite_height
        self.hit_stains.append((local_x, local_y, random.randint(7, 12)))

    def detach_part(self, part, hit_point, canvas_shape):
        if part not in self._part_bounds:
            return None
        self.missing_parts.add(part)
        self.prepare_animation()
        frame_index = round((self.phase % math.tau) * self._frame_count / math.tau) % self._frame_count
        sprite, sprite_mask = self._animation_frames[frame_index]
        left, top, right, bottom = self._part_bounds[part]
        height, width = canvas_shape[:2]
        scale = (height / 480) * self._reference_depth / (self.distance + 3.5)
        posture_width, posture_height = self._posture_scale()
        scale_x = scale * posture_width
        scale_y = scale * posture_height
        part_sprite = sprite[top:bottom, left:right].copy()
        for stain_x, stain_y, stain_size in self.hit_stains:
            if left <= stain_x <= right and top <= stain_y <= bottom:
                stain_center = (
                    round((stain_x - left) * part_sprite.shape[1] / (right - left)),
                    round((stain_y - top) * part_sprite.shape[0] / (bottom - top)),
                )
                cv.ellipse(part_sprite, stain_center,
                           (stain_size, max(2, stain_size // 2)),
                           -22, 0, 360, (10, 15, 160), -1, cv.LINE_AA)
        part_mask = sprite_mask[top:bottom, left:right]
        size = (max(1, round(part_sprite.shape[1] * scale_x)),
            max(1, round(part_sprite.shape[0] * scale_y)))
        part_sprite = cv.resize(part_sprite, size, interpolation=cv.INTER_AREA)
        part_mask = cv.resize(part_mask, size, interpolation=cv.INTER_NEAREST)
        center_x = self._center_x(width, self.lane, self.distance)
        ground_y = self._ground_y(height, self.distance)
        direction = 1 if hit_point[0] >= center_x else -1
        return DetachedPart(part_sprite, part_mask, hit_point, ground_y, direction)

    @classmethod
    def prepare_animation(cls):
        width, height = cls._sprite_size
        if cls._animation_frames is None:
            cls._animation_frames = []
            for frame_index in range(cls._frame_count):
                phase = math.tau * frame_index / cls._frame_count
                sprite = np.zeros((height, width, 3), dtype=np.uint8)
                mask = np.zeros((height, width), dtype=np.uint8)
                cls._render_model(
                    sprite, mask, phase, cls._reference_depth,
                    cls._sprite_ground, cls._sprite_focal_length
                )
                cls._animation_frames.append((sprite, mask))

        if cls._attack_frames is None:
            cls._attack_frames = []
            for attack_pose in cls._attack_poses:
                sprite = np.zeros((height, width, 3), dtype=np.uint8)
                mask = np.zeros((height, width), dtype=np.uint8)
                cls._render_model(
                    sprite, mask, 0.0, cls._reference_depth,
                    cls._sprite_ground, cls._sprite_focal_length, attack_pose
                )
                cls._attack_frames.append((sprite, mask))

    @classmethod
    def _render_model(cls, canvas, mask, phase, camera_depth, ground_y, focal_length,
                      attack=0.0):
        width = canvas.shape[1]
        gait = math.sin(phase)
        bob = 0.025 * (1 - math.cos(phase * 2))
        yaw = 0.04 * math.sin(phase * 0.5)
        cosine = math.cos(yaw)
        sine = math.sin(yaw)
        faces = []
        faces.extend(cls._ellipsoid_faces(
            (0, 0.96 + bob, -attack * 0.08), (0.37, 0.48, 0.25), (28, 52, 42)
        ))
        faces.extend(cls._ellipsoid_faces((0, 1.31 + bob, 0), (0.14, 0.17, 0.15), (38, 85, 48)))
        head_center = (0.025 * gait, 1.68 + bob, 0.015 + attack * 0.1)
        faces.extend(cls._ellipsoid_faces(head_center, (0.34, 0.37, 0.29), (42, 95, 52)))

        face_z = 0.245 + attack * 0.1
        faces.extend(cls._ellipsoid_faces((-0.13, 1.71 + bob, face_z), (0.095, 0.12, 0.065), (200, 205, 185)))
        faces.extend(cls._ellipsoid_faces((0.12, 1.68 + bob, face_z + 0.007), (0.075, 0.09, 0.055), (200, 205, 185)))
        faces.extend(cls._ellipsoid_faces((-0.105, 1.70 + bob, face_z + 0.055), (0.035, 0.045, 0.025), (10, 20, 10)))
        faces.extend(cls._ellipsoid_faces((0.14, 1.67 + bob, face_z + 0.055), (0.028, 0.038, 0.022), (10, 20, 10)))
        mouth_height = 0.065 + attack * 0.07
        faces.extend(cls._ellipsoid_faces(
            (0.0, 1.56 + bob - attack * 0.015, face_z + 0.045),
            (0.14, mouth_height, 0.045), (20, 10, 25)
        ))
        faces.extend(cls._ellipsoid_faces(
            (0.0, 1.535 + bob - attack * 0.055, face_z + 0.082),
            (0.075, 0.018 + attack * 0.012, 0.012), (210, 195, 140)
        ))
        faces.extend(cls._ellipsoid_faces((-0.21, 1.94 + bob, -0.015), (0.13, 0.075, 0.22), (32, 42, 30)))
        faces.extend(cls._ellipsoid_faces((0.0, 2.015 + bob, 0.0), (0.11, 0.09, 0.19), (32, 42, 30)))
        faces.extend(cls._ellipsoid_faces((0.0, 1.04 + bob, 0.225), (0.22, 0.31, 0.055), (95, 90, 65)))
        faces.extend(cls._limb_faces((0.0, 1.27 + bob, 0.28), (0.0, 0.77 + bob, 0.28), 0.045, 0.018, (30, 38, 95)))
        faces.extend(cls._ellipsoid_faces((0.0, 1.24 + bob, 0.292), (0.07, 0.07, 0.04), (30, 38, 95)))
        faces.extend(cls._ellipsoid_faces((-0.22, 0.88 + bob, 0.245), (0.09, 0.1, 0.045), (75, 38, 35)))

        for side, swing in ((-1, gait), (1, -gait)):
            shoulder = (side * 0.31, 1.22 + bob, 0.0)
            elbow = (side * (0.5 - attack * 0.06),
                     1.12 + bob + swing * 0.045 + attack * 0.2,
                     0.21 + swing * 0.06 + attack * 0.16)
            wrist = (side * (0.63 - attack * 0.1),
                     1.1 + bob + swing * 0.07 + attack * 0.35,
                     0.46 + swing * 0.12 + attack * 0.42)
            faces.extend(cls._limb_faces(shoulder, elbow, 0.15, 0.125, (38, 48, 35)))
            faces.extend(cls._limb_faces(elbow, wrist, 0.11, 0.08, (42, 95, 52)))
            faces.extend(cls._ellipsoid_faces(wrist, (0.12, 0.09, 0.11), (42, 95, 52)))
            for finger_offset in (-0.07, 0.0, 0.07):
                finger_end = (wrist[0] + finger_offset, wrist[1] - 0.13, wrist[2] + 0.035)
                faces.extend(cls._limb_faces(wrist, finger_end, 0.035, 0.022, (42, 95, 52)))

            hip = (side * 0.16, 0.57 + bob, 0.0)
            knee = (side * 0.17, 0.32 + bob + max(0, swing) * 0.055, swing * 0.1)
            ankle = (side * 0.18, 0.1 + bob + max(0, swing) * 0.1, swing * 0.18)
            faces.extend(cls._limb_faces(hip, knee, 0.14, 0.105, (32, 38, 32)))
            faces.extend(cls._limb_faces(knee, ankle, 0.105, 0.075, (32, 38, 32)))
            faces.extend(cls._ellipsoid_faces(
                (ankle[0], ankle[1] - 0.015, ankle[2] + 0.09),
                (0.15, 0.085, 0.22), (28, 30, 25)
            ))

        projected_faces = []
        for points, color in faces:
            transformed = []
            depths = []
            for x, y, z in points:
                rotated_x = x * cosine + z * sine
                rotated_z = -x * sine + z * cosine
                depth = camera_depth - rotated_z
                screen_x = width / 2 + rotated_x * focal_length / depth
                screen_y = ground_y - y * focal_length / depth
                transformed.append((round(screen_x), round(screen_y)))
                depths.append(depth)
            projected_faces.append((sum(depths) / len(depths), transformed, color))

        for _, points, color in sorted(projected_faces, key=lambda face: face[0], reverse=True):
            polygon = np.asarray(points, dtype=np.int32)
            cv.fillConvexPoly(canvas, polygon, color, cv.LINE_AA)
            cv.fillConvexPoly(mask, polygon, 255, cv.LINE_AA)

    @staticmethod
    def _ellipsoid_faces(center, radii, color):
        center_x, center_y, center_z = center
        radius_x, radius_y, radius_z = radii
        rings = 5
        sectors = 8
        vertices = []
        for ring in range(rings + 1):
            latitude = -math.pi / 2 + math.pi * ring / rings
            for sector in range(sectors):
                longitude = math.tau * sector / sectors
                vertices.append((
                    center_x + radius_x * math.cos(latitude) * math.sin(longitude),
                    center_y + radius_y * math.sin(latitude),
                    center_z + radius_z * math.cos(latitude) * math.cos(longitude),
                ))

        faces = []
        for ring in range(rings):
            for sector in range(sectors):
                next_sector = (sector + 1) % sectors
                points = [
                    vertices[ring * sectors + sector],
                    vertices[ring * sectors + next_sector],
                    vertices[(ring + 1) * sectors + next_sector],
                    vertices[(ring + 1) * sectors + sector],
                ]
                normal_z = sum((point[2] - center_z) / radius_z for point in points) / 4
                shade = 0.5 + 0.5 * max(0.0, normal_z)
                shaded = tuple(int(min(255, channel * shade)) for channel in color)
                faces.append((points, shaded))
        return faces

    @staticmethod
    def _limb_faces(start, end, radius_start, radius_end, color):
        start_vector = np.asarray(start, dtype=np.float64)
        end_vector = np.asarray(end, dtype=np.float64)
        direction = end_vector - start_vector
        direction /= np.linalg.norm(direction)
        reference = np.array((0.0, 0.0, 1.0))
        if abs(np.dot(direction, reference)) > 0.9:
            reference = np.array((0.0, 1.0, 0.0))
        axis_x = np.cross(direction, reference)
        axis_x /= np.linalg.norm(axis_x)
        axis_y = np.cross(direction, axis_x)
        sectors = 8
        rings = []
        for center, radius in ((start_vector, radius_start), (end_vector, radius_end)):
            ring = []
            for sector in range(sectors):
                angle = math.tau * sector / sectors
                offset = radius * (axis_x * math.cos(angle) + axis_y * math.sin(angle))
                ring.append(tuple(center + offset))
            rings.append(ring)

        faces = []
        for sector in range(sectors):
            next_sector = (sector + 1) % sectors
            points = [rings[0][sector], rings[0][next_sector],
                      rings[1][next_sector], rings[1][sector]]
            normal_z = sum(point[2] for point in points) / 4
            shade = 0.55 + 0.45 * max(0.0, min(1.0, normal_z / 0.5))
            shaded = tuple(int(min(255, channel * shade)) for channel in color)
            faces.append((points, shaded))
        faces.append((rings[0], tuple(int(min(255, channel * 0.48)) for channel in color)))
        faces.append((rings[1], color))
        return faces


class Bullet:
    def __init__(self, start, target, damage=20.0, weapon_type=1):
        self.start = np.asarray(start, dtype=np.float32)
        self.target = np.asarray(target, dtype=np.float32)
        self.damage = damage
        self.weapon_type = weapon_type
        self.label = "AK" if weapon_type == 2 else "P"
        self.color = (45, 215, 240) if weapon_type == 2 else (100, 235, 155)
        self.position = self.start.copy()
        self.distance = float(np.linalg.norm(self.target - self.start))
        self.duration = max(0.1, self.distance / 1300.0)
        self.elapsed = 0.0
        self.gravity = 1250.0
        self.arrived = self.distance == 0

    def update(self, delta_time):
        previous = tuple(self.position.round().astype(int))
        self.elapsed = min(self.duration, self.elapsed + delta_time)
        fraction = self.elapsed / self.duration
        self.position = self.start + (self.target - self.start) * fraction
        self.position[1] -= 0.5 * self.gravity * self.elapsed * (self.duration - self.elapsed)
        self.arrived = self.elapsed >= self.duration
        if self.arrived:
            self.position = self.target.copy()
        return previous

    def draw(self, canvas, previous):
        current = tuple(self.position.round().astype(int))
        cv.line(canvas, previous, current, self.color, 4, cv.LINE_AA)
        cv.circle(canvas, current, 7, self.color, -1, cv.LINE_AA)
        cv.circle(canvas, current, 2, (255, 255, 255), -1, cv.LINE_AA)
        label_size = cv.getTextSize(self.label, cv.FONT_HERSHEY_SIMPLEX, 0.38, 1)[0]
        label_x = current[0] + 8
        label_y = current[1] - 8
        cv.rectangle(canvas, (label_x - 2, label_y - label_size[1] - 3),
                     (label_x + label_size[0] + 2, label_y + 3),
                     (18, 27, 27), -1, cv.LINE_AA)
        cv.putText(canvas, self.label, (label_x, label_y),
                   cv.FONT_HERSHEY_SIMPLEX, 0.38, self.color, 1, cv.LINE_AA)


class BloodDrop:
    def __init__(self, position):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(50, 160)
        self.x, self.y = position
        self.velocity_x = math.cos(angle) * speed
        self.velocity_y = math.sin(angle) * speed - 60
        self.radius = random.randint(2, 5)
        self.lifetime = random.uniform(0.3, 0.55)

    def update(self, delta_time):
        self.x += self.velocity_x * delta_time
        self.y += self.velocity_y * delta_time
        self.velocity_y += 280 * delta_time
        self.lifetime -= delta_time

    def draw(self, canvas):
        center = (round(self.x), round(self.y))
        cv.circle(canvas, center, self.radius, (5, 10, 255), -1, cv.LINE_AA)
        cv.circle(canvas, (center[0] - 1, center[1] - 1), 1, (150, 190, 255), -1, cv.LINE_AA)


class DetachedPart:
    def __init__(self, sprite, mask, position, ground_y, direction):
        self.sprite = sprite
        self.mask = mask
        self.x, self.y = map(float, position)
        self.ground_y = float(ground_y)
        self.velocity_x = direction * random.uniform(100, 220) + random.uniform(-45, 45)
        self.velocity_y = random.uniform(-300, -180)
        self.gravity = 720.0
        self.angle = random.uniform(-25, 25)
        self.angular_velocity = random.choice((-1, 1)) * random.uniform(180, 420)
        self.lifetime = 2.4
        self.bounce_count = 0
        self.ash_started = False
        self.width = sprite.shape[1]
        self.height = sprite.shape[0]

    def update(self, delta_time):
        self.velocity_y += self.gravity * delta_time
        self.x += self.velocity_x * delta_time
        self.y += self.velocity_y * delta_time
        self.angle += self.angular_velocity * delta_time
        if self.y + self.height / 2 >= self.ground_y:
            self.y = self.ground_y - self.height / 2
            if abs(self.velocity_y) > 55:
                self.velocity_y = -self.velocity_y * 0.28
                self.velocity_x *= 0.62
                self.angular_velocity *= 0.55
                self.bounce_count += 1
            else:
                self.velocity_y = 0.0
                self.velocity_x *= 0.82
                self.angular_velocity *= 0.8
        self.lifetime -= delta_time

    def draw(self, canvas):
        diagonal = max(1, math.ceil(math.hypot(self.width, self.height)))
        pivot = (self.width / 2, self.height / 2)
        rotation = cv.getRotationMatrix2D(pivot, self.angle, 1.0)
        rotation[0, 2] += diagonal / 2 - pivot[0]
        rotation[1, 2] += diagonal / 2 - pivot[1]
        sprite = cv.warpAffine(self.sprite, rotation, (diagonal, diagonal),
                               flags=cv.INTER_LINEAR, borderMode=cv.BORDER_CONSTANT)
        mask = cv.warpAffine(self.mask, rotation, (diagonal, diagonal),
                             flags=cv.INTER_NEAREST, borderMode=cv.BORDER_CONSTANT)

        left = round(self.x - diagonal / 2)
        top = round(self.y - diagonal / 2)
        source_left = max(0, -left)
        source_top = max(0, -top)
        target_left = max(0, left)
        target_top = max(0, top)
        copy_width = min(diagonal - source_left, canvas.shape[1] - target_left)
        copy_height = min(diagonal - source_top, canvas.shape[0] - target_top)
        if copy_width <= 0 or copy_height <= 0:
            return

        source = sprite[source_top:source_top + copy_height, source_left:source_left + copy_width]
        alpha_mask = mask[source_top:source_top + copy_height, source_left:source_left + copy_width]
        target = canvas[target_top:target_top + copy_height, target_left:target_left + copy_width]
        fade = min(1.0, self.lifetime / 0.45)
        alpha = (alpha_mask.astype(np.float32) / 255 * fade)[:, :, None]
        target[:] = (source * alpha + target * (1 - alpha)).astype(np.uint8)

    def ash_points(self, count=10):
        rows, columns = np.nonzero(self.mask)
        if not len(rows):
            return []
        selected = np.random.choice(len(rows), size=min(count, len(rows)), replace=False)
        diagonal = max(1, math.ceil(math.hypot(self.width, self.height)))
        pivot = (self.width / 2, self.height / 2)
        rotation = cv.getRotationMatrix2D(pivot, self.angle, 1.0)
        rotation[0, 2] += diagonal / 2 - pivot[0]
        rotation[1, 2] += diagonal / 2 - pivot[1]
        points = []
        for index in selected:
            x = rotation[0, 0] * columns[index] + rotation[0, 1] * rows[index] + rotation[0, 2]
            y = rotation[1, 0] * columns[index] + rotation[1, 1] * rows[index] + rotation[1, 2]
            points.append((round(self.x - diagonal / 2 + x), round(self.y - diagonal / 2 + y)))
        return points


class AshParticle:
    def __init__(self, position):
        self.x, self.y = position
        self.velocity_x = random.uniform(-45, 45)
        self.velocity_y = random.uniform(-100, -35)
        self.radius = random.randint(2, 5)
        self.shade = random.randint(100, 190)
        self.lifetime = random.uniform(0.75, 1.3)
        self.initial_lifetime = self.lifetime

    def update(self, delta_time):
        self.x += self.velocity_x * delta_time
        self.y += self.velocity_y * delta_time
        self.velocity_y += 32 * delta_time
        self.lifetime -= delta_time

    def draw(self, canvas):
        fade = max(0.0, self.lifetime / self.initial_lifetime)
        radius = max(1, round(self.radius * fade))
        shade = round(self.shade * fade)
        cv.circle(canvas, (round(self.x), round(self.y)), radius,
                  (shade, shade, shade), -1, cv.LINE_AA)


class SpawnEffect:
    duration = 1.05

    def __init__(self, lane, distance):
        self.lane = lane
        self.distance = distance
        self.age = 0.0
        self.clod_phase = random.uniform(0, math.tau)

    def update(self, delta_time):
        self.age += delta_time

    def draw(self, canvas):
        height, width = canvas.shape[:2]
        scale = (height / 480) * Zombie._reference_depth / (self.distance + 3.5)
        progress = min(self.age / self.duration, 1.0)
        growth = min(self.age / 0.42, 1.0)
        pulse = 0.93 + 0.07 * math.sin(self.age * 15)
        center = (
            Zombie._center_x(width, self.lane, self.distance),
            Zombie._ground_y(height, self.distance) + 2,
        )
        radius_x = max(4, round(45 * scale * (0.28 + 0.72 * growth) * pulse))
        radius_y = max(2, round(15 * scale * (0.28 + 0.72 * growth)))

        cv.ellipse(canvas, center, (radius_x, radius_y), 0, 0, 360,
                   (85, 125, 160), -1, cv.LINE_AA)
        cv.ellipse(canvas, (center[0], center[1] - max(1, radius_y // 3)),
                   (max(2, radius_x - 3), max(1, radius_y - 2)),
                   0, 0, 360, (30, 45, 55), -1, cv.LINE_AA)
        cv.ellipse(canvas, center, (radius_x, radius_y), 0, 195, 345,
                   (150, 185, 210), max(1, round(2 * scale)), cv.LINE_AA)


class AmmoPickup:
    def __init__(self, weapon_type, amount, lane, distance):
        self.weapon_type = weapon_type
        self.amount = amount
        self.lane = lane
        self.distance = distance
        self.age = 0.0
        self.lifetime = 30.0

    def update(self, delta_time):
        self.age += delta_time
        self.lifetime -= delta_time
        self.distance = max(1.4, self.distance - 0.9 * delta_time)
        self.lane *= max(0.0, 1.0 - 1.8 * delta_time)

    def draw(self, canvas):
        height, width = canvas.shape[:2]
        scale = (height / 480) * Zombie._reference_depth / (self.distance + 3.5)
        center_x = Zombie._center_x(width, self.lane, self.distance)
        ground_y = Zombie._ground_y(height, self.distance)
        bob = round(math.sin(self.age * 5) * 3 * scale)
        box_width = max(12, round(30 * scale))
        box_height = max(9, round(22 * scale))
        center_y = ground_y - box_height // 2 - round(9 * scale) + bob
        color = (72, 205, 230) if self.weapon_type == 2 else (90, 220, 150)
        player_x, player_y = width // 2, height - 12
        for index in range(1, 5):
            fraction = index / 5
            trail_point = (
                round(center_x + (player_x - center_x) * fraction),
                round(ground_y + (player_y - ground_y) * fraction),
            )
            cv.circle(canvas, trail_point, max(1, round((3 - fraction) * scale)),
                      color, -1, cv.LINE_AA)
        cv.ellipse(canvas, (center_x, ground_y + 2),
                   (max(5, box_width), max(2, box_height // 4)),
                   0, 0, 360, (16, 31, 24), -1, cv.LINE_AA)
        cv.rectangle(canvas, (center_x - box_width // 2, center_y - box_height // 2),
                     (center_x + box_width // 2, center_y + box_height // 2),
                     (28, 45, 43), -1, cv.LINE_AA)
        cv.rectangle(canvas, (center_x - box_width // 2, center_y - box_height // 2),
                     (center_x + box_width // 2, center_y + box_height // 2),
                     color, max(1, round(2 * scale)), cv.LINE_AA)
        cv.putText(canvas, f"+{self.amount}",
                   (center_x - box_width // 2, center_y - box_height),
                   cv.FONT_HERSHEY_SIMPLEX, max(0.28, 0.38 * scale),
                   (235, 245, 235), 1, cv.LINE_AA)


class ZombieScene:
    _vignette_masks = {}

    def __init__(self):
        Zombie.prepare_animation()
        self.zombies = []
        self.last_update = None
        self.max_zombies = 5
        self.wave_number = 0
        self.wave_size = 0
        self.wave_remaining = 0
        self.wave_spawn_timer = 0.0
        self.wave_intermission = None
        self.wave_clear_duration = 3.0
        self.bullets = []
        self.blood_drops = []
        self.ash_particles = []
        self.detached_parts = []
        self.spawn_cycle = []
        self.weapon_recoil = 0.0
        self.spawn_effects = []
        self.ammo_pickups = []
        self.ammo_pickup_notice = ""
        self.ammo_pickup_timer = 0.0
        self.next_automatic_shot = 0.0
        self.max_player_health = 100
        self.player_health = self.max_player_health
        self.player_hit_timer = 0.0
        self.player_hit_direction = 1
        self.weapon_specs = {
            1: {"name": "PISTOL", "capacity": 8, "starting_total": 45, "damage": 55.0},
            2: {"name": "AK", "capacity": 30, "starting_total": 120, "damage": 20.0},
        }
        self.ammo = {weapon: spec["capacity"] for weapon, spec in self.weapon_specs.items()}
        self.reserve_ammo = {
            weapon: spec["starting_total"] - spec["capacity"]
            for weapon, spec in self.weapon_specs.items()
        }
        self.reload_duration = 1.25
        self.reload_timer = 0.0
        self.reloading = False
        self.reload_weapon = None
        self.shot_sound = None
        self._load_shot_sound()

    def _load_shot_sound(self):
        sound_path = Path(__file__).with_name("cartoon_zombie_game_single_bullet.mp3")
        if not sound_path.is_file():
            return
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            pygame.mixer.set_num_channels(max(16, pygame.mixer.get_num_channels()))
            self.shot_sound = pygame.mixer.Sound(str(sound_path))
            self.shot_sound.set_volume(0.45)
        except (pygame.error, OSError):
            self.shot_sound = None

    def start(self, now=None):
        now = time.monotonic() if now is None else now
        self.spawn_cycle.clear()
        self.spawn_effects.clear()
        self.ammo_pickups.clear()
        self.ammo_pickup_notice = ""
        self.ammo_pickup_timer = 0.0
        self.zombies = []
        self.last_update = now
        self.bullets.clear()
        self.blood_drops.clear()
        self.ash_particles.clear()
        self.detached_parts.clear()
        self.weapon_recoil = 0.0
        self.next_automatic_shot = 0.0
        self.player_health = self.max_player_health
        self.player_hit_timer = 0.0
        self.player_hit_direction = 1
        self.ammo = {weapon: spec["capacity"] for weapon, spec in self.weapon_specs.items()}
        self.reserve_ammo = {
            weapon: spec["starting_total"] - spec["capacity"]
            for weapon, spec in self.weapon_specs.items()
        }
        self.reload_timer = 0.0
        self.reloading = False
        self.reload_weapon = None
        self.wave_number = 0
        self.wave_size = 0
        self.wave_remaining = 0
        self.wave_spawn_timer = 0.0
        self.wave_intermission = None
        self._begin_next_wave()

    def _begin_next_wave(self):
        self.wave_number += 1
        self.wave_size = min(3 + (self.wave_number - 1) * 2, 15)
        self.wave_remaining = self.wave_size
        self.wave_spawn_timer = 0.0
        self.wave_intermission = None

    @property
    def wave_zombies_left(self):
        living_zombies = sum(zombie.death_timer is None for zombie in self.zombies)
        return self.wave_remaining + living_zombies

    def _update_waves(self, delta_time):
        if self.wave_remaining > 0:
            self.wave_spawn_timer -= delta_time
            if self.wave_spawn_timer <= 0 and len(self.zombies) < self.max_zombies:
                self.zombies.append(self._spawn_zombie())
                self.wave_remaining -= 1
                self.wave_spawn_timer = max(0.42, 1.0 - self.wave_number * 0.04)
            return

        if self.zombies:
            self.wave_intermission = None
            return

        if self.wave_intermission is None:
            self.wave_intermission = self.wave_clear_duration
        else:
            self.wave_intermission -= delta_time
            if self.wave_intermission <= 0:
                self._begin_next_wave()

    def _spawn_zombie(self):
        if not self.spawn_cycle:
            self.spawn_cycle = [
                "far_left", "far_right", "mid_left", "mid_right",
                "near_left", "near_right", "center_far", "center_mid",
            ]
            random.shuffle(self.spawn_cycle)

        region = self.spawn_cycle.pop()
        if region.startswith("far_"):
            side = -1 if region.endswith("left") else 1
            lane = side * random.uniform(0.58, 0.78)
            distance = random.uniform(5.2, 5.8)
        elif region.startswith("mid_"):
            side = -1 if region.endswith("left") else 1
            lane = side * random.uniform(0.68, 0.78)
            distance = random.uniform(3.7, 4.8)
        elif region.startswith("near_"):
            side = -1 if region.endswith("left") else 1
            lane = side * random.uniform(0.62, 0.76)
            distance = random.uniform(2.5, 3.4)
        elif region == "center_far":
            lane = random.uniform(-0.3, 0.3)
            distance = random.uniform(4.8, 5.7)
        else:
            lane = random.uniform(-0.5, 0.5)
            distance = random.uniform(3.4, 4.7)
        zombie = Zombie(lane, distance)
        self.spawn_effects.append(SpawnEffect(lane, distance))
        return zombie

    def _ammo_drop_chance(self):
        return max(0.08, 0.4 * 0.82 ** max(0, self.wave_number - 1))

    def _roll_ammo_drop(self):
        if random.random() >= self._ammo_drop_chance():
            return None
        weapon_type = random.choice((1, 2))
        minimum, maximum = (3, 15) if weapon_type == 1 else (15, 35)
        amount = round(random.triangular(minimum, maximum, minimum))
        return weapon_type, amount

    def shoot(self, target, canvas_shape, weapon_type=1, now=None):
        if target is None:
            return False
        if weapon_type not in self.weapon_specs or self.reloading:
            return False
        if self.ammo[weapon_type] <= 0:
            self.start_reload(weapon_type)
            return False
        if weapon_type == 2:
            now = time.perf_counter() if now is None else now
            if now < self.next_automatic_shot:
                return False
            self.next_automatic_shot = now + 0.12
        height, width = canvas_shape[:2]
        muzzle_offset = 275 if weapon_type == 2 else 128
        damage = self.weapon_specs[weapon_type]["damage"]
        self.bullets.append(Bullet(
            (width // 2, height + 24 - muzzle_offset), target, damage, weapon_type
        ))
        self.ammo[weapon_type] -= 1
        self.weapon_recoil = 1.0
        if self.ammo[weapon_type] == 0:
            self.start_reload(weapon_type)
        if self.shot_sound is not None:
            self.shot_sound.play()
        return True

    def start_reload(self, weapon_type):
        if weapon_type not in self.weapon_specs or self.reloading:
            return False
        if self.ammo[weapon_type] >= self.weapon_specs[weapon_type]["capacity"]:
            return False
        if self.reserve_ammo[weapon_type] <= 0:
            return False
        self.reloading = True
        self.reload_weapon = weapon_type
        self.reload_timer = 0.0
        return True

    def update(self, canvas, now=None):
        now = time.monotonic() if now is None else now
        if self.last_update is None:
            self.start(now)

        delta_time = min(max(now - self.last_update, 0.0), 0.1)
        self.last_update = now
        self.weapon_recoil = max(0.0, self.weapon_recoil - delta_time * 5.5)
        self.player_hit_timer = max(0.0, self.player_hit_timer - delta_time)
        if self.reloading:
            self.reload_timer += delta_time
            if self.reload_timer >= self.reload_duration:
                reload_amount = min(
                    self.weapon_specs[self.reload_weapon]["capacity"] - self.ammo[self.reload_weapon],
                    self.reserve_ammo[self.reload_weapon],
                )
                self.ammo[self.reload_weapon] += reload_amount
                self.reserve_ammo[self.reload_weapon] -= reload_amount
                self.reloading = False
                self.reload_timer = 0.0
                self.reload_weapon = None
        for zombie in self.zombies:
            previous_death_time = zombie.death_timer
            if zombie.update(delta_time, self.zombies):
                self.player_health = max(0, self.player_health - 12)
                self.player_hit_timer = 0.34
                self.player_hit_direction *= -1
            if (previous_death_time is not None
                    and previous_death_time < zombie._fall_duration <= zombie.death_timer
                    and not zombie.ash_started):
                self.ash_particles.extend(
                    AshParticle(point) for point in zombie.ash_points(canvas.shape)
                )
                zombie.ash_started = True
            if (zombie.death_timer is not None
                    and zombie.death_timer >= zombie._death_duration
                    and not zombie.ammo_drop_checked):
                zombie.ammo_drop_checked = True
                drop = self._roll_ammo_drop()
                if drop is not None:
                    weapon_type, amount = drop
                    self.ammo_pickups.append(
                        AmmoPickup(weapon_type, amount, zombie.lane, zombie.distance)
                    )
        self.zombies = [
            zombie for zombie in self.zombies
            if (zombie.death_timer is not None and zombie.death_timer < zombie._death_duration)
            or (zombie.death_timer is None and zombie.distance > 1.0)
        ]

        self._update_waves(delta_time)

        for effect in self.spawn_effects:
            effect.update(delta_time)
        self.spawn_effects = [effect for effect in self.spawn_effects if effect.age < effect.duration]

        self.ammo_pickup_timer = max(0.0, self.ammo_pickup_timer - delta_time)
        for pickup in self.ammo_pickups:
            pickup.update(delta_time)
        collected_pickups = [pickup for pickup in self.ammo_pickups if pickup.distance <= 1.45]
        for pickup in collected_pickups:
            self.reserve_ammo[pickup.weapon_type] += pickup.amount
            weapon_name = self.weapon_specs[pickup.weapon_type]["name"]
            self.ammo_pickup_notice = f"+{pickup.amount} {weapon_name} AMMO"
            self.ammo_pickup_timer = 1.5
        self.ammo_pickups = [
            pickup for pickup in self.ammo_pickups
            if pickup.distance > 1.45 and pickup.lifetime > 0
        ]

        active_bullets = []
        for bullet in self.bullets:
            previous = bullet.update(delta_time)
            if bullet.arrived:
                for zombie in sorted(self.zombies, key=lambda item: item.distance):
                    part = zombie.hit_test(tuple(bullet.target), canvas.shape)
                    if part:
                        injury = zombie.take_hit(part, bullet.damage)
                        if injury:
                            if part in ("head", "torso"):
                                zombie.add_hit_stain(tuple(bullet.target), canvas.shape)
                            detached_part = None
                            if injury == "fatal" or part not in ("head", "torso"):
                                detached_part = zombie.detach_part(
                                    part, tuple(bullet.target), canvas.shape
                                )
                            if detached_part:
                                self.detached_parts.append(detached_part)
                            count = 16 if injury == "fatal" else 11
                            self.blood_drops.extend(BloodDrop(tuple(bullet.target)) for _ in range(count))
                            break
            else:
                active_bullets.append((bullet, previous))
        self.bullets = [bullet for bullet, _ in active_bullets]

        for drop in self.blood_drops:
            drop.update(delta_time)
        self.blood_drops = [drop for drop in self.blood_drops if drop.lifetime > 0]
        for particle in self.ash_particles:
            particle.update(delta_time)
        self.ash_particles = [particle for particle in self.ash_particles if particle.lifetime > 0]
        for part in self.detached_parts:
            if part.lifetime > 0.55 and part.lifetime - delta_time <= 0.55 and not part.ash_started:
                self.ash_particles.extend(AshParticle(point) for point in part.ash_points())
                part.ash_started = True
            part.update(delta_time)
        self.detached_parts = [part for part in self.detached_parts if part.lifetime > 0]

        self._draw_terrain(canvas)
        for effect in self.spawn_effects:
            effect.draw(canvas)
        for pickup in self.ammo_pickups:
            pickup.draw(canvas)
        for zombie in sorted(self.zombies, key=lambda item: item.distance, reverse=True):
            zombie.draw(canvas)
        for part in self.detached_parts:
            part.draw(canvas)
        for particle in self.ash_particles:
            particle.draw(canvas)
        for drop in self.blood_drops:
            drop.draw(canvas)
        for bullet, previous in active_bullets:
            bullet.draw(canvas, previous)

        self._apply_cinematic_vignette(canvas)

        width = canvas.shape[1]
        cv.putText(canvas, f"WAVE {self.wave_number}  |  ZOMBIES LEFT {self.wave_zombies_left}",
               (20, 36), cv.FONT_HERSHEY_SIMPLEX, 0.58,
               (215, 235, 221), 2, cv.LINE_AA)
        self._draw_wave_intermission(canvas)
        if self.ammo_pickup_timer > 0:
            cv.putText(canvas, self.ammo_pickup_notice, (20, 62),
                       cv.FONT_HERSHEY_SIMPLEX, 0.5, (100, 225, 190), 1, cv.LINE_AA)
        self._draw_health_bar(canvas)
        if self.player_hit_timer > 0:
            flash = min(1.0, self.player_hit_timer / 0.34)
            color = (round(15 * flash), round(20 * flash), round(255 * flash))
            cv.rectangle(canvas, (2, 2), (canvas.shape[1] - 3, canvas.shape[0] - 3),
                         color, max(1, round(6 * flash)), cv.LINE_AA)

    def _draw_wave_intermission(self, canvas):
        if self.wave_intermission is None:
            return

        height, width = canvas.shape[:2]
        panel_width = max(1, min(width - 24, 360))
        panel_height = max(1, min(height - 24, 148))
        left = (width - panel_width) // 2
        top = (height - panel_height) // 2
        panel = canvas[top:top + panel_height, left:left + panel_width]
        tint = np.full_like(panel, (18, 31, 28))
        cv.addWeighted(panel, 0.3, tint, 0.7, 0, panel)
        cv.rectangle(canvas, (left, top), (left + panel_width, top + panel_height),
                     (96, 157, 127), 1, cv.LINE_AA)

        title = "WAVE CLEARED"
        title_size = cv.getTextSize(title, cv.FONT_HERSHEY_SIMPLEX, 0.72, 2)[0]
        cv.putText(canvas, title, ((width - title_size[0]) // 2, top + 42),
                   cv.FONT_HERSHEY_SIMPLEX, 0.72, (135, 226, 184), 2, cv.LINE_AA)
        subtitle = "NEXT WAVE IN"
        subtitle_size = cv.getTextSize(subtitle, cv.FONT_HERSHEY_SIMPLEX, 0.43, 1)[0]
        cv.putText(canvas, subtitle, ((width - subtitle_size[0]) // 2, top + 69),
                   cv.FONT_HERSHEY_SIMPLEX, 0.43, (205, 217, 207), 1, cv.LINE_AA)
        countdown = str(max(1, math.ceil(self.wave_intermission)))
        countdown_size = cv.getTextSize(countdown, cv.FONT_HERSHEY_SIMPLEX, 1.35, 3)[0]
        cv.putText(canvas, countdown,
                   ((width - countdown_size[0]) // 2, top + panel_height - 16),
                   cv.FONT_HERSHEY_SIMPLEX, 1.35, (235, 245, 235), 3, cv.LINE_AA)

    @classmethod
    def _apply_cinematic_vignette(cls, canvas):
        rows, cols = canvas.shape[:2]
        size = (rows, cols)
        mask = cls._vignette_masks.get(size)
        if mask is None:
            kernel_x = cv.getGaussianKernel(cols, cols * 0.55)
            kernel_y = cv.getGaussianKernel(rows, rows * 0.55)
            weight = kernel_y * kernel_x.T
            weight = 0.28 + 0.72 * weight / weight.max()
            mask = cv.cvtColor(np.round(weight * 255).astype(np.uint8), cv.COLOR_GRAY2BGR)
            cls._vignette_masks[size] = mask
        cv.multiply(canvas, mask, dst=canvas, scale=1 / 255, dtype=cv.CV_8U)

    def _draw_health_bar(self, canvas):
        width = canvas.shape[1]
        bar_width = min(220, width // 2)
        left = width - bar_width - min(20, width // 20)
        top = 22
        ratio = self.player_health / self.max_player_health
        if ratio > 0.6:
            color = (50, 225, 100)
        elif ratio > 0.3:
            color = (20, 190, 255)
        else:
            color = (20, 30, 255)
        cv.putText(canvas, f"HEALTH {self.player_health}/{self.max_player_health}",
                   (left, top - 5), cv.FONT_HERSHEY_SIMPLEX, 0.42,
                   (245, 255, 240), 1, cv.LINE_AA)
        cv.rectangle(canvas, (left, top), (left + bar_width, top + 12),
                     (10, 15, 15), -1)
        fill_width = round(bar_width * ratio)
        if fill_width:
            cv.rectangle(canvas, (left, top), (left + fill_width, top + 12),
                         color, -1)

    def draw_player(self, canvas, aim_position=None, weapon_type=1):
        height, width = canvas.shape[:2]
        center_x = width // 2
        is_ak = weapon_type == 2
        reload_progress = 0.0
        if self.reloading and self.reload_weapon == weapon_type:
            reload_progress = min(self.reload_timer / self.reload_duration, 1.0)
        reload_motion = math.sin(math.pi * reload_progress)
        recoil_distance = 18 if is_ak else 12
        pivot_y = (height + 24 + round(self.weapon_recoil * recoil_distance)
                   + round(reload_motion * 14))
        hit_strength = self.player_hit_timer / 0.34
        pivot_y += round(hit_strength * 12)
        muzzle_y = pivot_y - (275 if is_ak else 128)
        if aim_position is None:
            angle = 0.0
        else:
            dx = aim_position[0] - center_x
            dy = muzzle_y - aim_position[1]
            angle = max(-0.62, min(0.62, math.atan2(dx, max(1, dy))))
        angle += reload_motion * 0.22
        angle += self.player_hit_direction * hit_strength * 0.1
        cosine = math.cos(angle)
        sine = math.sin(angle)
        bob = round(math.sin(time.monotonic() * 2.4) * 1.5)
        pivot_y += bob

        def transform(point):
            x, y = point
            return (
                round(center_x + x * cosine - y * sine),
                round(pivot_y + x * sine + y * cosine),
            )

        def polygon(points, color, offset_y=0):
            points = np.asarray([
                transform((x, y + offset_y)) for x, y in points
            ], dtype=np.int32)
            cv.fillConvexPoly(canvas, points, color, cv.LINE_AA)

        skin = (160, 190, 210)
        glove_shadow = (130, 160, 180)
        if is_ak:
            polygon([(-165, 58), (-139, 3), (-108, -44), (-79, -112),
                     (-53, -128), (-39, -109), (-55, -74), (-81, -18),
                     (-110, 57), (-122, 77)], (30, 48, 40))
            polygon([(165, 58), (137, 1), (105, -48), (73, -97),
                     (49, -107), (35, -87), (55, -57), (85, -15),
                     (111, 58), (122, 77)], (30, 48, 40))

            polygon([(-15, -280), (15, -280), (13, -224), (-13, -224)], (20, 25, 28))
            polygon([(-21, -231), (21, -231), (24, -155), (-24, -155)], (40, 46, 48))
            polygon([(-24, -174), (24, -174), (20, -92), (-19, -83)], (28, 32, 35))
            polygon([(-17, -103), (18, -105), (22, -55), (13, -19),
                     (-12, -18), (-23, -57)], (22, 26, 28))
            polygon([(-23, -202), (23, -202), (18, -178), (-18, -178)], (60, 68, 65))
            magazine_drop = round(reload_motion * 42)
            polygon([(-18, -162), (-7, -151), (-4, -101),
                     (-18, -91), (-29, -105)], (34, 39, 38), magazine_drop)
            polygon([(13, -105), (36, -83), (29, -31),
                     (12, -37), (4, -78)], (28, 30, 32))
            polygon([(-4, -80), (5, -80), (8, -47), (-5, -47)], (10, 15, 18))

            polygon([(-73, -150), (-59, -174), (-35, -179),
                     (-20, -165), (-23, -146), (-42, -137), (-63, -139)], skin)
            polygon([(-57, -159), (-41, -166), (-24, -161),
                     (-21, -151), (-37, -146)], glove_shadow)
            polygon([(27, -81), (45, -77), (55, -64),
                     (49, -48), (31, -43), (16, -54), (14, -69)], skin)
            polygon([(20, -72), (37, -68), (47, -58),
                     (42, -52), (25, -57)], glove_shadow)
        else:
            polygon([(-158, 48), (-134, 0), (-92, -47), (-52, -87),
                     (-30, -80), (-47, -55), (-75, -15), (-109, 50), (-117, 72)], (30, 48, 40))
            polygon([(158, 48), (134, 0), (92, -18), (42, -40),
                     (12, -40), (22, -18), (56, 8), (106, 52), (117, 72)], (30, 48, 40))

            polygon([(-17, -137), (17, -137), (19, -78), (-19, -78)], (28, 32, 35))
            polygon([(-16, -81), (16, -81), (20, -44), (12, -12),
                     (-12, -12), (-20, -44)], (22, 26, 28))
            polygon([(-13, -129), (13, -129), (13, -121), (-13, -121)], (70, 80, 78))
            polygon([(-2, -77), (2, -77), (3, -48), (-3, -48)], (12, 15, 18))
            cv.ellipse(canvas, transform((0, -52)), (12, 13),
                       math.degrees(angle), 0, 180, (10, 12, 15), 2, cv.LINE_AA)
            magazine_drop = round(reload_motion * 34)
            polygon([(-8, -43), (8, -43), (9, -9), (-9, -9)],
                    (45, 52, 50), magazine_drop)

            polygon([(-48, -102), (-32, -113), (-10, -108), (2, -96),
                     (1, -82), (-12, -77), (-34, -81), (-49, -90)], skin)
            polygon([(-17, -69), (13, -72), (25, -57), (22, -37),
                     (11, -22), (-7, -22), (-20, -39), (-24, -55)], skin)
            polygon([(-36, -88), (-23, -87), (-15, -81), (-17, -75),
                     (-28, -77)], glove_shadow)
            polygon([(2, -64), (16, -63), (19, -53), (11, -48),
                     (1, -51)], glove_shadow)

        weapon = self.weapon_specs[weapon_type]
        ammo_text = (f"{weapon['name']}  {self.ammo[weapon_type]}/"
                 f"{self.reserve_ammo[weapon_type]} SPARE")
        cv.putText(canvas, ammo_text, (18, height - 22),
                   cv.FONT_HERSHEY_SIMPLEX, 0.55, (235, 245, 240), 1, cv.LINE_AA)
        if self.reloading:
            reload_name = self.weapon_specs[self.reload_weapon]["name"]
            label = f"RELOADING {reload_name}"
            text_width = cv.getTextSize(label, cv.FONT_HERSHEY_SIMPLEX, 0.55, 1)[0][0]
            left = (width - 120) // 2
            top = 54
            cv.putText(canvas, label, (center_x - text_width // 2, top),
                       cv.FONT_HERSHEY_SIMPLEX, 0.55, (240, 250, 242), 1, cv.LINE_AA)
            cv.rectangle(canvas, (left, top + 9), (left + 120, top + 16),
                         (20, 25, 22), -1)
            progress_width = round(120 * self.reload_timer / self.reload_duration)
            cv.rectangle(canvas, (left, top + 9), (left + progress_width, top + 16),
                         (60, 225, 150), -1)

    @staticmethod
    def _draw_terrain(canvas):
        height, width = canvas.shape[:2]
        horizon = round(height * 0.43)
        center = width // 2
        canvas[:] = (25, 35, 40)

        far_hills = np.asarray([
            (0, horizon + round(height * 0.02)),
            (round(width * 0.16), round(height * 0.31)),
            (round(width * 0.34), round(height * 0.39)),
            (round(width * 0.57), round(height * 0.29)),
            (round(width * 0.81), round(height * 0.37)),
            (width, round(height * 0.30)),
            (width, height),
            (0, height),
        ], dtype=np.int32)
        cv.fillPoly(canvas, [far_hills], (22, 52, 32), cv.LINE_AA)

        ground = np.asarray([
            (0, horizon), (width, horizon), (width, height), (0, height),
        ], dtype=np.int32)
        cv.fillPoly(canvas, [ground], (20, 65, 32), cv.LINE_AA)

        path = np.asarray([
            (round(width * 0.485), horizon),
            (round(width * 0.515), horizon),
            (round(width * 0.88), height),
            (round(width * 0.12), height),
        ], dtype=np.int32)
        cv.fillPoly(canvas, [path], (40, 52, 65), cv.LINE_AA)

        for fraction in (0.03, 0.33, 0.65, 1.0):
            bottom_x = round(width * (0.5 + 0.37 * fraction))
            cv.line(canvas, (center, horizon), (bottom_x, height), (28, 38, 46), 1, cv.LINE_AA)
            cv.line(canvas, (center, horizon), (width - bottom_x, height), (28, 38, 46), 1, cv.LINE_AA)

        for progress in (0.12, 0.23, 0.38, 0.56, 0.78):
            y = round(horizon + (height - horizon) * progress)
            half_width = round(width * (0.015 + 0.365 * progress))
            cv.line(canvas, (center - half_width, y), (center + half_width, y),
                    (45, 58, 70), 1, cv.LINE_AA)

        cv.line(canvas, (0, horizon), (width, horizon), (40, 75, 42), 2, cv.LINE_AA)
        for x, y, size in ((0.08, 0.65, 7), (0.22, 0.85, 9), (0.78, 0.7, 8),
                           (0.91, 0.9, 10), (0.13, 0.96, 11), (0.87, 0.52, 6)):
            point = (round(width * x), round(height * y))
            cv.line(canvas, point, (point[0] - size, point[1] - size * 2),
                    (30, 85, 38), 2, cv.LINE_AA)
            cv.line(canvas, point, (point[0] + size, point[1] - size * 2),
                    (30, 85, 38), 2, cv.LINE_AA)