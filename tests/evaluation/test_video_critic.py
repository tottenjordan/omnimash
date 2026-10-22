from omnimash.evaluation.models import DefectCategory, VideoEvaluationScorecard
from omnimash.evaluation.video_critic import VideoCriticAgent


def test_video_critic_rubric_generation():
    critic = VideoCriticAgent(mock_mode=True)
    prompt = """### DIRECTORIAL INTENT
Cinematic battle scene.
### CHARACTER PROFILES
[Role A] Neon Warrior in cyber armor.
### SCREENPLAY
[0-3s] [Role A] leaps from neon balcony.
[3-6s] [Role A] activates blade.
### AUDIO & ATMOSPHERE
Synthwave bass.
"""
    rubric = critic.build_rubric_prompt(prompt)
    assert "Video-Text Adherence" in rubric
    assert "Character Likeness" in rubric
    assert "Audio Balance" in rubric
    assert "Tag & Index Symmetry" in rubric


def test_video_critic_evaluate_clean_prompt_mock():
    critic = VideoCriticAgent(mock_mode=True)
    prompt = """### DIRECTORIAL INTENT
Parody scene.
### CHARACTER PROFILES
[Role A] DumbleDior: Reference sheet attached.
### SCREENPLAY
[0-3s] [Role A] [Instrumental: ducking -18dB under speech] "Welcome to fashion week."
[3-6s] [Role A] struts down catwalk.
### AUDIO & ATMOSPHERE
[Instrumental: rhythmic house beat]
"""
    scorecard = critic.evaluate_video(
        session_id="test_sess_clean",
        turn_id="turn_0",
        prompt=prompt,
        video_uri="gs://omnimash-media/test/clip.mp4",
    )
    assert isinstance(scorecard, VideoEvaluationScorecard)
    assert scorecard.overall_rating >= 80.0
    assert scorecard.pass_verdict is True
    assert scorecard.video_text_adherence.score >= 80.0
    assert scorecard.character_likeness.score >= 80.0
    assert scorecard.audio_visual_harmony.score >= 80.0
    assert scorecard.tag_and_index_integrity.score >= 80.0


def test_video_critic_evaluate_defect_audio_drowned_mock():
    critic = VideoCriticAgent(mock_mode=True)
    prompt = """### DIRECTORIAL INTENT
Interview scene.
### CHARACTER PROFILES
[Role A] Guest.
### SCREENPLAY
[0-3s] [Role A] speaks words: "I am saying something important."
### AUDIO & ATMOSPHERE
Blaring techno beat at 140bpm with heavy sub-bass.
"""
    scorecard = critic.evaluate_video(
        session_id="test_sess_audio",
        turn_id="turn_0",
        prompt=prompt,
        video_uri="gs://omnimash-media/test/clip.mp4",
        user_critique="Music completely covers speech",
        reported_defects=[DefectCategory.AUDIO_DROWNED],
    )
    assert scorecard.audio_visual_harmony.score < 70.0
    assert DefectCategory.AUDIO_DROWNED in scorecard.detected_defects
    assert scorecard.pass_verdict is False
    assert scorecard.suggested_prompt_patch is not None


def test_video_critic_evaluate_defect_wardrobe_contradiction_mock():
    critic = VideoCriticAgent(mock_mode=True)
    prompt = """### DIRECTORIAL INTENT
Duel.
### CHARACTER PROFILES
[Role A] Harry wearing red silk tuxedo, baggy sweatpants, green trench coat, blue fedora.
### SCREENPLAY
[0-3s] [Role A] stands in battlefield.
"""
    scorecard = critic.evaluate_video(
        session_id="test_sess_wardrobe",
        turn_id="turn_0",
        prompt=prompt,
        video_uri="gs://omnimash-media/test/clip.mp4",
        reported_defects=[DefectCategory.WARDROBE_CONTRADICTION],
    )
    assert scorecard.character_likeness.score < 75.0
    assert DefectCategory.WARDROBE_CONTRADICTION in scorecard.detected_defects
    assert scorecard.pass_verdict is False
