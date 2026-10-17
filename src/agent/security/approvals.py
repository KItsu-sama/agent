"""Interactive approval prompts."""

fromopenhands_sdk.openhands.sdk.event import ActionEvent


def approve_plan() -> bool:
    try:
        answer = input("Approve this plan and allow implementation? (yes/no): ")
    except (EOFError, KeyboardInterrupt):
        print("\nNo approval received.")
        return False
    return answer.strip().lower() in {"yes", "y"}


def confirm_pending_actions(pending: list[ActionEvent]) -> bool:
    print(f"\n{len(pending)} action(s) require approval:")
    for index, action in enumerate(pending, start=1):
        summary = action.summary or "(no summary provided)"
        preview = str(action.action).replace("\n", " ")[:240]
        print(f"{index}. [{action.tool_name}] {summary}")
        print(f"   {preview}")

    try:
        answer = input("Approve these actions? (yes/no): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nNo approval received; rejecting the actions.")
        return False
    return answer in {"yes", "y"}

