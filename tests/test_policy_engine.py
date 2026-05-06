from packages.core.policy import evaluate_constraints, resolve_policy


def test_evaluate_constraints_blocked_for_multi_agent_in_review() -> None:
    policy = resolve_policy("review")
    result = evaluate_constraints(policy=policy, runtime={"wants_multi_agent": True}, action="multi_agent")
    assert result["blocked"] is True
    assert "allow_multi_agent" in result["triggered_constraints"]
    assert result["severity"] == "blocked"


def test_evaluate_constraints_requires_approval_for_risk_limit() -> None:
    policy = resolve_policy("review")
    result = evaluate_constraints(
        policy=policy,
        metrics={"files_changed_count": 1, "added_lines": 3, "removed_lines": 1},
        patch_meta={"risk_level": "medium", "file_status": "modified"},
        action="patch",
    )
    assert result["blocked"] is False
    assert result["requires_approval"] is True
    assert "max_risk_level" in result["triggered_constraints"]
    assert result["severity"] == "approval_required"
