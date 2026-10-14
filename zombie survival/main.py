import cv2 as cv
from controls import Control
from handDetector import handDetector
from second_window import SecondWindow
from visuals import Visuals
from zombie_scene import ZombieScene

cap = cv.VideoCapture(0)
detector = handDetector()
control = Control()
game = SecondWindow("Game", side="right")  
visuals = Visuals()
zombie_scene = ZombieScene()
shooting_was_active = False
reload_gesture_was_active = False
weapon_type = 1

while True:
    ok, frame = cap.read()
    if not ok:
        break
    frame = cv.flip(frame, 1)

    results = detector.detect_hands(frame)

    game.clear(frame)          
    action = game.main_menu(frame)
    if action == "quit":
        break
    
    if game.screen == "ready":
        fingertips = control.both_index_fingertips(results, game.canvas.shape)
        if game.ready_pressed(fingertips):
            zombie_scene.start()
            game.begin_countdown()

    if game.screen == "countdown":
        countdown_label = game.countdown_label()
        if countdown_label is None:
            game.screen = "play"
        else:
            game.draw_countdown(game.canvas, countdown_label)

    if game.screen == "play":
        zombie_scene.update(game.canvas)
        # Check if player health dropped to 0
        if zombie_scene.player_health <= 0:
            # Save score to external file storage via leaderboard method
            game.add_score(game.player_name or "Anonymous", zombie_scene.wave_number)
            game.screen = "game_over"

    if game.screen == "try_again":
        zombie_scene.start()
        game.begin_countdown()

    mouse_position = visuals.draw_mouse(game.canvas, results)
    detected_weapon = control.gun_type(results, "Right")
    if detected_weapon in (1, 2):
        weapon_type = detected_weapon

    shooting_is_active = control.shooting(results, "Left")
    reload_gesture_is_active = control.left_hand_reload(results)
    
    if game.screen == "play":
        if reload_gesture_is_active and not reload_gesture_was_active:
            zombie_scene.start_reload(weapon_type)
        if weapon_type == 2 and shooting_is_active:
            zombie_scene.shoot(mouse_position, game.canvas.shape, weapon_type)
        elif weapon_type == 1 and shooting_is_active and not shooting_was_active:
            zombie_scene.shoot(mouse_position, game.canvas.shape, weapon_type)
    elif shooting_is_active and not shooting_was_active:
        game.select_at(mouse_position)
        
    shooting_was_active = shooting_is_active
    reload_gesture_was_active = reload_gesture_is_active
    
    if game.screen == "play":
        zombie_scene.draw_player(game.canvas, mouse_position, weapon_type)

    game.show(frame)

    key = cv.waitKey(1) & 0xFF
    if key == ord("q") and game.screen != "name_entry":
        break
    
    if game.screen == "name_entry":
        game.handle_keyboard_input(key)
    else:
        if key in (ord("r"), ord("R")) and game.screen == "play":
            zombie_scene.start_reload(weapon_type)

cap.release()
cv.destroyAllWindows()