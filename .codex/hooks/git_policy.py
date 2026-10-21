"""Guardrail de comandos Git para PreToolUse. No ejecuta comandos Git."""
import json
import os
import re
import shlex
import sys


def deny_reason(command):
    if not isinstance(command, str) or not command.strip():
        return "No se pudo verificar el comando de shell."
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return "Comando de shell ambiguo: usar comandos simples separados."
    # Only direct, standalone commands may push. Shell syntax and wrappers
    # cannot be trusted to preserve the argv evaluated by the prefix rules.
    git_present = any(os.path.basename(t) == "git" for t in tokens)
    sensitive = bool(re.search(r"\b(?:push|tag|update-ref|send-pack)\b", command))
    shell_syntax = any(c in command for c in "\n;|&<>`$(){}*?\\")
    wrappers = {"bash", "sh", "zsh", "env", "command", "exec", "sudo", "xargs"}
    if sensitive and (git_present or re.search(r"\bgit\b", command)):
        if shell_syntax or (tokens and os.path.basename(tokens[0]) in wrappers):
            return "Operación Git sensible envuelta o compuesta: usar un comando Git directo."
    if not git_present:
        return None
    if tokens[0] != "git":
        return "Usar el ejecutable git directamente, sin rutas ni envoltorios."
    if len(tokens) < 2:
        return None
    subcommand = tokens[1]
    if subcommand.startswith("-"):
        return "Opciones globales de Git no verificables: usar git <subcomando> directamente."
    args = tokens[2:]
    if subcommand in {"update-ref", "send-pack"}:
        return "Usar comandos Git de alto nivel; no se permite modificar referencias mediante plumbing."
    if subcommand == "tag":
        for arg in args:
            if arg.startswith("--delete") or (arg.startswith("-") and not arg.startswith("--") and "d" in arg[1:]):
                return "No se permite eliminar tags locales."
    if subcommand != "push":
        return None
    # Fail closed for options not explicitly understood. All deletions are
    # blocked, including ambiguous short tag names in deletion refspecs.
    safe_long = {"--atomic", "--tags", "--follow-tags", "--dry-run", "--porcelain", "--verbose", "--quiet", "--set-upstream"}
    safe_short = set("unvq")
    for arg in args:
        if arg.startswith("+") or ":+" in arg:
            return "No se permite forzar un push mediante refspecs con '+'."
        if arg.startswith(":"):
            return "No se permiten refspecs de eliminación remota."
        if arg.startswith("--"):
            if arg not in safe_long and arg != "--":
                return "Opción de push prohibida o no verificable: " + arg
        elif arg.startswith("-"):
            if not arg[1:] or any(c not in safe_short for c in arg[1:]):
                return "Opción de push prohibida o no verificable: " + arg
    return None


def main():
    try:
        event = json.load(sys.stdin)
        tool_input = event.get("tool_input", {})
        if isinstance(tool_input, str):
            tool_input = json.loads(tool_input)
        command = tool_input.get("command", tool_input.get("cmd"))
        reason = deny_reason(command)
    except Exception:
        reason = "No se pudo validar la entrada del hook; operación bloqueada."
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}, ensure_ascii=False))
    else:
        # No allow decision: preserve the normal approval and rules checks.
        print("{}")


if __name__ == "__main__":
    main()
