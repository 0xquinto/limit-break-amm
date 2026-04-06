"""Tests for critic.py — dismissal quality scoring and reinvestigation."""


def test_score_dismissal_quality_weak():
    """Dismissal with no test and vague reason → low score."""
    from audit.orchestrator.critic import score_dismissal_quality
    entry = {
        "id": "H-R1-CP-01", "status": "dismissed",
        "detail": "Looks safe",
    }
    score = score_dismissal_quality(entry)
    assert score < 30


def test_score_dismissal_quality_strong():
    """Dismissal with test file, guard location, and failure_class → high score."""
    from audit.orchestrator.critic import score_dismissal_quality
    entry = {
        "id": "H-R1-CP-01", "status": "dismissed",
        "test_file": "test/TestH001.sol",
        "guard_location": "AMMModule.sol:2144",
        "failure_class": "strategic",
        "detail": "require(_amount > 0) at AMMModule.sol:2144 blocks zero-amount path",
    }
    score = score_dismissal_quality(entry)
    assert score >= 70


def test_score_dismissal_quality_tested_auto_pass():
    """Tested/confirmed entries auto-score 100."""
    from audit.orchestrator.critic import score_dismissal_quality
    entry = {"id": "H-R1-CP-01", "status": "confirmed", "test_file": "test/T.sol"}
    score = score_dismissal_quality(entry)
    assert score == 100


def test_identify_weak_dismissals():
    """identify_weak_dismissals returns entries below threshold."""
    from audit.orchestrator.critic import identify_weak_dismissals
    results = [
        {"id": "H-001", "status": "dismissed", "detail": "safe"},
        {"id": "H-002", "status": "dismissed", "test_file": "test/T.sol",
         "guard_location": "X.sol:42", "failure_class": "strategic",
         "detail": "require blocks"},
        {"id": "H-003", "status": "confirmed", "test_file": "test/T.sol"},
    ]
    weak = identify_weak_dismissals(results, threshold=50)
    assert len(weak) == 1
    assert weak[0]["id"] == "H-001"


def test_build_critic_feedback():
    """Build critic feedback for weak dismissals."""
    from audit.orchestrator.critic import build_critic_feedback
    weak = [{"id": "H-001", "status": "dismissed", "detail": "safe"}]
    feedback = build_critic_feedback(weak)
    assert "H-001" in feedback
    assert "test" in feedback.lower() or "forge" in feedback.lower()


def test_build_reinvestigation_prompt():
    """Reinvestigation prompt contains hypothesis details and instructions."""
    from audit.orchestrator.critic import build_reinvestigation_prompt
    weak = [
        {"id": "H-001", "status": "dismissed", "detail": "safe",
         "mechanism": "Overflow in fee calculation at AMMModule.sol:2144"},
    ]
    prompt = build_reinvestigation_prompt(weak, agent_name="precision-sniper")
    assert "H-001" in prompt
    assert "AMMModule.sol:2144" in prompt or "fee calculation" in prompt
    assert "forge" in prompt.lower() or "test" in prompt.lower()
