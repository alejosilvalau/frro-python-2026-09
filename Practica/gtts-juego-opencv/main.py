import sys
import threading
import time
import random

from phrases import SUPPORTED_LANGUAGES, get_phrases, get_random_phrase
from face_tracker import FaceTracker
from game import Game


def list_languages():
    print("\n=== Supported Languages ===")
    for code, name in sorted(SUPPORTED_LANGUAGES.items()):
        print(f"  {code}  -  {name}")
    print(f"\nUsage: python {sys.argv[0]} <language_code>")
    print(f"Example: python {sys.argv[0]} es\n")


def run_game(shared_state, game):
    phrase_interval = 180
    frame_count = 0

    while game.running and shared_state["running"]:
        game.handle_events()

        yaw = shared_state["yaw"]
        pitch = shared_state["pitch"]
        face_detected = shared_state["face_detected"]
        key_fitted = shared_state["key_fitted"]

        game.update(yaw, pitch, face_detected)
        game.draw()

        if game.key_fitted and not shared_state.get("was_fitted", False):
            shared_state["key_fitted"] = True
            shared_state["was_fitted"] = True
            phrase = get_random_phrase(game.phrases_dict)
            game.play_phrase(phrase, game.phrases_dict[phrase])
        elif not game.key_fitted:
            shared_state["was_fitted"] = False
            shared_state["key_fitted"] = False

        frame_count += 1
        if frame_count >= phrase_interval and face_detected and not game.key_fitted:
            frame_count = 0
            phrase = get_random_phrase(game.phrases_dict)
            game.play_phrase(phrase, game.phrases_dict[phrase])

        game.tick()

    shared_state["running"] = False
    game.quit()


def run_tracker(shared_state, tracker):
    import cv2

    window_name = "Face Tracker"
    while shared_state["running"]:
        tracker.update()
        shared_state["face_detected"] = tracker.face_detected
        shared_state["yaw"] = tracker.yaw
        shared_state["pitch"] = tracker.pitch

        key_fitted = shared_state.get("key_fitted", False)
        frame = tracker.get_frame_with_border(key_fitted=key_fitted)

        if frame is not None:
            cv2.imshow(window_name, frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 27 or key == ord("q"):
            shared_state["running"] = False
            break

    tracker.release()
    cv2.destroyAllWindows()


def main():
    if len(sys.argv) < 2:
        list_languages()
        return

    lang_code = sys.argv[1].lower()
    if lang_code not in SUPPORTED_LANGUAGES:
        print(f"Error: '{lang_code}' not in supported languages.")
        list_languages()
        return

    print(f"Loading phrases for {SUPPORTED_LANGUAGES[lang_code]} ({lang_code})...")
    phrases = get_phrases(lang_code)
    print(f"Phrases loaded ({len(phrases)} cached). Starting game...")

    shared_state = {
        "running": True,
        "face_detected": False,
        "yaw": 0.0,
        "pitch": 0.0,
        "key_fitted": False,
        "was_fitted": False,
    }

    tracker = FaceTracker()
    game = Game()
    game.set_phrases(phrases)

    tracker_thread = threading.Thread(target=run_tracker, args=(shared_state, tracker), daemon=True)
    tracker_thread.start()

    try:
        run_game(shared_state, game)
    except KeyboardInterrupt:
        shared_state["running"] = False

    tracker_thread.join(timeout=3)
    print("Game ended.")


if __name__ == "__main__":
    main()
