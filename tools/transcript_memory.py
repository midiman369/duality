"""Distil a Claude Code session transcript (.jsonl) into readable memory files.

    python3 transcript_memory.py <session.jsonl> <out dir>

Writes conversation.md (the user's messages and Claude's replies, no tool calls, tool output or thinking),
user-requests.md (the user's messages alone) and compaction-summaries.md (the summaries written each time the
context was compacted)."""
import json
import os
import re
import sys

SR = re.compile(r"<system-reminder>.*?</system-reminder>\s*", re.S)
AT = re.compile(r'@"(/root/\.claude/uploads/[^"]+)"')


def clean(text):
    text = SR.sub("", text)
    return AT.sub(lambda m: "[upload: " + os.path.basename(m.group(1)) + "]", text).strip()


def parts_of(content):
    if isinstance(content, str):
        return clean(content)
    out = []
    for x in content:
        if x.get("type") == "text":
            out.append(clean(x["text"]))
        elif x.get("type") == "image":
            out.append("[image]")
    return "\n\n".join(p for p in out if p)


def is_human(d):
    if d.get("type") != "user" or d.get("isMeta") or d.get("isCompactSummary"):
        return False
    c = d["message"].get("content")
    if isinstance(c, list) and c and all(x.get("type") == "tool_result" for x in c):
        return False
    origin = d.get("origin") or {}
    return origin.get("kind", "human") == "human"


def stamp(ts):
    return ts.replace("T", " ")[:16] + " UTC" if ts else ""


def main(src, out):
    os.makedirs(out, exist_ok=True)
    conv, reqs, sums = [], [], []
    turn, last_role, first, last = 0, None, None, None
    with open(src) as f:
        for line in f:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            ts = d.get("timestamp")
            if ts:
                first, last = first or ts, ts
            if d.get("type") == "user" and d.get("isCompactSummary"):
                text = parts_of(d["message"].get("content", ""))
                sums.append(f"## {len(sums) + 1}. {stamp(ts)}\n\n{text}\n")
                conv.append(f"\n---\n\n*Context compacted here ({stamp(ts)}); summary {len(sums)} in "
                            f"compaction-summaries.md.*\n")
                last_role = None
                continue
            if is_human(d):
                text = parts_of(d["message"].get("content", ""))
                if not text:
                    continue
                turn += 1
                conv.append(f"\n---\n\n## {turn}. {stamp(ts)}\n\n**User:**\n\n{text}\n")
                reqs.append(f"## {turn}. {stamp(ts)}\n\n{text}\n")
                last_role = "user"
                continue
            if d.get("type") == "user" and (d.get("origin") or {}).get("kind") == "task-notification":
                conv.append("\n*(a background task finished)*\n")
                continue
            if d.get("type") == "assistant":
                texts = [x["text"].strip() for x in d["message"].get("content", [])
                         if x.get("type") == "text" and x.get("text", "").strip()]
                if texts:
                    if last_role != "claude":
                        conv.append("\n**Claude:**\n")
                    conv.append("\n" + "\n\n".join(texts) + "\n")
                    last_role = "claude"
    head = (f"Session {os.path.basename(src).split('.')[0]}, {stamp(first)} to {stamp(last)}; "
            f"{turn} user messages, {len(sums)} compactions.\n")
    with open(os.path.join(out, "conversation.md"), "w") as f:
        f.write("# Conversation (user messages and Claude's replies)\n\n" + head +
                "Tool calls, tool output and Claude's thinking are left out; the full record is in transcripts/.\n")
        f.writelines(conv)
    with open(os.path.join(out, "user-requests.md"), "w") as f:
        f.write("# The user's messages, in order\n\n" + head + "\n")
        f.write("\n".join(reqs))
    with open(os.path.join(out, "compaction-summaries.md"), "w") as f:
        f.write("# Compaction summaries\n\n" + head +
                "Each was written when the context filled up; together they trace the work's state over time.\n\n")
        f.write("\n".join(sums))
    print(head.strip())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
